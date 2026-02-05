"""Reproduce and troubleshoot user greeting replacement issues.

This script loads a model's system prompt from the DB and applies
`apply_system_prompt_to_body` with different users to see if any
cross-contamination or incorrect replacement occurs.

Usage: python3 scripts/repro_greeting.py
"""

from open_webui.models.models import Models
from open_webui.models.users import Users
from open_webui.utils.payload import apply_system_prompt_to_body
import json
import threading

MODEL_ID = "autotech-ai-expert---bullet-points"


def run_for_user(email):
    user = Users.get_user_by_email(email)
    if not user:
        # Fall back to direct DB lookup if model validation path fails
        import sqlite3
        conn = sqlite3.connect('backend/data/webui.db')
        c = conn.cursor()
        c.execute("SELECT id, email, name, info FROM user WHERE email=?", (email,))
        row = c.fetchone()
        conn.close()
        if not row:
            print(f"User not found: {email}")
            return
        user = {"id": row[0], "email": row[1], "name": row[2], "info": json.loads(row[3]) if row[3] else {}}

    # Load model params directly from DB to avoid model-layer issues
    import sqlite3
    conn = sqlite3.connect('backend/data/webui.db')
    c = conn.cursor()
    c.execute("SELECT params FROM model WHERE id = ?", (MODEL_ID,))
    row = c.fetchone()
    conn.close()
    if not row:
        print(f"Model not found in DB: {MODEL_ID}")
        return
    params = json.loads(row[0]) if row[0] else {}
    system = params.get('system')

    form_data = {"model": MODEL_ID, "messages": []}

    print("---")
    if isinstance(user, dict):
        uid = user.get('id')[:8]
        uemail = user.get('email')
    else:
        uid = user.id[:8]
        uemail = user.email
    print(f"User: {uemail} ({uid})")
    print("Before system template:\n", (system or '')[:300])

    form_data_after = apply_system_prompt_to_body(system, form_data, metadata=None, user=user)

    # Show the first system message after processing
    msg = form_data_after.get("messages", [])[0]["content"]
    print("After replacement:\n", msg)


if __name__ == "__main__":
    # Sequential
    print("Sequential run:\n")
    run_for_user("wishaex@gmail.com")  # Gary
    run_for_user("bryon@gmail.com")    # Bryon

    # Concurrent
    print("\nConcurrent run:\n")
    t1 = threading.Thread(target=run_for_user, args=("wishaex@gmail.com",))
    t2 = threading.Thread(target=run_for_user, args=("bryon@gmail.com",))
    t1.start(); t2.start()
    t1.join(); t2.join()
