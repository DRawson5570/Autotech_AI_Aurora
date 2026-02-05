import os
import json
import logging
import time
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from open_webui.utils.auth import get_verified_user, get_admin_user
from open_webui.models.users import Users

log = logging.getLogger(__name__)
router = APIRouter()


def _is_localhost_url(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed = urlparse(str(value))
        host = (parsed.hostname or "").lower()
        return host in {"localhost", "127.0.0.1", "0.0.0.0"}
    except Exception:
        return False


def _normalize_base_url(value: str) -> str:
    # We build query-string URLs like f"{base}/?foo=bar"; ensure base has no trailing slash.
    return str(value).strip().rstrip("/")


def _get_public_webui_base_url(request: Request) -> str:
    """Best-effort public base URL for links/Stripe redirects.

    Order of precedence:
    - Explicit env/config values (unless they point at localhost)
    - Admin-configured WEBUI_URL (public URL)
    - Reverse-proxy forwarded headers / request host
    - Final fallback to localhost
    """

    # Prefer explicitly configured base URL, but ignore localhost defaults on production.
    candidates: list[str | None] = [
        os.environ.get("WEBUI_BASE_URL"),
        getattr(getattr(request.app.state, "config", None), "WEBUI_BASE_URL", None),
        # Admin setting used elsewhere for public links; reuse as a safe fallback.
        getattr(getattr(request.app.state, "config", None), "WEBUI_URL", None),
    ]
    for candidate in candidates:
        if candidate and not _is_localhost_url(candidate):
            return _normalize_base_url(candidate)

    # Derive from request headers (supports reverse proxies).
    xf_host = request.headers.get("x-forwarded-host")
    host = xf_host or request.headers.get("host")
    xf_proto = request.headers.get("x-forwarded-proto")
    scheme = (xf_proto or request.url.scheme or "http").split(",")[0].strip()
    if host:
        return _normalize_base_url(f"{scheme}://{host.split(',')[0].strip()}")

    return "http://localhost:8080"


def _get_token_usd_rate_from_request(request: Request) -> float:
    # Use DB-backed persistent config, falling back to env default.
    try:
        rate = float(getattr(request.app.state.config, "BILLING_TOKEN_USD_RATE", 0.00002))
    except Exception:
        rate = float(os.environ.get("BILLING_TOKEN_USD_RATE", "0.00002"))
    return rate


def _usd_amount_cents_for_tokens(tokens: int, token_usd_rate: float) -> int:
    # Stripe expects an integer in cents.
    # Use Decimal to avoid floating point surprises.
    amount = (Decimal(int(tokens)) * Decimal(str(token_usd_rate)) * Decimal("100")).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    cents = int(amount)
    # Avoid a 0-cent charge (Stripe will reject).
    return max(1, cents)


class TokenPricingForm(BaseModel):
    token_usd_rate: float


@router.post("/admin/trial_tokens")
async def admin_grant_trial_tokens(payload: dict, admin=Depends(get_admin_user)):
    """Admin endpoint: grant free trial tokens to a user.

    Accepts either {user_id, tokens} or {email, tokens}. Credits balance immediately.
    """
    from open_webui.models import billing

    user_id = payload.get("user_id")
    email = payload.get("email")
    tokens = payload.get("tokens")

    if user_id is None and email is None:
        raise HTTPException(status_code=400, detail="Missing user_id or email")

    try:
        tokens_int = int(tokens)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tokens")

    if tokens_int <= 0:
        raise HTTPException(status_code=400, detail="Tokens must be > 0")

    # Simple guardrail to prevent accidental huge grants
    if tokens_int > 10_000_000:
        raise HTTPException(status_code=400, detail="Tokens too large")

    if not user_id and email:
        email_norm = str(email).strip()
        u = Users.get_user_by_email(email_norm)
        if not u and email_norm.lower() != email_norm:
            u = Users.get_user_by_email(email_norm.lower())
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        user_id = u.id

    u = Users.get_user_by_id(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        tp = billing.purchase_tokens(
            user_id=user_id,
            tokens=tokens_int,
            cost="0",
            currency="USD",
            status="succeeded",
        )
        new_balance = billing.get_user_balance(user_id)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Failed to grant trial tokens")
        raise HTTPException(status_code=500, detail="Failed to grant trial tokens") from e

    return {
        "purchase_id": tp.id,
        "user_id": user_id,
        "email": u.email,
        "name": u.name,
        "granted_tokens": tokens_int,
        "tokens_balance": int(new_balance),
    }


@router.get("/admin/usage")
async def admin_list_usage(
    # NOTE: keep signature args aligned with spaces for readability.
    request: Request,
    period: str | None = None,
    page: int = 1,
    page_size: int = 50,
    admin=Depends(get_admin_user),
):
    """Admin endpoint: list per-user monthly aggregates for a given period (YYYY-MM)."""
    import datetime
    from open_webui.models import billing

    # Parse period YYYY-MM; default to current UTC month
    if not period:
        now = datetime.datetime.utcnow()
        period = f"{now.year:04d}-{now.month:02d}"

    try:
        year, month = [int(p) for p in period.split("-")]
        start = datetime.datetime(year, month, 1)
        if month == 12:
            end = datetime.datetime(year + 1, 1, 1)
        else:
            end = datetime.datetime(year, month + 1, 1)
        period_start = int(start.timestamp())
        period_end = int(end.timestamp())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid period format; expected YYYY-MM")

    rate = _get_token_usd_rate_from_request(request)

    # Retrieve items
    items, total = billing.list_user_token_usage(period_start, period_end, page=page, page_size=page_size)

    # Enrich with user info
    results = []
    for item in items:
        u = Users.get_user_by_id(item.user_id)
        # This is the user's prepaid token balance (if they are enrolled).
        try:
            if billing.has_user_balance_record(item.user_id):
                balance = int(billing.get_user_balance(item.user_id))
            else:
                balance = None
        except Exception:
            balance = None

        # Cost is computed at display time from current configured rate.
        computed_cost = billing.compute_cost_for_tokens(item.tokens_total, rate)
        results.append(
            {
                "user_id": item.user_id,
                "email": u.email if u else None,
                "name": u.name if u else None,
                "period_start": item.period_start,
                "period_end": item.period_end,
                "tokens_prompt": item.tokens_prompt,
                "tokens_completion": item.tokens_completion,
                "tokens_total": item.tokens_total,
                "cost_total": computed_cost,
                "currency": item.currency,
                "billed": item.billed,
                "tokens_balance": balance,
            }
        )

    return {"items": results, "total": total, "page": page, "page_size": page_size, "rate": rate}


@router.get("/admin/token_pricing")
async def admin_get_token_pricing(request: Request, admin=Depends(get_admin_user)):
    rate = _get_token_usd_rate_from_request(request)
    return {"token_usd_rate": float(rate)}


@router.post("/admin/token_pricing")
async def admin_update_token_pricing(request: Request, form_data: TokenPricingForm, admin=Depends(get_admin_user)):
    try:
        rate = float(form_data.token_usd_rate)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid token_usd_rate")

    if not (rate > 0):
        raise HTTPException(status_code=400, detail="token_usd_rate must be > 0")
    # Guardrail: prevent obvious misconfiguration (e.g., dollars-per-token by accident)
    if rate > 1:
        raise HTTPException(status_code=400, detail="token_usd_rate is unexpectedly large")

    # Persist to DB-backed config
    request.app.state.config.BILLING_TOKEN_USD_RATE = rate
    return {"token_usd_rate": float(rate)}


@router.get("/admin/purchases")
async def admin_list_purchases(status: str | None = None, page: int = 1, page_size: int = 50, admin=Depends(get_admin_user)):
    """List token purchases with optional status filter (pending|succeeded|failed)."""
    from open_webui.models import billing

    items, total = billing.list_token_purchases(status=status, page=page, page_size=page_size)

    results = []
    for it in items:
        u = Users.get_user_by_id(it.user_id)
        results.append({
            "id": it.id,
            "user_id": it.user_id,
            "email": u.email if u else None,
            "name": u.name if u else None,
            "tokens": it.tokens,
            "cost": it.cost,
            "currency": it.currency,
            "status": it.status,
            "stripe_session_id": it.stripe_session_id,
            "stripe_payment_id": it.stripe_payment_id,
            "created_at": it.created_at,
        })

    return {"items": results, "total": total, "page": page, "page_size": page_size}


@router.post("/admin/purchases/{purchase_id}/reconcile")
async def admin_reconcile_purchase(purchase_id: str, admin=Depends(get_admin_user)):
    """Admin endpoint: reconcile a single purchase (idempotent)."""
    from open_webui.models import billing

    res = billing.reconcile_one(purchase_id)
    return res


@router.get("/admin/subscriptions")
async def admin_list_subscriptions(admin=Depends(get_admin_user)):
    """Admin endpoint: list all user subscriptions with plan details."""
    from open_webui.models import billing
    from open_webui.models.users import Users
    import datetime
    
    with billing.get_db() as db:
        subs = db.query(billing.UserSubscription).all()
        
        result = []
        for sub in subs:
            # Get user info
            user = Users.get_user_by_id(sub.user_id)
            if not user:
                continue  # Skip orphaned subscriptions
            
            # Get tier info
            tier_info = billing.Billing.get_tier_info(sub.tier_id) or {}
            tier_name = tier_info.get("name", sub.tier_id or "None")
            tokens_included = tier_info.get("tokens_included", 0)
            
            # Get current token balance
            bal = db.query(billing.UserTokenBalance).filter_by(user_id=sub.user_id).first()
            token_balance = int(bal.tokens_balance) if bal else 0
            
            # Calculate tokens used this period
            tokens_used = tokens_included - token_balance if token_balance >= 0 else tokens_included + abs(token_balance)
            if tokens_used < 0:
                tokens_used = 0
            
            # Format renew date
            renew_date = None
            if sub.current_period_end:
                renew_date = datetime.datetime.utcfromtimestamp(sub.current_period_end).strftime("%Y-%m-%d")
            
            result.append({
                "user_id": sub.user_id,
                "name": user.name,
                "email": user.email,
                "tier_id": sub.tier_id,
                "tier_name": tier_name,
                "tokens_included": tokens_included,
                "tokens_used": tokens_used,
                "token_balance": token_balance,
                "renew_date": renew_date,
                "status": sub.status,
                "pending_tier_id": sub.pending_tier_id,
            })
        
        return {"subscriptions": result}


@router.post("/admin/purchases/reconcile_all")
async def admin_reconcile_all(older_than_seconds: int | None = None, admin=Depends(get_admin_user)):
    """Admin endpoint: reconcile all pending purchases older than the given age (seconds).

    Returns the list of reconciliation results.
    """
    from open_webui.models import billing

    age = int(older_than_seconds) if older_than_seconds is not None else 3600
    res = billing.reconcile_pending_purchases(age)
    return {"results": res, "count": len(res)}


@router.get("/admin/usage/export")
async def admin_export_usage_csv(request: Request, period: str | None = None, admin=Depends(get_admin_user)):
    """Admin endpoint: export CSV for the given period (YYYY-MM). Includes an USD estimate using env var BILLING_TOKEN_USD_RATE."""
    import csv
    import io
    import datetime
    from fastapi.responses import StreamingResponse
    from open_webui.models import billing

    # Parse period
    if not period:
        now = datetime.datetime.utcnow()
        period = f"{now.year:04d}-{now.month:02d}"

    try:
        year, month = [int(p) for p in period.split("-")]
        start = datetime.datetime(year, month, 1)
        if month == 12:
            end = datetime.datetime(year + 1, 1, 1)
        else:
            end = datetime.datetime(year, month + 1, 1)
        period_start = int(start.timestamp())
        period_end = int(end.timestamp())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid period format; expected YYYY-MM")

    rate = _get_token_usd_rate_from_request(request)

    # Fetch all items (no pagination)
    items, _ = billing.list_user_token_usage(period_start, period_end, page=1, page_size=10000)

    # Build CSV in memory
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["user_id", "email", "name", "period_start", "period_end", "tokens_prompt", "tokens_completion", "tokens_total", "cost_usd", "currency", "billed"])

    for item in items:
        u = Users.get_user_by_id(item.user_id)
        cost = billing.compute_cost_for_tokens(item.tokens_total, rate)
        writer.writerow([
            item.user_id,
            u.email if u else "",
            u.name if u else "",
            item.period_start,
            item.period_end,
            item.tokens_prompt,
            item.tokens_completion,
            item.tokens_total,
            cost,
            item.currency,
            item.billed,
        ])

    buffer.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=usage_{period}.csv"}
    return StreamingResponse(buffer, media_type="text/csv", headers=headers)


@router.post("/admin/usage/dry_run")
async def admin_dry_run_invoice(request: Request, period: str | None = None, rate: float | None = None, admin=Depends(get_admin_user)):
    """Admin endpoint: dry-run invoice calculation for a given period (YYYY-MM).

    Returns per-user token totals and an estimated USD amount using the configured rate or provided override.
    """
    import datetime
    from open_webui.models import billing

    # Parse period YYYY-MM; default to current UTC month
    if not period:
        now = datetime.datetime.utcnow()
        period = f"{now.year:04d}-{now.month:02d}"

    try:
        year, month = [int(p) for p in period.split("-")]
        start = datetime.datetime(year, month, 1)
        if month == 12:
            end = datetime.datetime(year + 1, 1, 1)
        else:
            end = datetime.datetime(year, month + 1, 1)
        period_start = int(start.timestamp())
        period_end = int(end.timestamp())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid period format; expected YYYY-MM")

    # rate override or persistent config default
    rate_to_use = float(rate) if rate is not None else _get_token_usd_rate_from_request(request)

    log.info(f"Admin dry-run invoice requested for period={period} by admin user (rate={rate_to_use})")

    # Fetch all items
    items, total = billing.list_user_token_usage(period_start, period_end, page=1, page_size=10000)

    results = []
    grand_total_tokens = 0
    grand_total_cost = 0.0
    for item in items:
        cost = float(billing.compute_cost_for_tokens(item.tokens_total, rate_to_use))
        grand_total_tokens += int(item.tokens_total or 0)
        grand_total_cost += cost
        u = Users.get_user_by_id(item.user_id)
        results.append(
            {
                "user_id": item.user_id,
                "email": u.email if u else None,
                "name": u.name if u else None,
                "tokens_total": item.tokens_total,
                "cost_usd": f"{cost:.6f}",
            }
        )

    return {"items": results, "total_users": len(results), "grand_total_tokens": grand_total_tokens, "grand_total_cost": f"{grand_total_cost:.6f}", "rate": rate_to_use}


@router.post("/portal")
async def create_billing_portal(request: Request, user=Depends(get_verified_user)):
    """Create a Stripe Checkout session in setup mode to collect payment method.

    This uses Checkout Session with mode='setup' which properly attaches payment methods
    to the customer, unlike the billing portal which requires existing subscriptions.
    
    Requires environment variable STRIPE_API_KEY.
    """
    stripe_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_key:
        raise HTTPException(status_code=400, detail="Stripe is not configured on the server.")

    import stripe

    stripe.api_key = stripe_key

    # Ensure we have a Stripe customer id for the user
    u = Users.get_user_by_id(user.id)
    info = u.info or {}
    customer_id = info.get("stripe_customer_id")

    try:
        if not customer_id:
            # Create customer
            cust = stripe.Customer.create(email=u.email, metadata={"user_id": u.id})
            customer_id = cust.id
            # Persist customer id in user.info
            info["stripe_customer_id"] = customer_id
            Users.update_user_by_id(user.id, {"info": info})

        # Build return URL - go to settings/account page
        base_url = os.environ.get("STRIPE_RETURN_URL")
        if not base_url or _is_localhost_url(base_url):
            base_url = _get_public_webui_base_url(request)
        
        # Return to settings page with account tab selected
        success_url = f"{base_url}/?settings=account"
        cancel_url = f"{base_url}/?settings=account"

        # Use Checkout Session in setup mode to collect payment method
        # This properly attaches the payment method to the customer
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="setup",
            payment_method_types=["card"],
            success_url=success_url,
            cancel_url=cancel_url,
        )

        return {"url": session.url}
    except stripe.error.StripeError as e:
        log.exception("Stripe error creating checkout session")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        log.exception("Error creating checkout session")
        raise HTTPException(status_code=500, detail=str(e))


class SubscriptionCheckoutForm(BaseModel):
    tier_id: str


@router.post("/user/subscription/checkout")
async def create_subscription_checkout(
    request: Request, 
    form_data: SubscriptionCheckoutForm, 
    user=Depends(get_verified_user)
):
    """Create a Stripe Checkout session to set up billing and charge first month.
    
    This is for NEW subscribers who don't have a payment method yet.
    It will:
    1. Collect payment method
    2. Charge the first month of the selected tier
    3. On success callback, activate subscription and grant tokens
    """
    from open_webui.models import billing
    import stripe
    
    stripe_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_key:
        raise HTTPException(status_code=400, detail="Stripe is not configured on the server.")
    
    stripe.api_key = stripe_key
    
    # Validate tier
    tier_info = billing.Billing.get_tier_info(form_data.tier_id)
    if not tier_info:
        raise HTTPException(status_code=400, detail=f"Invalid tier_id: {form_data.tier_id}")
    
    if form_data.tier_id == "none":
        raise HTTPException(status_code=400, detail="Cannot checkout for 'none' tier")
    
    # Get or create Stripe customer
    u = Users.get_user_by_id(user.id)
    info = u.info or {}
    customer_id = info.get("stripe_customer_id")
    
    try:
        if not customer_id:
            cust = stripe.Customer.create(email=u.email, metadata={"user_id": u.id})
            customer_id = cust.id
            info["stripe_customer_id"] = customer_id
            Users.update_user_by_id(user.id, {"info": info})
        
        # Build return URL
        base_url = os.environ.get("STRIPE_RETURN_URL")
        if not base_url or _is_localhost_url(base_url):
            base_url = _get_public_webui_base_url(request)
        
        # Success URL includes session_id for confirmation
        success_url = f"{base_url}/billing/subscription/confirm?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/?settings=account"
        
        # Create Checkout Session in payment mode for first month
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="payment",
            payment_method_types=["card"],
            payment_method_options={
                "card": {
                    "setup_future_usage": "off_session",
                },
            },
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": tier_info["monthly_price_cents"],
                    "product_data": {
                        "name": f"Autotech AI - {tier_info['name']} Plan",
                        "description": f"First month - {tier_info['tokens_included']:,} tokens included",
                    },
                },
                "quantity": 1,
            }],
            payment_intent_data={
                "metadata": {
                    "user_id": user.id,
                    "tier_id": form_data.tier_id,
                    "type": "subscription_first_month",
                },
            },
            metadata={
                "user_id": user.id,
                "tier_id": form_data.tier_id,
                "type": "subscription_first_month",
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )
        
        return {"url": session.url, "session_id": session.id}
        
    except stripe.error.StripeError as e:
        log.exception("Stripe error creating subscription checkout")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        log.exception("Error creating subscription checkout")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/subscription/confirm")
async def confirm_subscription_checkout(
    session_id: str,
    user=Depends(get_verified_user)
):
    """Confirm subscription checkout and activate the subscription.
    
    Called after successful Stripe Checkout payment for first month.
    """
    from open_webui.models import billing
    import stripe
    import datetime
    
    stripe_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_key:
        raise HTTPException(status_code=400, detail="Stripe is not configured.")
    
    stripe.api_key = stripe_key
    
    try:
        # Retrieve the checkout session
        session = stripe.checkout.Session.retrieve(session_id)
        
        if session.payment_status != "paid":
            raise HTTPException(status_code=400, detail="Payment not completed")
        
        # Verify this session belongs to this user
        if session.metadata.get("user_id") != user.id:
            raise HTTPException(status_code=403, detail="Session does not belong to this user")
        
        tier_id = session.metadata.get("tier_id")
        if not tier_id:
            raise HTTPException(status_code=400, detail="Missing tier_id in session")
        
        tier_info = billing.Billing.get_tier_info(tier_id)
        if not tier_info:
            raise HTTPException(status_code=400, detail=f"Invalid tier_id: {tier_id}")
        
        # Calculate billing period (1 month from now)
        now = int(time.time())
        dt = datetime.datetime.utcfromtimestamp(now)
        if dt.month == 12:
            next_month = datetime.datetime(dt.year + 1, 1, dt.day, dt.hour, dt.minute, dt.second)
        else:
            try:
                next_month = datetime.datetime(dt.year, dt.month + 1, dt.day, dt.hour, dt.minute, dt.second)
            except ValueError:
                import calendar
                last_day = calendar.monthrange(dt.year, dt.month + 1)[1]
                next_month = datetime.datetime(dt.year, dt.month + 1, last_day, dt.hour, dt.minute, dt.second)
        
        period_end = int(next_month.timestamp())
        
        # Activate subscription with billing period
        sub = billing.Billing.set_user_subscription(
            user_id=user.id,
            tier_id=tier_id,
            period_start=now,
            period_end=period_end,
            status="active"
        )
        
        # Grant tokens for the month
        tokens_granted = billing.Billing.grant_monthly_tokens(user.id, tier_id)
        
        # Create invoice record for this payment
        payment_intent = stripe.PaymentIntent.retrieve(session.payment_intent)
        
        with billing.get_db() as db:
            invoice = billing.BillingInvoice(
                id=str(billing.uuid.uuid4()),
                user_id=user.id,
                period_start=now,
                period_end=period_end,
                tier_id=tier_id,
                tier_name=tier_info["name"],
                base_price_cents=tier_info["monthly_price_cents"],
                tokens_included=tier_info["tokens_included"],
                tokens_used=0,
                tokens_overage=0,
                overage_cost_cents=0,
                total_amount_cents=tier_info["monthly_price_cents"],
                status="paid",
                stripe_payment_intent_id=session.payment_intent,
                stripe_charge_id=payment_intent.latest_charge if payment_intent.latest_charge else None,
                created_at=now,
                updated_at=now,
                paid_at=now,
            )
            db.add(invoice)
            db.commit()
        
        return {
            "success": True,
            "subscription": sub.model_dump(),
            "tier": tier_info,
            "tokens_granted": tokens_granted,
            "message": f"Welcome to {tier_info['name']}! {tokens_granted:,} tokens have been added to your account.",
        }
        
    except stripe.error.StripeError as e:
        log.exception("Stripe error confirming subscription")
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Error confirming subscription")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/token_pricing")
async def user_get_token_pricing(request: Request, user=Depends(get_verified_user)):
    """Return the configured USD-per-token rate and available token bundles.

    This is safe to expose to authenticated users and is used by the UI
    to display accurate pricing for token bundles.
    """
    from open_webui.env import BILLING_TOKEN_BUNDLES

    rate = _get_token_usd_rate_from_request(request)
    return {"token_usd_rate": float(rate), "token_bundles": BILLING_TOKEN_BUNDLES}


@router.get("/public/token_pricing")
async def public_get_token_pricing(request: Request):
    """Public token pricing endpoint.

    This is used by the UI to display accurate pricing labels even when an auth token
    isn't immediately available (e.g., during session initialization).
    """
    from open_webui.env import BILLING_TOKEN_BUNDLES

    rate = _get_token_usd_rate_from_request(request)
    return {"token_usd_rate": float(rate), "token_bundles": BILLING_TOKEN_BUNDLES}


@router.get("/user/balance")
async def user_balance(user=Depends(get_verified_user)):
    """Return current user's token balance."""
    from open_webui.models import billing

    bal = billing.get_user_balance(user.id)
    return {"tokens_balance": int(bal)}


@router.get("/user/overage-status")
async def user_overage_status(user=Depends(get_verified_user)):
    """Check if user is in overage and get upgrade recommendation."""
    from open_webui.models.billing import Billing
    
    status = Billing.check_overage_status(user.id)
    if not status:
        return {"in_overage": False}
    return status


@router.get("/user/auto_renew")
async def user_get_auto_renew(user=Depends(get_verified_user)):
    """Return current user's auto-renew settings."""
    from open_webui.models import billing

    settings = billing.get_auto_renew_settings(user.id)
    return settings


class AutoRenewForm(BaseModel):
    enabled: bool
    tokens: int = 0


@router.post("/user/auto_renew")
async def user_set_auto_renew(form_data: AutoRenewForm, user=Depends(get_verified_user)):
    """Update user's auto-renew settings. Requires a saved payment method (Stripe customer with default payment method)."""
    from open_webui.models import billing

    # Validate tokens is a valid bundle amount if enabling
    if form_data.enabled:
        if form_data.tokens <= 0:
            raise HTTPException(status_code=400, detail="Must specify a positive token amount for auto-renew")

        # Check if user has a saved payment method
        u = Users.get_user_by_id(user.id)
        info = u.info or {}
        customer_id = info.get("stripe_customer_id")

        if not customer_id:
            raise HTTPException(
                status_code=400,
                detail="No payment method on file. Please make a purchase first to save your payment method."
            )

        # Verify customer has a default payment method
        stripe_key = os.environ.get("STRIPE_API_KEY")
        if stripe_key:
            try:
                import stripe
                stripe.api_key = stripe_key
                customer = stripe.Customer.retrieve(customer_id)
                default_pm = customer.get("invoice_settings", {}).get("default_payment_method")
                if not default_pm:
                    # Check for any attached payment methods
                    pms = stripe.PaymentMethod.list(customer=customer_id, type="card", limit=1)
                    if not pms.data:
                        raise HTTPException(
                            status_code=400,
                            detail="No payment method on file. Please add a card via Manage Billing first."
                        )
            except stripe.error.StripeError as e:
                log.exception("Stripe error checking payment method")
                raise HTTPException(status_code=500, detail=f"Payment verification failed: {str(e)}")

    settings = billing.set_auto_renew_settings(user.id, form_data.enabled, form_data.tokens)
    return settings


# ===== TIERED BILLING ENDPOINTS =====

def _is_user_in_trial_group(user_id: str) -> bool:
    """Check if user is a member of a 'Trial' group (case-insensitive)."""
    from open_webui.models.groups import Groups
    
    try:
        user_groups = Groups.get_groups_by_member_id(user_id)
        for group in user_groups:
            if group.name.lower() == "trial":
                return True
        return False
    except Exception as e:
        log.warning(f"Error checking trial group membership: {e}")
        return False


@router.get("/user/billing-status")
async def get_user_billing_status(user=Depends(get_verified_user)):
    """Check if user has billing set up (Stripe customer with payment method).
    
    Users in the 'Trial' group are automatically exempted from billing requirements.
    """
    import stripe
    
    stripe_key = os.environ.get("STRIPE_API_KEY")
    
    # Check if user is in Trial group - exempt from billing requirements
    if _is_user_in_trial_group(user.id):
        return {
            "has_billing_setup": True,
            "has_payment_method": True,
            "stripe_configured": True,
            "is_trial": True,
            "message": "Trial account - billing not required",
        }
    
    if not stripe_key:
        # No Stripe configured - allow tier selection without payment
        return {
            "has_billing_setup": True,
            "has_payment_method": True,
            "stripe_configured": False,
            "is_trial": False,
            "message": "Stripe not configured - billing disabled",
        }
    
    stripe.api_key = stripe_key
    
    u = Users.get_user_by_id(user.id)
    info = u.info or {} if u else {}
    customer_id = info.get("stripe_customer_id")
    
    if not customer_id:
        return {
            "has_billing_setup": False,
            "has_payment_method": False,
            "stripe_configured": True,
            "is_trial": False,
            "message": "Please set up billing to select a plan",
        }
    
    # Check if customer has a payment method
    try:
        payment_methods = stripe.PaymentMethod.list(
            customer=customer_id,
            type="card",
            limit=1,
        )
        has_payment = len(payment_methods.data) > 0
    except stripe.error.StripeError as e:
        log.warning(f"Stripe error checking payment methods: {e}")
        has_payment = False
    
    return {
        "has_billing_setup": has_payment,  # Only true if payment method exists
        "has_payment_method": has_payment,
        "stripe_configured": True,
        "is_trial": False,
        "customer_id": customer_id,
        "message": "Billing is set up" if has_payment else "Please add a payment method",
    }


@router.get("/tiers")
async def get_subscription_tiers(user=Depends(get_verified_user)):
    """Get all available subscription tiers."""
    from open_webui.models import billing
    
    tiers = billing.get_all_tiers()
    return {"tiers": tiers}


@router.get("/user/subscription")
async def get_user_subscription(user=Depends(get_verified_user)):
    """Get current user's subscription tier info."""
    from open_webui.models import billing
    
    sub = billing.get_user_subscription(user.id)
    if sub:
        tier_info = billing.get_tier_info(sub.tier_id)
        result = {
            "subscription": sub.model_dump(),
            "tier": tier_info,
        }
        # Include pending tier info if there's a scheduled change
        if sub.pending_tier_id:
            result["pending_tier"] = billing.get_tier_info(sub.pending_tier_id)
        return result
    
    # Return default tier info for users without a subscription
    from open_webui.env import BILLING_DEFAULT_TIER
    default_tier = BILLING_DEFAULT_TIER or "starter"
    tier_info = billing.get_tier_info(default_tier)
    return {
        "subscription": None,
        "tier": tier_info,
        "default_tier": default_tier,
    }


class SubscriptionForm(BaseModel):
    tier_id: str


@router.post("/user/subscription")
async def set_user_subscription(form_data: SubscriptionForm, user=Depends(get_verified_user)):
    """Set user's subscription tier.
    
    If the user has an active billing period, the tier change will be scheduled
    for the next billing cycle. They can cancel the pending change by selecting
    their current tier again.
    """
    from open_webui.models import billing
    
    tier_info = billing.get_tier_info(form_data.tier_id)
    if not tier_info:
        raise HTTPException(status_code=400, detail=f"Invalid tier_id: {form_data.tier_id}")
    
    # Set the subscription (may be immediate or pending)
    sub = billing.set_user_subscription(user.id, form_data.tier_id)
    
    result = {
        "subscription": sub.model_dump(),
        "tier": billing.get_tier_info(sub.tier_id),  # Current tier
    }
    
    # If there's a pending tier change, include that info
    if sub.pending_tier_id:
        result["pending_tier"] = billing.get_tier_info(sub.pending_tier_id)
        result["message"] = f"Your plan will change to {result['pending_tier']['name']} at the end of your current billing period."
    elif form_data.tier_id == sub.tier_id:
        # They may have cancelled a pending change
        result["message"] = f"Your plan is set to {tier_info['name']}."
    
    return result


@router.get("/user/bill")
async def get_user_bill(user=Depends(get_verified_user)):
    """Get current user's monthly bill summary including overage calculation."""
    from open_webui.models import billing
    
    bill = billing.calculate_monthly_bill(user.id)
    return bill


@router.get("/user/usage/summary")
async def get_user_usage_summary(user=Depends(get_verified_user)):
    """Get comprehensive usage summary including bill, daily breakdown, and model usage."""
    from open_webui.models import billing
    
    summary = billing.get_usage_summary(user.id)
    return summary


@router.get("/user/usage/daily")
async def get_user_daily_usage(
    user=Depends(get_verified_user),
    start_date: str = None,
    end_date: str = None,
):
    """Get user's daily usage for a date range.
    
    Query params:
        start_date: YYYY-MM-DD (defaults to start of current month)
        end_date: YYYY-MM-DD (defaults to today)
    """
    from open_webui.models import billing
    import datetime
    
    # Default to current month
    today = datetime.datetime.utcnow()
    if not start_date:
        start_date = f"{today.year:04d}-{today.month:02d}-01"
    if not end_date:
        end_date = today.strftime("%Y-%m-%d")
    
    # Validate date formats
    try:
        datetime.datetime.strptime(start_date, "%Y-%m-%d")
        datetime.datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    
    daily = billing.get_daily_usage(user.id, start_date, end_date)
    return {"daily_usage": [d.model_dump() for d in daily]}


@router.get("/user/usage/by_model")
async def get_user_usage_by_model(
    user=Depends(get_verified_user),
    start_date: str = None,
    end_date: str = None,
):
    """Get user's token usage breakdown by model for a date range.
    
    Query params:
        start_date: YYYY-MM-DD (defaults to start of current month)
        end_date: YYYY-MM-DD (defaults to today)
    """
    from open_webui.models import billing
    import datetime
    
    # Default to current month
    today = datetime.datetime.utcnow()
    if not start_date:
        start_date = f"{today.year:04d}-{today.month:02d}-01"
    if not end_date:
        end_date = today.strftime("%Y-%m-%d")
    
    # Validate date formats
    try:
        datetime.datetime.strptime(start_date, "%Y-%m-%d")
        datetime.datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    
    by_model = billing.get_usage_by_model(user.id, start_date, end_date)
    return {"by_model": by_model}


@router.post("/user/purchase")
async def user_purchase(payload: dict, user=Depends(get_verified_user)):
    """Create a token purchase record and credit user balance. This endpoint is an MVP and does not integrate a real payment flow (Stripe integration is planned separately). Request JSON: {tokens: number, cost: string?, currency: "USD"}
    """
    from open_webui.models import billing

    tokens = int(payload.get("tokens", 0))
    if tokens <= 0:
        raise HTTPException(status_code=400, detail="Invalid token amount")

    cost = payload.get("cost")
    currency = payload.get("currency") or "USD"

    try:
        purchase = billing.purchase_tokens(user.id, tokens, cost=cost, currency=currency, status="succeeded")
        balance = billing.get_user_balance(user.id)
        return {"purchase": purchase.model_dump(), "tokens_balance": int(balance)}
    except Exception as e:
        log.exception("Error creating token purchase")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user/create_checkout_session")
async def user_create_checkout_session(payload: dict, request: Request, user=Depends(get_verified_user)):
    """Create a Stripe Checkout session for purchasing tokens. Request JSON: {tokens: number, cost: string (USD), currency: 'USD'}"""
    stripe_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_key:
        raise HTTPException(status_code=400, detail="Stripe is not configured on the server.")

    try:
        import stripe

        stripe.api_key = stripe_key

        tokens = int(payload.get("tokens", 0))
        if tokens <= 0:
            raise HTTPException(status_code=400, detail="Invalid token amount")

        currency = payload.get("currency") or "USD"
        if str(currency).upper() != "USD":
            raise HTTPException(status_code=400, detail="Only USD purchases are supported")

        rate = _get_token_usd_rate_from_request(request)
        amount_cents = _usd_amount_cents_for_tokens(tokens, rate)
        computed_cost = f"{(Decimal(amount_cents) / Decimal('100')):.2f}"

        # Create pending TokenPurchase record
        from open_webui.models import billing

        tentative = billing.purchase_tokens(user.id, tokens, cost=computed_cost, currency=currency, status="pending")

        # Build success/cancel URLs
        # Use the dedicated /api/v1/billing/checkout/success endpoint which handles
        # confirmation server-side and then redirects to STRIPE_RETURN_URL
        base = _get_public_webui_base_url(request)
        success_url = f"{base}/api/v1/billing/checkout/success?checkout_success=1&purchase_id={tentative.id}&session_id={{CHECKOUT_SESSION_ID}}"
        
        stripe_return = os.environ.get("STRIPE_RETURN_URL")
        if stripe_return and not _is_localhost_url(stripe_return):
            cancel_url = f"{_normalize_base_url(stripe_return)}/?checkout_canceled=1"
        else:
            cancel_url = f"{base}/?checkout_canceled=1"

        # Get or create Stripe customer for this user to ensure correct email in checkout
        u = Users.get_user_by_id(user.id)
        info = u.info or {}
        customer_id = info.get("stripe_customer_id")
        if not customer_id:
            cust = stripe.Customer.create(email=u.email, metadata={"user_id": u.id})
            customer_id = cust.id
            info["stripe_customer_id"] = customer_id
            Users.update_user_by_id(user.id, {"info": info})

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"{tokens} tokens"},
                        "unit_amount": int(amount_cents),
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"purchase_id": tentative.id, "user_id": user.id},
        )

        # attach session id to token purchase
        from open_webui.internal.db import get_db
        with get_db() as db:
            tp = db.query(billing.TokenPurchase).filter_by(id=tentative.id).first()
            if tp:
                tp.stripe_session_id = session.id
                db.commit()

        return {
            "url": session.url,
            "purchase_id": tentative.id,
            "tokens": tokens,
            "amount_cents": int(amount_cents),
            "token_usd_rate": float(rate),
        }
    except Exception as e:
        log.exception("Error creating checkout session")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user/confirm_checkout")
async def user_confirm_checkout(payload: dict, user=Depends(get_verified_user)):
    """Confirm a Stripe Checkout purchase after redirect back to the app.

    This is a fallback for environments where Stripe webhooks cannot reach the server.
    Request JSON: {session_id: string}
    """
    stripe_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_key:
        raise HTTPException(status_code=400, detail="Stripe is not configured on the server.")

    session_id = (payload or {}).get("session_id")
    purchase_id = (payload or {}).get("purchase_id")
    if session_id is not None and not isinstance(session_id, str):
        raise HTTPException(status_code=400, detail="Invalid session_id")
    if purchase_id is not None and not isinstance(purchase_id, str):
        raise HTTPException(status_code=400, detail="Invalid purchase_id")
    if not session_id and not purchase_id:
        raise HTTPException(status_code=400, detail="Missing session_id or purchase_id")

    try:
        import stripe

        stripe.api_key = stripe_key

        from open_webui.models import billing
        from open_webui.internal.db import get_db

        if session_id:
            checkout = stripe.checkout.Session.retrieve(session_id)
            metadata = (getattr(checkout, "metadata", None) or {})
            purchase_id_from_session = metadata.get("purchase_id")
            user_id = metadata.get("user_id")

            if user_id and str(user_id) != str(user.id):
                raise HTTPException(status_code=403, detail="Session does not belong to this user")

            if purchase_id and purchase_id_from_session and str(purchase_id) != str(purchase_id_from_session):
                raise HTTPException(status_code=400, detail="purchase_id does not match session")

            purchase_id = purchase_id or purchase_id_from_session
            if not purchase_id:
                raise HTTPException(status_code=400, detail="Session missing purchase_id")

            # Stripe can report either payment_status ("paid") or status ("complete").
            payment_status = getattr(checkout, "payment_status", None)
            status = getattr(checkout, "status", None)
            if payment_status != "paid" and status != "complete":
                raise HTTPException(status_code=400, detail="Checkout session is not paid")

            billing.confirm_purchase(
                purchase_id,
                stripe_payment_id=getattr(checkout, "payment_intent", None),
            )
        else:
            # Fallback: confirm by purchase_id by reconciling against Stripe using the stored session id.
            with get_db() as db:
                tp = db.query(billing.TokenPurchase).filter_by(id=purchase_id).first()
                if not tp:
                    raise HTTPException(status_code=404, detail="Purchase not found")
                if str(tp.user_id) != str(user.id):
                    raise HTTPException(status_code=403, detail="Purchase does not belong to this user")

            billing.reconcile_one(purchase_id)

        bal = billing.get_user_balance(user.id)
        return {"status": "ok", "purchase_id": purchase_id, "tokens_balance": int(bal)}
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Error confirming checkout session")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checkout/success")
async def checkout_success_redirect(
    request: Request,
    checkout_success: str = None,
    session_id: str = None,
    purchase_id: str = None,
):
    """
    Handle Stripe checkout redirect. Confirms the purchase server-side and redirects to the app.
    
    This is a GET endpoint that Stripe redirects to after successful payment.
    It confirms the purchase and then redirects the user to the main app.
    """
    from fastapi.responses import RedirectResponse
    
    stripe_key = os.environ.get("STRIPE_API_KEY")
    redirect_base = os.environ.get("STRIPE_RETURN_URL", "/")
    
    log.info(f"[CHECKOUT_SUCCESS] Received redirect: session_id={session_id}, purchase_id={purchase_id}")
    
    if not stripe_key:
        log.error("[CHECKOUT_SUCCESS] Stripe not configured")
        return RedirectResponse(url=redirect_base)
    
    if not session_id and not purchase_id:
        log.error("[CHECKOUT_SUCCESS] No session_id or purchase_id provided")
        return RedirectResponse(url=redirect_base)
    
    try:
        import stripe
        stripe.api_key = stripe_key
        
        from open_webui.models import billing
        
        if session_id:
            checkout = stripe.checkout.Session.retrieve(session_id)
            metadata = (getattr(checkout, "metadata", None) or {})
            purchase_id_from_session = metadata.get("purchase_id")
            
            if purchase_id and purchase_id_from_session and str(purchase_id) != str(purchase_id_from_session):
                log.error(f"[CHECKOUT_SUCCESS] purchase_id mismatch: {purchase_id} vs {purchase_id_from_session}")
                return RedirectResponse(url=redirect_base)
            
            purchase_id = purchase_id or purchase_id_from_session
            
            payment_status = getattr(checkout, "payment_status", None)
            status = getattr(checkout, "status", None)
            
            if payment_status != "paid" and status != "complete":
                log.warning(f"[CHECKOUT_SUCCESS] Session not paid: payment_status={payment_status}, status={status}")
                return RedirectResponse(url=redirect_base)
            
            if purchase_id:
                billing.confirm_purchase(
                    purchase_id,
                    stripe_payment_id=getattr(checkout, "payment_intent", None),
                )
                log.info(f"[CHECKOUT_SUCCESS] Purchase {purchase_id} confirmed!")
        elif purchase_id:
            billing.reconcile_one(purchase_id)
            log.info(f"[CHECKOUT_SUCCESS] Purchase {purchase_id} reconciled!")
        
        return RedirectResponse(url=redirect_base)
        
    except Exception as e:
        log.exception(f"[CHECKOUT_SUCCESS] Error confirming purchase: {e}")
        return RedirectResponse(url=redirect_base)


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Stripe webhook endpoint — set STRIPE_WEBHOOK_SECRET to validate signatures."""
    stripe_key = os.environ.get("STRIPE_API_KEY")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not stripe_key or not webhook_secret:
        # If not configured, we still accept the call for testing but log a warning
        log.warning("Stripe webhook called but STRIPE_WEBHOOK_SECRET is not configured; skipping signature verification")

    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    try:
        import stripe

        stripe.api_key = stripe_key
        if webhook_secret and sig_header:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            event = None
            try:
                event = json.loads(payload)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid webhook payload")

        # Handle checkout.session.completed
        if (event and event.get('type') == 'checkout.session.completed') or (hasattr(event, 'type') and getattr(event, 'type') == 'checkout.session.completed'):
            data = event['data']['object'] if isinstance(event, dict) else event['data']['object']
            purchase_id = (data.get('metadata') or {}).get('purchase_id')
            payment_intent = data.get('payment_intent')

            # record webhook received
            try:
                from open_webui.utils.telemetry.metrics import inc_billing_webhook

                inc_billing_webhook('checkout.session.completed', 'received')
            except Exception:
                pass

            if purchase_id:
                from open_webui.models import billing
                try:
                    billing.confirm_purchase(purchase_id, stripe_payment_id=payment_intent)
                    try:
                        from open_webui.utils.telemetry.metrics import inc_billing_webhook

                        inc_billing_webhook('checkout.session.completed', 'confirmed', {"purchase_id": purchase_id})
                    except Exception:
                        pass
                except Exception:
                    try:
                        from open_webui.utils.telemetry.metrics import inc_billing_webhook

                        inc_billing_webhook('checkout.session.completed', 'confirm_failed', {"purchase_id": purchase_id})
                    except Exception:
                        pass

        return {'status': 'ok'}
    except stripe.error.SignatureVerificationError as e:
        log.exception('Invalid Stripe signature')
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception('Error processing stripe webhook')
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# LOCAL BILLING ADMINISTRATION
# ============================================================================

@router.post("/admin/billing/run")
async def admin_run_billing(user=Depends(get_admin_user)):
    """Manually trigger billing run (admin only).
    
    This charges all users whose billing period has ended.
    Normally this would be run by cron, but admins can trigger it manually.
    """
    from open_webui.models.billing import Billing
    
    stripe_api_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_api_key:
        raise HTTPException(status_code=500, detail="STRIPE_API_KEY not configured")
    
    results = Billing.run_billing(stripe_api_key)
    return results


@router.get("/admin/billing/pending")
async def admin_get_pending_invoices(user=Depends(get_admin_user)):
    """Get all pending/failed invoices for admin review."""
    from open_webui.models.billing import Billing
    
    invoices = Billing.get_pending_invoices()
    return [inv.model_dump() for inv in invoices]


@router.get("/admin/billing/users-to-bill")
async def admin_get_users_to_bill(user=Depends(get_admin_user)):
    """Preview which users would be billed if billing runs now."""
    from open_webui.models.billing import Billing
    
    users = Billing.get_users_to_bill()
    return users


@router.post("/admin/billing/charge-invoice/{invoice_id}")
async def admin_charge_invoice(invoice_id: str, user=Depends(get_admin_user)):
    """Manually retry charging a specific invoice."""
    from open_webui.models.billing import Billing
    
    stripe_api_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_api_key:
        raise HTTPException(status_code=500, detail="STRIPE_API_KEY not configured")
    
    result = Billing.charge_invoice(invoice_id, stripe_api_key)
    
    if result["success"]:
        # Advance billing period if charge succeeded
        from open_webui.models.billing import BillingInvoice
        from open_webui.internal.db import get_db
        with get_db() as db:
            invoice = db.query(BillingInvoice).filter_by(id=invoice_id).first()
            if invoice:
                Billing.advance_billing_period(invoice.user_id)
    
    return result


@router.get("/user/invoices")
async def get_user_invoices(user=Depends(get_verified_user)):
    """Get current user's invoice history."""
    from open_webui.models.billing import Billing
    
    invoices = Billing.get_user_invoices(user.id)
    return [inv.model_dump() for inv in invoices]
