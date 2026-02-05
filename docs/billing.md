# Billing & Token System

This document describes the tiered subscription billing system and token management.

## Overview

Autotech AI uses a **tiered subscription model** with local billing:
- Users select a plan (Starter/Pro/Enterprise)
- Each plan includes monthly tokens at a fixed price
- Overage is charged at $0.02 per 1K tokens
- A daily cron job charges users' stored payment methods via Stripe PaymentIntent

## Subscription Tiers

| Tier | Monthly Price | Tokens Included | Overage Rate |
|------|--------------|-----------------|--------------|
| Starter | $20 | 400,000 | $0.02/1K |
| Pro | $30 | 800,000 | $0.02/1K |
| Enterprise | $40 | 1,500,000 | $0.02/1K |

Special cases:
- **Trial group** — Users in the "Trial" group are exempt from billing; they use granted tokens until depleted
- **No Plan** — Users can cancel subscription; they keep remaining tokens but get no monthly allocation

## Environment Variables

```bash
# Required
STRIPE_API_KEY           # Stripe secret key for charges

# Optional
STRIPE_WEBHOOK_SECRET    # Verify webhook signatures (recommended)
WEBUI_BASE_URL           # Public URL for Stripe redirects
```

## User Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/billing/user/billing-status` | Get subscription status, tier, billing dates |
| `POST /api/v1/billing/user/subscription` | Set/update subscription tier |
| `POST /api/v1/billing/portal` | Open Stripe Checkout to add/update payment method |
| `GET /api/v1/billing/user/invoices` | Get invoice history |
| `GET /api/v1/billing/user/balance` | Get current token balance |
| `GET /api/v1/billing/user/usage` | Get usage summary for current period |

## Admin Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/billing/admin/billing/run` | Manually trigger billing run |
| `GET /api/v1/billing/admin/billing/pending` | View pending/failed invoices |
| `GET /api/v1/billing/admin/billing/users-to-bill` | Preview who would be billed |
| `POST /api/v1/billing/admin/billing/charge-invoice/{id}` | Retry a failed invoice |
| `POST /api/v1/billing/admin/trial_tokens` | Grant trial tokens to user |
| `POST /api/v1/billing/admin/token_pricing` | Update token pricing |

## Billing Flow

### 1. User Setup
1. User opens Settings → Token Dashboard
2. Selects a tier (auto-saves)
3. Clicks "Set Up Payment Method" → Stripe Checkout (setup mode)
4. Returns with payment method attached to Stripe Customer

### 2. Monthly Billing Cycle
1. **Cron job runs daily** (recommended: 2am)
2. Finds users whose `current_period_end` has passed
3. Creates invoice with: base price + overage charges
4. Charges stored payment method via `stripe.PaymentIntent.create()`
5. On success: advances user to next billing period
6. On failure: marks invoice as failed for admin review

### 3. Invoice Statuses
- `pending` — Created, not yet charged
- `paid` — Successfully charged
- `failed` — Charge failed (will retry on next run or manual retry)

## Local Billing (Cron Job)

The billing system runs locally via cron, NOT through Stripe Subscriptions.

### Production Setup (poweredge1)

```bash
# Add to crontab -e:
0 2 * * * cd /home/drawson/autotech_ai && /path/to/python scripts/run_billing.py >> /var/log/autotech_billing.log 2>&1
```

### Manual Billing Run

```bash
# Via script
cd /home/drawson/autotech_ai
STRIPE_API_KEY=sk_live_xxx python scripts/run_billing.py

# Via API (admin only)
curl -X POST https://automotive.aurora-sentient.net/api/v1/billing/admin/billing/run \
  -H "Authorization: Bearer $TOKEN"
```

### Development

No cron job needed on dev. Test billing manually:
```bash
# Check who would be billed
curl http://localhost:8080/api/v1/billing/admin/billing/users-to-bill

# Run billing manually
curl -X POST http://localhost:8080/api/v1/billing/admin/billing/run
```

## Database Tables

### UserSubscription
Tracks user's current tier and billing period:
- `tier_id`, `status`, `current_period_start`, `current_period_end`
- `stripe_customer_id`, `stripe_subscription_id` (legacy)

### BillingInvoice
Records each billing cycle:
- `period_start`, `period_end`, `tier_id`, `tier_name`
- `base_price_cents`, `tokens_included`, `tokens_used`, `tokens_overage`
- `overage_cost_cents`, `total_amount_cents`
- `status` (pending/paid/failed), `stripe_payment_intent_id`
- `retry_count`, `failure_reason`

### UserTokenBalance
Current token balance for each user.

### TokenUsage
Per-request token consumption logs.

## Legacy Token Purchases

The old token purchase system (buy X tokens for $Y) still exists for one-off purchases:

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/billing/user/create_checkout_session` | Create Stripe Checkout for token purchase |
| `POST /api/v1/billing/webhook` | Stripe webhook for purchase confirmation |
| `GET /api/v1/billing/admin/purchases` | List token purchases |

## Testing

- Use Stripe test mode keys (`sk_test_xxx`)
- Create test users with different tiers
- Fast-forward billing periods by manually updating `current_period_end`
- Trigger billing run via admin API

## Troubleshooting

### User can't see Token Dashboard
- Check user is verified (logged in)
- Check user is not in "Trial" group (trial users see simplified view)

### Payment method not attaching
- Verify `STRIPE_API_KEY` is set
- Check Stripe Dashboard for customer records
- Ensure Checkout success_url includes `?settings=account`

### Billing not running
- Check cron job is installed and running
- Verify `STRIPE_API_KEY` in cron environment
- Check `/var/log/autotech_billing.log` for errors
- Try manual run via admin API
