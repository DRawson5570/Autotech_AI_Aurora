from fastapi import FastAPI
from opentelemetry.sdk.resources import Resource
import importlib


def test_metrics_helpers_are_callable():
    # Initialize metrics on a dummy app so helpers are registered
    app = FastAPI()
    from open_webui.utils.telemetry.metrics import setup_metrics

    setup_metrics(app, Resource.create({'service.name': 'test'}))

    # Import helpers and call them; they should not raise
    from open_webui.utils.telemetry.metrics import inc_billing_webhook, inc_reconcile_result

    inc_billing_webhook('checkout.session.completed', 'received')
    inc_billing_webhook('checkout.session.completed', 'confirmed', {'purchase_id': 'p_test'})
    inc_reconcile_result('confirmed', 'unit_test')

    # If we get here, helpers are callable
    assert True
