import time, uuid
from open_webui.models.billing import record_usage_event
from open_webui.internal.db import get_db
from open_webui.models.users import Users

# Create a temp user
uid = f"billing_check_{uuid.uuid4().hex[:8]}"
Users.insert_new_user(uid, "Billing Check", f"{uid}@example.com")
print('Inserted user', uid)

# Call record_usage_event
record_usage_event(uid, 'chat-test', 'msg-1', 3, 7, 10, token_source='test', ts=int(time.time()))
print('Recorded usage event')

# Query usage_event and user_token_usage
from sqlalchemy import text
with get_db() as db:
    res = db.execute(text("SELECT id, user_id, tokens_total, created_at FROM usage_event WHERE user_id = :uid"), {"uid": uid}).fetchall()
    print('usage_event rows:', res)

    res2 = db.execute(text("SELECT user_id, tokens_total, period_start FROM user_token_usage WHERE user_id = :uid"), {"uid": uid}).fetchall()
    print('user_token_usage rows:', res2)
