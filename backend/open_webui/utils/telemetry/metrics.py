"""OpenTelemetry metrics bootstrap for Open WebUI.

This module initialises a MeterProvider that sends metrics to an OTLP
collector. The collector is responsible for exposing a Prometheus
`/metrics` endpoint – WebUI does **not** expose it directly.

Metrics collected:

* http.server.requests (counter)
* http.server.duration (histogram, milliseconds)

Attributes used: http.method, http.route, http.status_code

If you wish to add more attributes (e.g. user-agent) you can, but beware of
high-cardinality label sets.
"""

from __future__ import annotations

import time
from typing import Dict, List, Sequence, Any
from base64 import b64encode

from fastapi import FastAPI, Request
from opentelemetry import metrics

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.view import View
from opentelemetry.sdk.metrics.export import (
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource

from open_webui.env import (
    OTEL_SERVICE_NAME,
    ENABLE_OTEL_METRICS,
    OTEL_METRICS_EXPORTER_OTLP_ENDPOINT,
    OTEL_METRICS_BASIC_AUTH_USERNAME,
    OTEL_METRICS_BASIC_AUTH_PASSWORD,
    OTEL_METRICS_OTLP_SPAN_EXPORTER,
    OTEL_METRICS_EXPORTER_OTLP_INSECURE,
)
from open_webui.models.users import Users

_EXPORT_INTERVAL_MILLIS = 10_000  # 10 seconds


def _build_meter_provider(resource: Resource) -> MeterProvider | None:
    """Return a configured MeterProvider, or ``None`` when required exporter
    packages are unavailable.
    """
    headers = []
    if OTEL_METRICS_BASIC_AUTH_USERNAME and OTEL_METRICS_BASIC_AUTH_PASSWORD:
        auth_string = (
            f"{OTEL_METRICS_BASIC_AUTH_USERNAME}:{OTEL_METRICS_BASIC_AUTH_PASSWORD}"
        )
        auth_header = b64encode(auth_string.encode()).decode()
        headers = [("authorization", f"Basic {auth_header}")]

    # Periodic reader pushes metrics over OTLP/gRPC to collector
    try:
        if OTEL_METRICS_OTLP_SPAN_EXPORTER == "http":
            # Import only when required so module import-time doesn't fail in
            # environments that don't install optional exporter packages.
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
                OTLPMetricExporter as OTLPHttpMetricExporter,
            )

            readers: List[PeriodicExportingMetricReader] = [
                PeriodicExportingMetricReader(
                    OTLPHttpMetricExporter(
                        endpoint=OTEL_METRICS_EXPORTER_OTLP_ENDPOINT, headers=headers
                    ),
                    export_interval_millis=_EXPORT_INTERVAL_MILLIS,
                )
            ]
        else:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter,
            )

            readers: List[PeriodicExportingMetricReader] = [
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(
                        endpoint=OTEL_METRICS_EXPORTER_OTLP_ENDPOINT,
                        insecure=OTEL_METRICS_EXPORTER_OTLP_INSECURE,
                        headers=headers,
                    ),
                    export_interval_millis=_EXPORT_INTERVAL_MILLIS,
                )
            ]
    except Exception as exc:
        # Optional exporters may not be installed in test/dev environments;
        # metrics are best-effort – log at debug level and return None to
        # indicate we couldn't build a provider so `setup_metrics` keeps
        # the no-op helpers.
        import logging

        log = logging.getLogger(__name__)
        log.debug("Could not build meter provider (optional exporters may be missing): %s", exc)
        return None

    # Optional view to limit cardinality: drop user-agent etc.
    views: List[View] = [
        View(
            instrument_name="http.server.duration",
            attribute_keys=["http.method", "http.route", "http.status_code"],
        ),
        View(
            instrument_name="http.server.requests",
            attribute_keys=["http.method", "http.route", "http.status_code"],
        ),
        View(
            instrument_name="webui.users.total",
        ),
        View(
            instrument_name="webui.users.active",
        ),
        View(
            instrument_name="webui.users.active.today",
        ),
    ]

    provider = MeterProvider(
        resource=resource,
        metric_readers=list(readers),
        views=views,
    )
    return provider


# No-op helpers exported so callers can safely import and call them even when metrics are not enabled.
def inc_billing_webhook(event_type: str, outcome: str = "success", attrs: Dict[str, str] | None = None):
    """Increment billing webhook event counter (no-op until metrics are configured)."""
    return None


def inc_reconcile_result(action: str, reason: str | None = None):
    """Record a reconcile result (no-op until metrics are configured)."""
    return None


def setup_metrics(app: FastAPI, resource: Resource) -> None:
    """Attach OTel metrics middleware to *app* and initialise provider.

    Metrics are only enabled when ``ENABLE_OTEL_METRICS`` is true. This
    avoids background exporter threads being started in test/dev
    environments where metrics aren't desired.
    """

    if not ENABLE_OTEL_METRICS:
        return

    provider = _build_meter_provider(resource)
    if provider is None:
        # Couldn't build a provider (likely optional exporter package missing).
        # Keep no-op helpers – metrics are best-effort.
        return

    metrics.set_meter_provider(provider)
    meter = metrics.get_meter(__name__)

    # Instruments
    request_counter = meter.create_counter(
        name="http.server.requests",
        description="Total HTTP requests",
        unit="1",
    )
    duration_histogram = meter.create_histogram(
        name="http.server.duration",
        description="HTTP request duration",
        unit="ms",
    )

    def observe_active_users(
        options: metrics.CallbackOptions,
    ) -> Sequence[metrics.Observation]:
        return [
            metrics.Observation(
                value=Users.get_active_user_count(),
            )
        ]

    def observe_total_registered_users(
        options: metrics.CallbackOptions,
    ) -> Sequence[metrics.Observation]:
        return [
            metrics.Observation(
                value=len(Users.get_users()["users"]),
            )
        ]

    meter.create_observable_gauge(
        name="webui.users.total",
        description="Total number of registered users",
        unit="users",
        callbacks=[observe_total_registered_users],
    )

    meter.create_observable_gauge(
        name="webui.users.active",
        description="Number of currently active users",
        unit="users",
        callbacks=[observe_active_users],
    )

    def observe_users_active_today(
        options: metrics.CallbackOptions,
    ) -> Sequence[metrics.Observation]:
        return [metrics.Observation(value=Users.get_num_users_active_today())]

    meter.create_observable_gauge(
        name="webui.users.active.today",
        description="Number of users active since midnight today",
        unit="users",
        callbacks=[observe_users_active_today],
    )

    # Billing-specific instruments
    billing_webhook_counter = meter.create_counter(
        name="billing.webhook.events",
        description="Billing webhook events",
        unit="1",
    )

    billing_reconcile_counter = meter.create_counter(
        name="billing.reconcile.runs",
        description="Reconcile run outcomes",
        unit="1",
    )

    def observe_pending_purchases(options: metrics.CallbackOptions):
        # Lazy import so module import time isn't heavy
        try:
            from open_webui.internal.db import get_db
            from open_webui.models.billing import TokenPurchase

            with get_db() as db:
                cnt = db.query(TokenPurchase).filter_by(status="pending").count()
                return [metrics.Observation(value=cnt)]
        except Exception:
            # In rare cases, database won't be available during startup; return zero
            return [metrics.Observation(value=0)]

    meter.create_observable_gauge(
        name="billing.purchases.pending",
        description="Number of pending token purchases",
        unit="purchases",
        callbacks=[observe_pending_purchases],
    )

    # Helper functions to be used by other modules (safe no-op if provider not fully configured)
    def inc_billing_webhook(event_type: str, outcome: str = "success", attrs: Dict[str, str] | None = None):
        try:
            extra = attrs or {}
            billing_webhook_counter.add(1, {"event_type": event_type, "outcome": outcome, **extra})
        except Exception:
            # swallow; metrics are best-effort
            pass

    def inc_reconcile_result(action: str, reason: str | None = None):
        try:
            billing_reconcile_counter.add(1, {"action": action, "reason": reason or ""})
        except Exception:
            pass

    # Expose helpers at module level
    globals()["inc_billing_webhook"] = inc_billing_webhook
    globals()["inc_reconcile_result"] = inc_reconcile_result

    # FastAPI middleware
    @app.middleware("http")
    async def _metrics_middleware(request: Request, call_next):
        start_time = time.perf_counter()

        status_code = None
        try:
            response = await call_next(request)
            status_code = getattr(response, "status_code", 500)
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            # Route template e.g. "/items/{item_id}" instead of real path.
            route = request.scope.get("route")
            route_path = getattr(route, "path", request.url.path)

            attrs: Dict[str, str | int] = {
                "http.method": request.method,
                "http.route": route_path,
                "http.status_code": status_code,
            }

            request_counter.add(1, attrs)
            duration_histogram.record(elapsed_ms, attrs)
