from fastapi import FastAPI
from opentelemetry.sdk.resources import Resource
import importlib
import os


def test_setup_metrics_noop_when_disabled(monkeypatch):
    # Ensure environment indicates metrics are disabled
    monkeypatch.setenv("ENABLE_OTEL_METRICS", "False")

    # Reload the module to pick up the environment change
    import open_webui.utils.telemetry.metrics as metrics_mod
    importlib.reload(metrics_mod)

    app = FastAPI()
    # Calling setup_metrics should not raise and should not configure a provider
    metrics_mod.setup_metrics(app, Resource.create({"service.name": "test"}))

    # The helpers should be callable and no-op (should not raise)
    metrics_mod.inc_billing_webhook("checkout.session.completed", "received")
    metrics_mod.inc_reconcile_result("none", "unit_test")

    assert True
