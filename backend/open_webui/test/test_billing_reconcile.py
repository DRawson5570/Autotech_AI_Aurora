import importlib
import time


def test_reconcile_one(monkeypatch):
    billing = importlib.import_module('open_webui.models.billing')

    # Create a pending purchase
    uid = f"recon_user_{int(time.time())}"
    tp = billing.purchase_tokens(uid, 200, cost='4.00', currency='USD', status='pending')

    # Monkeypatch stripe to return a session with a succeeded payment_intent
    class FakePaymentIntent:
        def __init__(self):
            self.id = 'pi_ok'
            self.status = 'succeeded'

    class FakeSession:
        def __init__(self):
            self.id = 'sess_ok'
            self.payment_intent = 'pi_ok'

        def get(self, key):
            if key == 'payment_intent':
                return 'pi_ok'
            return None

    class FakeStripe:
        api_key = None

        class SessionObj:
            @staticmethod
            def retrieve(session_id):
                return {'id': 'sess_ok', 'payment_intent': 'pi_ok'}

        checkout = type('c', (), {'Session': SessionObj})

        class PaymentIntent:
            @staticmethod
            def retrieve(pid):
                return {'id': pid, 'status': 'succeeded'}

    import sys
    monkeypatch.setitem(sys.modules, 'stripe', FakeStripe)

    # attach session id to purchase
    tp2 = tp
    from open_webui.internal.db import get_db
    with get_db() as db:
        p = db.query(importlib.import_module('open_webui.models.billing').TokenPurchase).filter_by(id=tp2.id).first()
        p.stripe_session_id = 'sess_ok'
        db.commit()

    res = billing.reconcile_one(tp.id)
    assert res['action'] in ('confirmed', 'none')

    # If it confirmed, balance should be >= tokens
    if res['action'] == 'confirmed':
        bal = billing.get_user_balance(uid)
        assert bal >= 200
