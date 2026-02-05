"""Smoke script: create a Stripe Checkout session for buying tokens.

Usage: PYTHONPATH=backend python scripts/stripe_checkout_smoke.py
Requires: STRIPE_API_KEY env var and running server at WEBUI_BASE_URL (or provide WEBUI_BASE_URL env var)
"""
import os
import requests

SERVER = os.environ.get('WEBUI_BASE_URL', 'http://localhost:8080')
API_BASE = SERVER.rstrip('/') + '/api/v1/billing'

TOKEN = os.environ.get('ADMIN_API_TOKEN')  # optional

if not os.environ.get('STRIPE_API_KEY'):
    print('STRIPE_API_KEY is not set - cannot create Checkout session')
    print('Set STRIPE_API_KEY to your test key and retry for a full checkout flow.')
    raise SystemExit(1)

# For this smoke script we assume an authenticated user via token or local session.
# Use a token if provided, otherwise rely on cookie/session.
headers = {}
if TOKEN:
    headers['Authorization'] = f'Bearer {TOKEN}'

payload = {'tokens': 500, 'cost': '10.00', 'currency': 'USD'}

print('Creating checkout session...')
resp = requests.post(f'{API_BASE}/user/create_checkout_session', json=payload, headers=headers)
if resp.status_code != 200:
    print('Failed:', resp.status_code, resp.text)
else:
    print('Checkout session URL:', resp.json().get('url'))
    print('Open this URL in a browser to complete the purchase.')
