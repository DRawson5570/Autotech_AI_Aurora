from fastapi import APIRouter, Request

from open_webui.utils.auth import create_token
from open_webui.env import DATABASE_URL, DATA_DIR
from open_webui.models.users import Users
from open_webui.internal.db import get_db
from sqlalchemy import text

router = APIRouter()


@router.get("/__test/admin-token")
async def get_admin_token(request: Request):
    """Development-only helper: return a freshly signed JWT for the admin user.

    Tests can use this to set a cookie before visiting pages so SSR sees a valid session.
    """
    token = create_token(data={"id": "admin"})
    return {"token": token}


@router.get("/__test/db-debug")
async def db_debug(request: Request, email: str = ""):
    """Development-only helper: debug DB visibility for a given email.

    Returns the server's DATABASE_URL and whether the provided email exists
    according to different lookup methods inside the running server process.
    """
    if not email:
        return {"error": "missing email query parameter"}

    email_norm = email.lower()

    # Check via model helper
    user_via_model = Users.get_user_by_email(email_norm)

    # Check via direct SQL
    rows = []
    try:
        with get_db() as db:
            res = db.execute(text("SELECT id, email FROM \"user\" WHERE lower(email)=:email"), {"email": email_norm})
            rows = [dict(r) for r in res.fetchall()]
    except Exception as e:
        rows = [str(e)]

    return {
        "database_url": DATABASE_URL,
        "data_dir": str(DATA_DIR),
        "email": email_norm,
        "user_via_model": user_via_model.model_dump() if user_via_model else None,
        "rows": rows,
    }
