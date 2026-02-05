import time
import importlib


def test_confirm_purchase_and_credit_balance():
    billing = importlib.import_module('open_webui.models.billing')

    uid = f"test_user_{int(time.time())}"

    # Create a pending purchase
    tp = billing.purchase_tokens(uid, 100, cost='1.00', currency='USD', status='pending')
    assert tp.status == 'pending'

    # Confirm the purchase
    confirmed = billing.confirm_purchase(tp.id, stripe_payment_id='pi_test')
    assert confirmed is not None
    assert confirmed.status == 'succeeded'

    # Balance should be credited
    bal = billing.get_user_balance(uid)
    assert bal >= 100
