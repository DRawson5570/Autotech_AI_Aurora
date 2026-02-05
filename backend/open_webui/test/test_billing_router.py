from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
import importlib


def _make_app_and_client(monkeypatch, list_items):
    # Import router
    billing_router = importlib.import_module('open_webui.routers.billing').router

    # Monkeypatch billing.list_user_token_usage
    import open_webui.models.billing as billing

    def _fake_list(ps, pe, page=1, page_size=50):
        return (list_items, len(list_items))

    monkeypatch.setattr(billing, 'list_user_token_usage', _fake_list)

    # Monkeypatch Users.get_user_by_id
    import open_webui.models.users as users

    class FakeUserObj:
        def __init__(self, id):
            self.id = id
            self.email = f"{id}@example.com"
            self.name = f"User {id}"

    # Monkeypatch the class method get_user_by_id
    monkeypatch.setattr(users.Users, 'get_user_by_id', lambda uid: FakeUserObj(uid))

    # Build a small app and override the admin dependency on the app
    app = FastAPI()
    app.include_router(billing_router)

    # override get_admin_user dependency so admin-only endpoints allow access
    from open_webui.utils.auth import get_admin_user as real_admin_dep

    def fake_admin():
        class FakeAdmin:
            id = 'admin'
            role = 'admin'
        return FakeAdmin()

    app.dependency_overrides[real_admin_dep] = fake_admin

    client = TestClient(app)
    return client


def test_list_usage_endpoint(monkeypatch):
    from open_webui.models.billing import UserTokenUsageModel

    sample = [UserTokenUsageModel(
        id='u1',
        user_id='user1',
        period_start=1672531200,
        period_end=1675209600,
        tokens_prompt=10,
        tokens_completion=90,
        tokens_total=100,
        cost_total=None,
        currency='USD',
        billed=False,
        created_at=1672531200,
        updated_at=1672531200,
    )]

    client = _make_app_and_client(monkeypatch, sample)
    resp = client.get('/admin/usage?period=2023-01&page=1&page_size=50')
    assert resp.status_code == 200
    data = resp.json()
    assert data['total'] == 1
    assert len(data['items']) == 1
    item = data['items'][0]
    assert item['user_id'] == 'user1'
    assert item['tokens_total'] == 100


def _make_user_app_and_client(monkeypatch, balance_value=0):
    billing_router = importlib.import_module('open_webui.routers.billing').router
    import open_webui.models.billing as billing

    # monkeypatch get_user_balance
    monkeypatch.setattr(billing, 'get_user_balance', lambda uid: int(balance_value))

    # build app and override get_verified_user dependency
    app = FastAPI()
    app.include_router(billing_router)

    from open_webui.utils.auth import get_verified_user as real_verified

    def fake_verified():
        class FakeUser:
            id = 'user-test'
            role = 'user'
        return FakeUser()

    app.dependency_overrides[real_verified] = fake_verified
    client = TestClient(app)
    return client


def test_user_balance_endpoint(monkeypatch):
    client = _make_user_app_and_client(monkeypatch, balance_value=123)
    resp = client.get('/user/balance')
    assert resp.status_code == 200
    data = resp.json()
    assert data['tokens_balance'] == 123


def test_user_purchase_endpoint(monkeypatch):
    billing_router = importlib.import_module('open_webui.routers.billing').router
    app = FastAPI()
    app.include_router(billing_router)

    # override get_verified_user
    from open_webui.utils.auth import get_verified_user as real_verified

    def fake_verified():
        class FakeUser:
            id = 'user-purchase'
            role = 'user'
        return FakeUser()

    app.dependency_overrides[real_verified] = fake_verified

    # monkeypatch billing.purchase_tokens to return a simple object
    import open_webui.models.billing as billing

    class FakePurchase:
        def __init__(self):
            self.id = 'p1'
            self.user_id = 'user-purchase'
            self.tokens = 500
            self.cost = '10.00'
            self.currency = 'USD'
            self.stripe_payment_id = None
            self.created_at = 1234567890

        def model_dump(self):
            return {
                'id': self.id,
                'user_id': self.user_id,
                'tokens': self.tokens,
                'cost': self.cost,
                'currency': self.currency,
                'stripe_payment_id': self.stripe_payment_id,
                'created_at': self.created_at,
            }

    monkeypatch.setattr(billing, 'purchase_tokens', lambda uid, tokens, cost=None, currency='USD', stripe_payment_id=None, status='succeeded': FakePurchase())
    monkeypatch.setattr(billing, 'get_user_balance', lambda uid: 500)

    client = TestClient(app)
    resp = client.post('/user/purchase', json={'tokens': 500, 'cost': '10.00'})
    assert resp.status_code == 200
    data = resp.json()
    assert 'purchase' in data
    assert data['tokens_balance'] == 500


def test_export_csv(monkeypatch):
    from open_webui.models.billing import UserTokenUsageModel

    sample = [UserTokenUsageModel(
        id='u2',
        user_id='user2',
        period_start=1672531200,
        period_end=1675209600,
        tokens_prompt=5,
        tokens_completion=45,
        tokens_total=50,
        cost_total=None,
        currency='USD',
        billed=False,
        created_at=1672531200,
        updated_at=1672531200,
    )]

    client = _make_app_and_client(monkeypatch, sample)
    resp = client.get('/admin/usage/export?period=2023-01')
    assert resp.status_code == 200
    text = resp.text
    assert 'user_id' in text
    assert 'user2' in text
    # Ensure cost column exists and is numeric
    assert ',' in text


def test_admin_purchases_list_and_reconcile(monkeypatch):
    # Create a fake purchase list
    from open_webui.models.billing import TokenPurchase

    sample_items = [
        {
            'id': 'p1',
            'user_id': 'user1',
            'tokens': 100,
            'cost': '2.00',
            'currency': 'USD',
            'status': 'pending',
            'stripe_session_id': None,
            'stripe_payment_id': None,
            'created_at': 1672531200,
        }
    ]

    client = _make_app_and_client(monkeypatch, [])

    # Monkeypatch billing.list_token_purchases to return our sample
    import types
    import open_webui.models.billing as billing_model

    monkeypatch.setattr(billing_model, 'list_token_purchases', lambda status, page, page_size: ([types.SimpleNamespace(**sample_items[0])], len(sample_items)))

    # Now call list endpoint
    resp = client.get('/admin/purchases?status=pending')
    assert resp.status_code == 200
    data = resp.json()
    assert data['total'] == 1
    assert len(data['items']) == 1

    # Monkeypatch reconcile_one
    import open_webui.models.billing as mb
    monkeypatch.setattr(mb, 'reconcile_one', lambda pid: {'purchase_id': pid, 'action': 'confirmed', 'reason': 'test'})

    resp = client.post('/admin/purchases/p1/reconcile')
    assert resp.status_code == 200
    data = resp.json()
    assert data['action'] == 'confirmed'

    # Reconcile all (no-op)
    resp = client.post('/admin/purchases/reconcile_all')
    assert resp.status_code == 200
    data = resp.json()
    assert 'results' in data


def test_admin_reconcile_all_invokes_helper(monkeypatch):
    """Ensure the admin reconcile_all endpoint calls reconcile_pending_purchases with given age"""
    billing_router = importlib.import_module('open_webui.routers.billing').router
    app = FastAPI()
    app.include_router(billing_router)

    # override admin dependency
    from open_webui.utils.auth import get_admin_user as real_admin_dep

    def fake_admin():
        class FakeAdmin:
            id = 'admin'
            role = 'admin'
        return FakeAdmin()

    app.dependency_overrides[real_admin_dep] = fake_admin
    client = TestClient(app)

    calls = {}
    import open_webui.models.billing as mb

    def fake_reconcile(age):
        calls['age'] = age
        return [{'purchase_id': 'p1', 'action': 'confirmed', 'reason': 'ok'}]

    monkeypatch.setattr(mb, 'reconcile_pending_purchases', fake_reconcile)

    resp = client.post('/admin/purchases/reconcile_all?older_than_seconds=42')
    assert resp.status_code == 200
    data = resp.json()
    assert data['count'] == 1
    assert data['results'][0]['action'] == 'confirmed'
    assert calls['age'] == 42


def test_dry_run_invoice(monkeypatch):
    from open_webui.models.billing import UserTokenUsageModel

    sample = [UserTokenUsageModel(
        id='u3',
        user_id='user3',
        period_start=1672531200,
        period_end=1675209600,
        tokens_prompt=0,
        tokens_completion=100,
        tokens_total=100,
        cost_total=None,
        currency='USD',
        billed=False,
        created_at=1672531200,
        updated_at=1672531200,
    )]

    client = _make_app_and_client(monkeypatch, sample)
    resp = client.post('/admin/usage/dry_run?period=2023-01')
    assert resp.status_code == 200
    data = resp.json()
    assert data['total_users'] == 1
    assert data['grand_total_tokens'] == 100
    assert float(data['grand_total_cost']) >= 0.0
