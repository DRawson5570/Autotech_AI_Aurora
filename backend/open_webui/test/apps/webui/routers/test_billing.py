import uuid
from fastapi.testclient import TestClient
from open_webui.main import app
from open_webui.models.users import Users
from open_webui.utils.auth import create_token


def test_create_billing_portal():
    # Create a temporary user
    uid = f"test_billing_{uuid.uuid4().hex[:8]}"
    email = f"{uid}@example.com"
    Users.insert_new_user(uid, "Test Billing", email, role="user")
    user = Users.get_user_by_email(email)

    token = create_token({"id": user.id})
    # The main app should include the billing router; just use TestClient(app)
    # Ensure billing router is registered for the test by loading module from file path
    import importlib.util, importlib.machinery, pathlib
    billing_path = pathlib.Path(__file__).resolve().parents[4] / 'routers' / 'billing.py'
    spec = importlib.util.spec_from_file_location('test_billing_module', str(billing_path))
    billing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(billing)
    app.include_router(billing.router, prefix="/api/v1/billing", tags=["billing"]) 

    client = TestClient(app)

    headers = {"Authorization": f"Bearer {token}"}
    # Remove WEBUI_BASE_URL from config if present to simulate missing config key
    if hasattr(app.state.config, 'WEBUI_BASE_URL'):
        delattr(app.state.config, 'WEBUI_BASE_URL')

    resp = client.post("/api/v1/billing/portal", headers=headers)

    # Expect either success with {"url": "..."} or 400 if STRIPE_API_KEY not set
    assert resp.status_code in (200, 400)
    if resp.status_code == 200:
        assert "url" in resp.json()


def test_ensure_billing_router_registered():
    """Simulate missing billing routes and ensure the startup handler registers them."""
    # Remove any existing billing routes from the app
    app.router.routes = [r for r in app.router.routes if not getattr(r, 'path', '').startswith('/api/v1/billing')]
    assert not any(getattr(r, 'path', '').startswith('/api/v1/billing') for r in app.routes)

    # Remove the module if it's loaded so we test dynamic import
    import sys

    sys.modules.pop('open_webui.routers.billing', None)

    # Call the startup handler directly
    from open_webui.main import ensure_billing_router_registered
    import asyncio

    asyncio.get_event_loop().run_until_complete(ensure_billing_router_registered())

    # After running the startup hook, billing routes should be present
    assert any(getattr(r, 'path', '').startswith('/api/v1/billing') for r in app.routes)


def test_billing_registered_on_client_startup():
    """Ensure billing routes are present when TestClient triggers lifespan/startup."""
    # Remove any existing billing routes and module so we simulate a fresh start
    app.router.routes = [r for r in app.router.routes if not getattr(r, 'path', '').startswith('/api/v1/billing')]
    import sys

    sys.modules.pop('open_webui.routers.billing', None)

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        # After the TestClient context manager enters, lifespan startup runs
        assert any(getattr(r, 'path', '').startswith('/api/v1/billing') for r in app.routes)
