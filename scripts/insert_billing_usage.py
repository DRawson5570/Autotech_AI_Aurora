#!/usr/bin/env python3
"""Insert sample billing usage events for smoke checks.

This script is meant to be run with PYTHONPATH=backend python scripts/insert_billing_usage.py
"""
import time
import os

from open_webui.models.users import Users
from open_webui.models.billing import record_usage_event, list_user_token_usage, compute_cost_for_tokens, _billing_period_for_timestamp, UsageEvent
from open_webui.internal.db import get_db


def main():
    emails = [
        'billing_check_42af3487@example.com',
        'billing_check_de87784b@example.com',
        'billing_check_2ad15198@example.com',
    ]

    now = int(time.time())

    print('Inserting usage events...')
    for i, e in enumerate(emails, start=1):
        u = Users.get_user_by_email(e)
        if not u:
            print(f'MISSING USER: {e} (skipping)')
            continue
        prompt = i * 5
        completion = i * 20
        total = prompt + completion
        record_usage_event(u.id, None, f'smoke-{i}', prompt, completion, total, token_source='test', ts=now)
        print(f'Inserted for {e}: tokens_total={total}')

    period_start, period_end = _billing_period_for_timestamp(now)
    items, total_count = list_user_token_usage(period_start, period_end, page=1, page_size=100)

    print('\nAggregates for current month:')
    for it in items:
        cost = compute_cost_for_tokens(it.tokens_total, float(os.environ.get('BILLING_TOKEN_USD_RATE','0.00002')))
        print(f'user_id={it.user_id} tokens_total={it.tokens_total} cost_usd={cost} billed={it.billed}')

    with get_db() as db:
        for e in emails:
            u = Users.get_user_by_email(e)
            if not u:
                continue
            rows = db.query(UsageEvent).filter_by(user_id=u.id).order_by(UsageEvent.created_at.desc()).limit(5).all()
            print(f"\nusage_event rows for {u.email} (count={len(rows)}):")
            for r in rows:
                print(f"  id={r.id} tokens_total={r.tokens_total} ts={r.created_at} source={r.token_source}")


if __name__ == '__main__':
    main()
