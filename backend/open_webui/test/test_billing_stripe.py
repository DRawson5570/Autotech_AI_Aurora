import importlib
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app():
    billing = importlib.import_module('open_webui.routers.billing')
    app = FastAPI()
    app.include_router(billing.router)
    return app


def test_create_checkout_session(monkeypatch):
    app = _make_app()

    # override get_verified_user
    from open_webui.utils.auth import get_verified_user as real_verified

    def fake_verified():
        class FakeUser:
            id = 'stripe-user'
            role = 'user'
            email = 'stripe@example.com'

        return FakeUser()

    app.dependency_overrides[real_verified] = fake_verified

    import os

    # set stripe api key env so endpoint doesn't reject
    os.environ['STRIPE_API_KEY'] = 'sk_test_abc'

    # monkeypatch stripe
    class FakeSession:
        def __init__(self):
            self.id = 'sess_123'
            self.url = 'https://checkout.test/session'

    class FakeCheckoutSession:
        @staticmethod
        def create(**kwargs):
            return FakeSession()

    class FakeStripe:
        api_key = None
        checkout = type('c', (), {'Session': FakeCheckoutSession})

    # Monkeypatch stripe module
    import sys
    monkeypatch.setitem(sys.modules, 'stripe', FakeStripe)

    client = TestClient(app)
    resp = client.post('/user/create_checkout_session', json={'tokens': 500, 'cost': '10.00'})
    assert resp.status_code == 200
    data = resp.json()
    assert 'url' in data


def test_webhook_confirm(monkeypatch):
    app = _make_app()

    # monkeypatch Billing.confirm_purchase
    import open_webui.models.billing as billing

    called = {}

    def fake_confirm(purchase_id, stripe_payment_id=None):
        called['id'] = purchase_id
        called['pid'] = stripe_payment_id
        return True

    # ensure module-level helper exists and monkeypatch it
    monkeypatch.setattr(billing, 'confirm_purchase', fake_confirm)

    client = TestClient(app)

    # simulate stripe event payload dict
    payload = {
        'type': 'checkout.session.completed',
        'data': {
            'object': {
                'metadata': {'purchase_id': 'p123'},
                'payment_intent': 'pi_abc',
            }
        }
    }

    resp = client.post('/webhook', data=json.dumps(payload), headers={'stripe-signature': 't'})
    assert resp.status_code == 200
    assert called['id'] == 'p123'
    assert called['pid'] == 'pi_abc'
