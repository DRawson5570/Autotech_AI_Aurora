import time
import uuid
import os
from pydantic import BaseModel, ConfigDict

from open_webui.internal.db import Base, get_db
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    String,
    Text,
    Index,
)


class UsageEvent(Base):
    __tablename__ = "usage_event"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, unique=True)
    user_id = Column(String, index=True)
    chat_id = Column(String, nullable=True)
    message_id = Column(String, nullable=True)

    tokens_prompt = Column(BigInteger, default=0)
    tokens_completion = Column(BigInteger, default=0)
    tokens_total = Column(BigInteger, default=0)

    token_source = Column(String, nullable=True)  # provider or tokenizer

    created_at = Column(BigInteger, nullable=False)


class UserSubscription(Base):
    """User's subscription tier for tiered billing model."""
    __tablename__ = "user_subscription"
    __table_args__ = {"extend_existing": True}

    user_id = Column(String, primary_key=True, unique=True)
    tier_id = Column(String, nullable=False, default="starter")  # starter, pro, enterprise
    pending_tier_id = Column(String, nullable=True)  # Tier change scheduled for next cycle
    stripe_subscription_id = Column(String, nullable=True)  # For Stripe recurring billing
    current_period_start = Column(BigInteger, nullable=True)  # epoch timestamp
    current_period_end = Column(BigInteger, nullable=True)  # epoch timestamp
    status = Column(String, nullable=False, default="active")  # active, canceled, past_due
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class DailyUsage(Base):
    """Daily token usage breakdown for usage analytics."""
    __tablename__ = "daily_usage"
    __table_args__ = (
        Index("ix_daily_usage_user_date", "user_id", "date"),
        {"extend_existing": True},
    )

    id = Column(String, primary_key=True, unique=True)
    user_id = Column(String, index=True)
    date = Column(String, nullable=False)  # YYYY-MM-DD format
    model_id = Column(String, nullable=True)  # which model was used
    tokens_prompt = Column(BigInteger, default=0)
    tokens_completion = Column(BigInteger, default=0)
    tokens_total = Column(BigInteger, default=0)
    request_count = Column(BigInteger, default=0)  # number of requests
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class UserTokenUsage(Base):
    __tablename__ = "user_token_usage"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, unique=True)
    user_id = Column(String, index=True)

    period_start = Column(BigInteger, nullable=False)  # epoch timestamp start of period
    period_end = Column(BigInteger, nullable=False)  # epoch timestamp end of period

    tokens_prompt = Column(BigInteger, default=0)
    tokens_completion = Column(BigInteger, default=0)
    tokens_total = Column(BigInteger, default=0)

    cost_total = Column(String, nullable=True)
    currency = Column(String, nullable=True, default="USD")

    billed = Column(Boolean, default=False)

    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class UsageEventModel(BaseModel):
    id: str
    user_id: str
    chat_id: str | None
    message_id: str | None
    tokens_prompt: int
    tokens_completion: int
    tokens_total: int
    token_source: str | None
    created_at: int

    model_config = ConfigDict(from_attributes=True)


class UserTokenUsageModel(BaseModel):
    id: str
    user_id: str
    period_start: int
    period_end: int
    tokens_prompt: int
    tokens_completion: int
    tokens_total: int
    cost_total: str | None = None
    currency: str | None = "USD"
    billed: bool = False
    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


class UserSubscriptionModel(BaseModel):
    user_id: str
    tier_id: str
    pending_tier_id: str | None = None
    stripe_subscription_id: str | None = None
    current_period_start: int | None = None
    current_period_end: int | None = None
    status: str = "active"
    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


class DailyUsageModel(BaseModel):
    id: str
    user_id: str
    date: str
    model_id: str | None = None
    tokens_prompt: int
    tokens_completion: int
    tokens_total: int
    request_count: int = 0
    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)


# Convenience helper functions

def _billing_period_for_timestamp(ts: int) -> tuple[int, int]:
    """Return (period_start_ts, period_end_ts) for month-based billing period (UTC)."""
    import datetime

    dt = datetime.datetime.utcfromtimestamp(ts)
    start = datetime.datetime(dt.year, dt.month, 1)
    if dt.month == 12:
        end = datetime.datetime(dt.year + 1, 1, 1)
    else:
        end = datetime.datetime(dt.year, dt.month + 1, 1)

    return (int(start.timestamp()), int(end.timestamp()))


class UserTokenBalance(Base):
    __tablename__ = "user_token_balance"
    __table_args__ = {"extend_existing": True}

    user_id = Column(String, primary_key=True, unique=True)
    tokens_balance = Column(BigInteger, default=0)
    updated_at = Column(BigInteger, nullable=False)
    # Auto-renew settings
    auto_renew_enabled = Column(Boolean, default=False, nullable=False)
    auto_renew_tokens = Column(BigInteger, default=0, nullable=False)  # 0 = disabled


class TokenPurchase(Base):
    __tablename__ = "token_purchase"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, unique=True)
    user_id = Column(String, index=True)
    tokens = Column(BigInteger, nullable=False)
    cost = Column(String, nullable=True)
    currency = Column(String, nullable=True, default="USD")
    status = Column(String, nullable=False, default="pending")  # pending, succeeded, failed
    stripe_session_id = Column(String, nullable=True)
    stripe_payment_id = Column(String, nullable=True)
    created_at = Column(BigInteger, nullable=False)


# Additional helpers for token purchase & balances

class UserTokenBalanceModel(BaseModel):
    user_id: str
    tokens_balance: int
    updated_at: int
    auto_renew_enabled: bool = False
    auto_renew_tokens: int = 0

    model_config = ConfigDict(from_attributes=True)


class TokenPurchaseModel(BaseModel):
    id: str
    user_id: str
    tokens: int
    cost: str | None
    currency: str | None
    status: str
    stripe_session_id: str | None = None
    stripe_payment_id: str | None = None
    created_at: int

    model_config = ConfigDict(from_attributes=True)


class BillingInvoice(Base):
    """Invoice records for subscription billing."""
    __tablename__ = "billing_invoice"
    __table_args__ = (
        Index("ix_billing_invoice_user_period", "user_id", "period_start"),
        # Unique constraint prevents duplicate invoices for the same period
        Index("uq_billing_invoice_user_period", "user_id", "period_start", unique=True),
        {"extend_existing": True},
    )

    id = Column(String, primary_key=True, unique=True)
    user_id = Column(String, index=True)
    
    # Billing period this invoice covers
    period_start = Column(BigInteger, nullable=False)
    period_end = Column(BigInteger, nullable=False)
    
    # Tier and usage details
    tier_id = Column(String, nullable=False)
    tier_name = Column(String, nullable=True)
    base_price_cents = Column(BigInteger, default=0)
    tokens_included = Column(BigInteger, default=0)
    tokens_used = Column(BigInteger, default=0)
    tokens_overage = Column(BigInteger, default=0)
    overage_cost_cents = Column(BigInteger, default=0)
    total_amount_cents = Column(BigInteger, default=0)
    
    # Payment status
    status = Column(String, nullable=False, default="pending")  # pending, paid, failed, void
    stripe_payment_intent_id = Column(String, nullable=True)
    stripe_charge_id = Column(String, nullable=True)
    failure_reason = Column(Text, nullable=True)
    retry_count = Column(BigInteger, default=0)
    
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    paid_at = Column(BigInteger, nullable=True)


class BillingInvoiceModel(BaseModel):
    id: str
    user_id: str
    period_start: int
    period_end: int
    tier_id: str
    tier_name: str | None = None
    base_price_cents: int = 0
    tokens_included: int = 0
    tokens_used: int = 0
    tokens_overage: int = 0
    overage_cost_cents: int = 0
    total_amount_cents: int = 0
    status: str = "pending"
    stripe_payment_intent_id: str | None = None
    stripe_charge_id: str | None = None
    failure_reason: str | None = None
    retry_count: int = 0
    created_at: int
    updated_at: int
    paid_at: int | None = None

    model_config = ConfigDict(from_attributes=True)


class Billing:
    @staticmethod
    def record_usage_event(user_id: str, chat_id: str | None, message_id: str | None, tokens_prompt: int, tokens_completion: int, tokens_total: int, token_source: str | None = None, ts: int | None = None):
        ts = ts or int(time.time())
        with get_db() as db:
            # insert usage_event
            ue = UsageEvent(
                **{
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "tokens_prompt": int(tokens_prompt or 0),
                    "tokens_completion": int(tokens_completion or 0),
                    "tokens_total": int(tokens_total or 0),
                    "token_source": token_source,
                    "created_at": ts,
                }
            )
            db.add(ue)

            # upsert user_token_usage for the billing period (month-level)
            period_start, period_end = _billing_period_for_timestamp(ts)

            utu = (
                db.query(UserTokenUsage)
                .filter_by(user_id=user_id, period_start=period_start, period_end=period_end)
                .first()
            )

            if not utu:
                now = int(time.time())
                utu = UserTokenUsage(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    period_start=period_start,
                    period_end=period_end,
                    tokens_prompt=int(tokens_prompt or 0),
                    tokens_completion=int(tokens_completion or 0),
                    tokens_total=int(tokens_total or 0),
                    cost_total=None,
                    currency="USD",
                    billed=False,
                    created_at=now,
                    updated_at=now,
                )
                db.add(utu)
            else:
                utu.tokens_prompt = (utu.tokens_prompt or 0) + int(tokens_prompt or 0)
                utu.tokens_completion = (utu.tokens_completion or 0) + int(tokens_completion or 0)
                utu.tokens_total = (utu.tokens_total or 0) + int(tokens_total or 0)
                utu.updated_at = int(time.time())

            # decrement user token balance if present (prepaid token model)
            if tokens_total and int(tokens_total) > 0:
                balance = db.query(UserTokenBalance).filter_by(user_id=user_id).first()
                if balance:
                    # allow negative balances (we record usage even if user exhausted prepaid tokens)
                    balance.tokens_balance = (balance.tokens_balance or 0) - int(tokens_total)
                    balance.updated_at = int(time.time())

            # upsert daily_usage for analytics breakdown
            import datetime
            date_str = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            # Extract model from token_source if available
            model_id = token_source.split(":")[0] if token_source and ":" in token_source else token_source
            
            daily = (
                db.query(DailyUsage)
                .filter_by(user_id=user_id, date=date_str, model_id=model_id)
                .first()
            )
            now = int(time.time())
            if not daily:
                daily = DailyUsage(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    date=date_str,
                    model_id=model_id,
                    tokens_prompt=int(tokens_prompt or 0),
                    tokens_completion=int(tokens_completion or 0),
                    tokens_total=int(tokens_total or 0),
                    request_count=1,
                    created_at=now,
                    updated_at=now,
                )
                db.add(daily)
            else:
                daily.tokens_prompt = (daily.tokens_prompt or 0) + int(tokens_prompt or 0)
                daily.tokens_completion = (daily.tokens_completion or 0) + int(tokens_completion or 0)
                daily.tokens_total = (daily.tokens_total or 0) + int(tokens_total or 0)
                daily.request_count = (daily.request_count or 0) + 1
                daily.updated_at = now

            db.commit()

    @staticmethod
    def get_user_balance(user_id: str) -> int:
        with get_db() as db:
            bal = db.query(UserTokenBalance).filter_by(user_id=user_id).first()
            return int(bal.tokens_balance if bal else 0)

    @staticmethod
    def check_overage_status(user_id: str) -> dict | None:
        """Check if user is in overage and calculate potential upgrade savings.
        
        Returns None if not in overage, otherwise:
        {
            "in_overage": True,
            "current_tier": str,
            "tokens_over": int,
            "projected_overage_cost": float,
            "upgrade_tier": str | None,
            "upgrade_tier_name": str | None,
            "upgrade_price": float | None,
            "projected_total_current": float,
            "projected_total_upgrade": float | None,
            "savings": float | None,
        }
        """
        from open_webui.env import BILLING_TIERS
        
        with get_db() as db:
            # Get user's subscription
            sub = db.query(UserSubscription).filter_by(user_id=user_id).first()
            if not sub or sub.tier_id == "none":
                return None
            
            # Get current balance
            bal = db.query(UserTokenBalance).filter_by(user_id=user_id).first()
            current_balance = int(bal.tokens_balance if bal else 0)
            
            # Not in overage if balance is positive
            if current_balance >= 0:
                return None
            
            tokens_over = abs(current_balance)
            current_tier = BILLING_TIERS.get(sub.tier_id, {})
            
            # Calculate current projected cost
            base_price = current_tier.get("monthly_price_cents", 0) / 100
            overage_rate = current_tier.get("overage_rate_per_10k", 50) / 100  # Convert cents to dollars
            projected_overage_cost = (tokens_over / 10000) * overage_rate
            projected_total_current = base_price + projected_overage_cost
            
            # Find next tier up
            tier_order = ["starter", "pro", "enterprise"]
            current_idx = tier_order.index(sub.tier_id) if sub.tier_id in tier_order else -1
            
            upgrade_tier = None
            upgrade_tier_name = None
            upgrade_price = None
            projected_total_upgrade = None
            savings = None
            
            if current_idx >= 0 and current_idx < len(tier_order) - 1:
                next_tier_id = tier_order[current_idx + 1]
                next_tier = BILLING_TIERS.get(next_tier_id, {})
                
                next_base = next_tier.get("monthly_price_cents", 0) / 100
                next_tokens = next_tier.get("tokens_included", 0)
                next_overage_rate = next_tier.get("overage_rate_per_10k", 50) / 100
                
                # How much would user be over on next tier?
                # User has used: tier_included + tokens_over
                total_used = current_tier.get("tokens_included", 0) + tokens_over
                next_tier_over = max(0, total_used - next_tokens)
                next_overage_cost = (next_tier_over / 10000) * next_overage_rate
                projected_total_upgrade = next_base + next_overage_cost
                
                if projected_total_upgrade < projected_total_current:
                    upgrade_tier = next_tier_id
                    upgrade_tier_name = next_tier.get("name", next_tier_id.title())
                    upgrade_price = next_base
                    savings = projected_total_current - projected_total_upgrade
            
            return {
                "in_overage": True,
                "current_tier": sub.tier_id,
                "tokens_over": tokens_over,
                "projected_overage_cost": round(projected_overage_cost, 2),
                "upgrade_tier": upgrade_tier,
                "upgrade_tier_name": upgrade_tier_name,
                "upgrade_price": upgrade_price,
                "projected_total_current": round(projected_total_current, 2),
                "projected_total_upgrade": round(projected_total_upgrade, 2) if projected_total_upgrade else None,
                "savings": round(savings, 2) if savings else None,
            }

    @staticmethod
    def has_user_balance_record(user_id: str) -> bool:
        """Return True if the user has an explicit UserTokenBalance row.

        This is used to distinguish token-metered users from users that have not
        been enrolled into the token billing system yet.
        """
        with get_db() as db:
            bal = db.query(UserTokenBalance).filter_by(user_id=user_id).first()
            return bool(bal)

    @staticmethod
    def get_auto_renew_settings(user_id: str) -> dict:
        """Return the user's auto-renew settings."""
        with get_db() as db:
            bal = db.query(UserTokenBalance).filter_by(user_id=user_id).first()
            if not bal:
                return {"auto_renew_enabled": False, "auto_renew_tokens": 0}
            return {
                "auto_renew_enabled": bool(bal.auto_renew_enabled),
                "auto_renew_tokens": int(bal.auto_renew_tokens or 0),
            }

    @staticmethod
    def set_auto_renew_settings(user_id: str, enabled: bool, tokens: int) -> dict:
        """Update the user's auto-renew settings."""
        with get_db() as db:
            bal = db.query(UserTokenBalance).filter_by(user_id=user_id).first()
            now = int(time.time())
            if not bal:
                # Create a balance record if none exists
                bal = UserTokenBalance(
                    user_id=user_id,
                    tokens_balance=0,
                    updated_at=now,
                    auto_renew_enabled=enabled,
                    auto_renew_tokens=int(tokens) if enabled else 0,
                )
                db.add(bal)
            else:
                bal.auto_renew_enabled = enabled
                bal.auto_renew_tokens = int(tokens) if enabled else 0
                bal.updated_at = now
            db.commit()
            return {
                "auto_renew_enabled": bool(bal.auto_renew_enabled),
                "auto_renew_tokens": int(bal.auto_renew_tokens or 0),
            }

    @staticmethod
    def purchase_tokens(user_id: str, tokens: int, cost: str | None = None, currency: str = "USD", stripe_payment_id: str | None = None, status: str = "succeeded", ts: int | None = None) -> TokenPurchaseModel:
        """Create a TokenPurchase record and credit balance immediately when status=='succeeded'. For Stripe flow you'll create a record with status='pending' and finalize via confirm_purchase."""
        ts = ts or int(time.time())
        with get_db() as db:
            tp = TokenPurchase(
                id=str(uuid.uuid4()),
                user_id=user_id,
                tokens=int(tokens),
                cost=cost,
                currency=currency,
                status=status,
                stripe_payment_id=stripe_payment_id,
                created_at=ts,
            )
            db.add(tp)

            # credit immediately for non-pending purchases
            if status == "succeeded":
                bal = db.query(UserTokenBalance).filter_by(user_id=user_id).first()
                if not bal:
                    bal = UserTokenBalance(user_id=user_id, tokens_balance=int(tokens), updated_at=ts)
                    db.add(bal)
                else:
                    bal.tokens_balance = (bal.tokens_balance or 0) + int(tokens)
                    bal.updated_at = ts

            db.commit()

            return TokenPurchaseModel.model_validate(tp)

    @staticmethod
    def confirm_purchase(purchase_id: str, stripe_payment_id: str | None = None) -> TokenPurchaseModel | None:
        """Idempotently mark a pending TokenPurchase as succeeded and credit the user's balance."""
        with get_db() as db:
            tp = db.query(TokenPurchase).filter_by(id=purchase_id).first()
            if not tp:
                return None
            if tp.status == "succeeded":
                return TokenPurchaseModel.model_validate(tp)

            # mark succeeded and set payment id
            tp.status = "succeeded"
            if stripe_payment_id:
                tp.stripe_payment_id = stripe_payment_id

            # credit user's balance
            bal = db.query(UserTokenBalance).filter_by(user_id=tp.user_id).first()
            now = int(time.time())
            if not bal:
                bal = UserTokenBalance(user_id=tp.user_id, tokens_balance=int(tp.tokens), updated_at=now)
                db.add(bal)
            else:
                bal.tokens_balance = (bal.tokens_balance or 0) + int(tp.tokens)
                bal.updated_at = now

            db.commit()
            return TokenPurchaseModel.model_validate(tp)

    @staticmethod
    def reconcile_one(purchase_id: str) -> dict:
        """Attempt to reconcile a single pending purchase using Stripe session or payment intent info.

        Returns a dict summarizing action: {purchase_id, status, action, reason}
        """
        import logging
        log = logging.getLogger(__name__)

        with get_db() as db:
            tp = db.query(TokenPurchase).filter_by(id=purchase_id).first()
            if not tp:
                return {"purchase_id": purchase_id, "status": "missing", "action": "none", "reason": "not_found"}

            if tp.status == "succeeded":
                return {"purchase_id": purchase_id, "status": "succeeded", "action": "none", "reason": "already_succeeded"}

            stripe_key = os.environ.get("STRIPE_API_KEY")
            if not stripe_key:
                # cannot verify with Stripe; leave pending
                return {"purchase_id": purchase_id, "status": tp.status, "action": "none", "reason": "stripe_not_configured"}

            try:
                import stripe
                stripe.api_key = stripe_key

                # Prefer lookup by session id if present
                if tp.stripe_session_id:
                    session = stripe.checkout.Session.retrieve(tp.stripe_session_id)
                    # If session has payment_intent and payment status was succeeded, confirm
                    payment_intent = session.get("payment_intent") or (session.get("payment_status") if isinstance(session, dict) else None)
                    if payment_intent:
                        pi = stripe.PaymentIntent.retrieve(payment_intent)
                        if getattr(pi, "status", None) in ("succeeded", "requires_capture") or (isinstance(pi, dict) and pi.get("status") in ("succeeded",)):
                            # confirm locally
                            Billing.confirm_purchase(tp.id, stripe_payment_id=payment_intent)
                            log.info("Reconciled purchase %s via payment_intent %s", tp.id, payment_intent)
                            try:
                                from open_webui.utils.telemetry.metrics import inc_reconcile_result

                                inc_reconcile_result('confirmed', 'payment_intent_succeeded')
                            except Exception:
                                pass
                            return {"purchase_id": purchase_id, "status": "succeeded", "action": "confirmed", "reason": "payment_intent_succeeded"}

                # Fallback: if we have a stripe_payment_id already recorded, check it
                if tp.stripe_payment_id:
                    pi = stripe.PaymentIntent.retrieve(tp.stripe_payment_id)
                    if getattr(pi, "status", None) in ("succeeded", "requires_capture") or (isinstance(pi, dict) and pi.get("status") in ("succeeded",)):
                        Billing.confirm_purchase(tp.id, stripe_payment_id=tp.stripe_payment_id)
                        try:
                            from open_webui.utils.telemetry.metrics import inc_reconcile_result

                            inc_reconcile_result('confirmed', 'existing_payment_intent_succeeded')
                        except Exception:
                            pass
                        return {"purchase_id": purchase_id, "status": "succeeded", "action": "confirmed", "reason": "existing_payment_intent_succeeded"}

                # Otherwise, leave it pending
                try:
                    from open_webui.utils.telemetry.metrics import inc_reconcile_result

                    inc_reconcile_result('none', 'no_positive_evidence')
                except Exception:
                    pass
                return {"purchase_id": purchase_id, "status": tp.status, "action": "none", "reason": "no_positive_evidence"}
            except Exception as e:
                log.exception("Error reconciling purchase %s", purchase_id)
                try:
                    from open_webui.utils.telemetry.metrics import inc_reconcile_result

                    inc_reconcile_result('error', str(e))
                except Exception:
                    pass
                return {"purchase_id": purchase_id, "status": tp.status, "action": "error", "reason": str(e)}

    @staticmethod
    def reconcile_pending_purchases(older_than_seconds: int = 3600) -> list:
        """Reconcile all pending purchases older than a given age. Returns list of summary dicts for each purchase attempted."""
        import time

        cutoff = int(time.time()) - int(older_than_seconds)
        results = []
        with get_db() as db:
            items = db.query(TokenPurchase).filter(TokenPurchase.status == "pending", TokenPurchase.created_at <= cutoff).all()
            for it in items:
                results.append(Billing.reconcile_one(it.id))
        return results

    # ===== SUBSCRIPTION MANAGEMENT (Tiered Billing) =====

    @staticmethod
    def get_user_subscription(user_id: str) -> UserSubscriptionModel | None:
        """Get user's subscription tier info."""
        with get_db() as db:
            sub = db.query(UserSubscription).filter_by(user_id=user_id).first()
            if sub:
                return UserSubscriptionModel.model_validate(sub)
            return None

    @staticmethod
    def set_user_subscription(
        user_id: str,
        tier_id: str,
        stripe_subscription_id: str | None = None,
        period_start: int | None = None,
        period_end: int | None = None,
        status: str = "active"
    ) -> UserSubscriptionModel:
        """Create or update user's subscription tier.
        
        For existing subscriptions with an active billing period:
        - If tier_id matches current tier, clear any pending change
        - If tier_id differs, set as pending (takes effect next cycle)
        
        For new subscriptions or no billing period yet:
        - Apply tier immediately
        """
        now = int(time.time())
        with get_db() as db:
            sub = db.query(UserSubscription).filter_by(user_id=user_id).first()
            if not sub:
                # New subscription - apply immediately
                sub = UserSubscription(
                    user_id=user_id,
                    tier_id=tier_id,
                    pending_tier_id=None,
                    stripe_subscription_id=stripe_subscription_id,
                    current_period_start=period_start,
                    current_period_end=period_end,
                    status=status,
                    created_at=now,
                    updated_at=now,
                )
                db.add(sub)
            else:
                # Existing subscription - check if we should defer the change
                has_active_period = (
                    sub.current_period_end is not None 
                    and sub.current_period_end > now
                    and sub.tier_id not in (None, "none")
                )
                
                if has_active_period:
                    if tier_id == sub.tier_id:
                        # User selected current tier - cancel pending change
                        sub.pending_tier_id = None
                    else:
                        # Different tier - set as pending for next cycle
                        sub.pending_tier_id = tier_id
                else:
                    # No active period - apply immediately
                    sub.tier_id = tier_id
                    sub.pending_tier_id = None
                
                if stripe_subscription_id is not None:
                    sub.stripe_subscription_id = stripe_subscription_id
                if period_start is not None:
                    sub.current_period_start = period_start
                if period_end is not None:
                    sub.current_period_end = period_end
                sub.status = status
                sub.updated_at = now
            db.commit()
            db.refresh(sub)
            return UserSubscriptionModel.model_validate(sub)

    @staticmethod
    def get_tier_info(tier_id: str) -> dict | None:
        """Get tier configuration from env."""
        from open_webui.env import BILLING_TIERS
        return BILLING_TIERS.get(tier_id)

    @staticmethod
    def get_all_tiers() -> dict:
        """Get all available subscription tiers."""
        from open_webui.env import BILLING_TIERS
        return BILLING_TIERS

    @staticmethod
    def get_monthly_usage(user_id: str, period_start: int | None = None, period_end: int | None = None) -> int:
        """Get total tokens used in a billing period. Defaults to current month."""
        if period_start is None or period_end is None:
            period_start, period_end = _billing_period_for_timestamp(int(time.time()))
        
        with get_db() as db:
            utu = (
                db.query(UserTokenUsage)
                .filter_by(user_id=user_id, period_start=period_start, period_end=period_end)
                .first()
            )
            return int(utu.tokens_total if utu else 0)

    @staticmethod
    def calculate_monthly_bill(user_id: str, period_start: int | None = None, period_end: int | None = None) -> dict:
        """Calculate user's monthly bill with tier, usage, and overage.
        
        Returns:
            {
                "tier_id": str,
                "tier_name": str,
                "base_price_cents": int,
                "tokens_included": int,
                "tokens_used": int,
                "tokens_overage": int,
                "overage_rate_per_1k_cents": int,
                "overage_cost_cents": int,
                "total_cost_cents": int,
                "usage_percent": float,  # 0-100+
            }
        """
        sub = Billing.get_user_subscription(user_id)
        # Use 'none' for users without a subscription, not 'starter'
        tier_id = sub.tier_id if sub and sub.tier_id and sub.tier_id != "none" else "none"
        tier = Billing.get_tier_info(tier_id)
        
        # If no tier (new user), return minimal info
        if not tier:
            return {
                "tier_id": "none",
                "tier_name": "No Plan",
                "base_price_cents": 0,
                "tokens_included": 0,
                "tokens_used": Billing.get_monthly_usage(user_id, period_start, period_end),
                "tokens_overage": 0,
                "overage_rate_per_1k_cents": 0,
                "overage_cost_cents": 0,
                "total_cost_cents": 0,
                "usage_percent": 0,
            }
        
        tokens_used = Billing.get_monthly_usage(user_id, period_start, period_end)
        tokens_included = tier["tokens_included"]
        tokens_overage = max(0, tokens_used - tokens_included)
        
        # Overage cost calculation
        overage_rate_per_1k = tier["overage_rate_per_1k_cents"]
        overage_cost_cents = int((tokens_overage / 1000) * overage_rate_per_1k)
        
        base_price = tier["monthly_price_cents"]
        total_cost = base_price + overage_cost_cents
        
        usage_percent = (tokens_used / tokens_included * 100) if tokens_included > 0 else 0
        
        return {
            "tier_id": tier_id,
            "tier_name": tier["name"],
            "base_price_cents": base_price,
            "tokens_included": tokens_included,
            "tokens_used": tokens_used,
            "tokens_overage": tokens_overage,
            "overage_rate_per_1k_cents": overage_rate_per_1k,
            "overage_cost_cents": overage_cost_cents,
            "total_cost_cents": total_cost,
            "usage_percent": round(usage_percent, 1),
        }

    # ===== DAILY USAGE ANALYTICS =====

    @staticmethod
    def get_daily_usage(user_id: str, start_date: str, end_date: str) -> list[DailyUsageModel]:
        """Get daily usage records for a user within date range (YYYY-MM-DD format)."""
        with get_db() as db:
            items = (
                db.query(DailyUsage)
                .filter(
                    DailyUsage.user_id == user_id,
                    DailyUsage.date >= start_date,
                    DailyUsage.date <= end_date,
                )
                .order_by(DailyUsage.date.asc())
                .all()
            )
            return [DailyUsageModel.model_validate(item) for item in items]

    @staticmethod
    def get_usage_by_model(user_id: str, start_date: str, end_date: str) -> list[dict]:
        """Get usage breakdown by model for a date range.
        
        Returns list of: {"model_id": str, "tokens_total": int, "request_count": int}
        """
        from sqlalchemy import func
        
        with get_db() as db:
            results = (
                db.query(
                    DailyUsage.model_id,
                    func.sum(DailyUsage.tokens_total).label("tokens_total"),
                    func.sum(DailyUsage.request_count).label("request_count"),
                )
                .filter(
                    DailyUsage.user_id == user_id,
                    DailyUsage.date >= start_date,
                    DailyUsage.date <= end_date,
                )
                .group_by(DailyUsage.model_id)
                .all()
            )
            return [
                {
                    "model_id": r.model_id or "unknown",
                    "tokens_total": int(r.tokens_total or 0),
                    "request_count": int(r.request_count or 0),
                }
                for r in results
            ]

    @staticmethod
    def get_usage_summary(user_id: str) -> dict:
        """Get comprehensive usage summary for current billing period.
        
        Returns:
            {
                "bill": {...},  # from calculate_monthly_bill
                "daily_usage": [...],  # last 30 days
                "by_model": [...],  # breakdown by model
                "period_start": str,  # YYYY-MM-DD
                "period_end": str,
                "subscription": {...},  # current subscription info
                "pending_tier": {...} | None,  # pending tier info if any
            }
        """
        import datetime
        
        # Current billing period
        now = int(time.time())
        period_start_ts, period_end_ts = _billing_period_for_timestamp(now)
        
        period_start = datetime.datetime.utcfromtimestamp(period_start_ts).strftime("%Y-%m-%d")
        period_end = datetime.datetime.utcfromtimestamp(period_end_ts - 1).strftime("%Y-%m-%d")  # -1 to stay in current month
        
        bill = Billing.calculate_monthly_bill(user_id, period_start_ts, period_end_ts)
        daily_usage = Billing.get_daily_usage(user_id, period_start, period_end)
        by_model = Billing.get_usage_by_model(user_id, period_start, period_end)
        
        # Get subscription info
        sub = Billing.get_user_subscription(user_id)
        sub_dict = sub.model_dump() if sub else None
        
        # Get pending tier info if any
        pending_tier = None
        if sub and sub.pending_tier_id:
            pending_tier = Billing.get_tier_info(sub.pending_tier_id)
        
        return {
            "bill": bill,
            "daily_usage": [d.model_dump() for d in daily_usage],
            "by_model": by_model,
            "period_start": period_start,
            "period_end": period_end,
            "subscription": sub_dict,
            "pending_tier": pending_tier,
        }

    # ========== LOCAL BILLING RUN ==========

    @staticmethod
    def get_users_to_bill(as_of: int | None = None) -> list[dict]:
        """Get list of users whose billing period has ended and need to be charged.
        
        Returns list of {user_id, period_start, period_end, tier_id} for users who:
        - Have an active subscription (not 'none')
        - Have a billing period that ended before `as_of`
        - Have not already been invoiced for that period
        """
        import datetime
        as_of = as_of or int(time.time())
        
        with get_db() as db:
            # Get all active subscriptions
            subs = db.query(UserSubscription).filter(
                UserSubscription.status == "active",
                UserSubscription.tier_id != "none",
            ).all()
            
            to_bill = []
            for sub in subs:
                # Check if billing period has ended
                if sub.current_period_end and sub.current_period_end <= as_of:
                    # Check if already invoiced for this period
                    existing = db.query(BillingInvoice).filter_by(
                        user_id=sub.user_id,
                        period_start=sub.current_period_start,
                    ).first()
                    
                    if not existing:
                        to_bill.append({
                            "user_id": sub.user_id,
                            "period_start": sub.current_period_start,
                            "period_end": sub.current_period_end,
                            "tier_id": sub.tier_id,
                        })
            
            return to_bill

    @staticmethod
    def create_invoice(user_id: str, period_start: int, period_end: int) -> BillingInvoiceModel | None:
        """Create an invoice for a user's billing period.
        
        Returns existing invoice if one already exists for this period (idempotent).
        Returns None if invoice creation fails due to race condition.
        """
        now = int(time.time())
        
        with get_db() as db:
            # Check for existing invoice first (idempotent)
            existing = db.query(BillingInvoice).filter_by(
                user_id=user_id,
                period_start=period_start,
            ).first()
            
            if existing:
                # Already invoiced - return existing (prevents double-invoice)
                return BillingInvoiceModel.model_validate(existing)
            
            # Calculate the bill
            bill = Billing.calculate_monthly_bill(user_id, period_start, period_end)
            
            try:
                invoice = BillingInvoice(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    period_start=period_start,
                    period_end=period_end,
                    tier_id=bill["tier_id"],
                    tier_name=bill["tier_name"],
                    base_price_cents=bill["base_price_cents"],
                    tokens_included=bill["tokens_included"],
                    tokens_used=bill["tokens_used"],
                    tokens_overage=bill["tokens_overage"],
                    overage_cost_cents=bill["overage_cost_cents"],
                    total_amount_cents=bill["total_cost_cents"],
                    status="pending",
                    retry_count=0,
                    created_at=now,
                    updated_at=now,
                )
                db.add(invoice)
                db.commit()
                db.refresh(invoice)
                return BillingInvoiceModel.model_validate(invoice)
            except Exception as e:
                # Unique constraint violation or other error - check if invoice was created
                db.rollback()
                existing = db.query(BillingInvoice).filter_by(
                    user_id=user_id,
                    period_start=period_start,
                ).first()
                if existing:
                    # Race condition - another process created it first
                    return BillingInvoiceModel.model_validate(existing)
                raise  # Re-raise if it's a different error

    @staticmethod
    def charge_invoice(invoice_id: str, stripe_api_key: str) -> dict:
        """Charge a pending invoice using the user's stored payment method.
        
        Returns {"success": bool, "error": str|None, "payment_intent_id": str|None}
        """
        import stripe
        stripe.api_key = stripe_api_key
        
        with get_db() as db:
            invoice = db.query(BillingInvoice).filter_by(id=invoice_id).first()
            if not invoice:
                return {"success": False, "error": "Invoice not found"}
            
            if invoice.status == "paid":
                return {"success": True, "error": None, "payment_intent_id": invoice.stripe_payment_intent_id}
            
            if invoice.total_amount_cents <= 0:
                # No charge needed (free tier or no usage)
                invoice.status = "paid"
                invoice.paid_at = int(time.time())
                invoice.updated_at = int(time.time())
                db.commit()
                return {"success": True, "error": None, "payment_intent_id": None}
            
            # Get user's Stripe customer ID and payment method
            from open_webui.models.users import Users
            user = Users.get_user_by_id(invoice.user_id)
            if not user:
                invoice.status = "failed"
                invoice.failure_reason = "User not found"
                invoice.updated_at = int(time.time())
                db.commit()
                return {"success": False, "error": "User not found"}
            
            info = user.info or {}
            customer_id = info.get("stripe_customer_id")
            if not customer_id:
                invoice.status = "failed"
                invoice.failure_reason = "No Stripe customer ID"
                invoice.updated_at = int(time.time())
                db.commit()
                return {"success": False, "error": "No Stripe customer ID"}
            
            try:
                # Get default payment method
                payment_methods = stripe.PaymentMethod.list(
                    customer=customer_id,
                    type="card",
                    limit=1,
                )
                
                if not payment_methods.data:
                    invoice.status = "failed"
                    invoice.failure_reason = "No payment method on file"
                    invoice.retry_count += 1
                    invoice.updated_at = int(time.time())
                    db.commit()
                    return {"success": False, "error": "No payment method on file"}
                
                payment_method = payment_methods.data[0].id
                
                # Create and confirm payment intent with idempotency key
                # The idempotency key ensures the same charge is never processed twice
                idempotency_key = f"invoice_{invoice.id}"
                
                payment_intent = stripe.PaymentIntent.create(
                    amount=invoice.total_amount_cents,
                    currency="usd",
                    customer=customer_id,
                    payment_method=payment_method,
                    off_session=True,
                    confirm=True,
                    description=f"Autotech AI - {invoice.tier_name} ({invoice.period_start} - {invoice.period_end})",
                    metadata={
                        "invoice_id": invoice.id,
                        "user_id": invoice.user_id,
                        "period_start": str(invoice.period_start),
                        "period_end": str(invoice.period_end),
                    },
                    idempotency_key=idempotency_key,
                )
                
                invoice.stripe_payment_intent_id = payment_intent.id
                if payment_intent.latest_charge:
                    invoice.stripe_charge_id = payment_intent.latest_charge
                invoice.status = "paid"
                invoice.paid_at = int(time.time())
                invoice.updated_at = int(time.time())
                db.commit()
                
                return {"success": True, "error": None, "payment_intent_id": payment_intent.id}
                
            except stripe.error.CardError as e:
                invoice.status = "failed"
                invoice.failure_reason = str(e.user_message or e)
                invoice.retry_count += 1
                invoice.updated_at = int(time.time())
                db.commit()
                return {"success": False, "error": str(e.user_message or e)}
                
            except stripe.error.StripeError as e:
                invoice.status = "failed"
                invoice.failure_reason = str(e)
                invoice.retry_count += 1
                invoice.updated_at = int(time.time())
                db.commit()
                return {"success": False, "error": str(e)}

    @staticmethod
    def advance_billing_period(user_id: str) -> UserSubscriptionModel | None:
        """Advance user's subscription to the next billing period.
        
        If there's a pending tier change, apply it now.
        """
        import datetime
        now = int(time.time())
        
        with get_db() as db:
            sub = db.query(UserSubscription).filter_by(user_id=user_id).first()
            if not sub or sub.tier_id == "none":
                return None
            
            # Apply pending tier change if any
            if sub.pending_tier_id:
                sub.tier_id = sub.pending_tier_id
                sub.pending_tier_id = None
            
            # Calculate next period
            if sub.current_period_end:
                # Next period starts where this one ended
                new_start = sub.current_period_end
            else:
                new_start = now
            
            # Calculate period end (1 month later)
            dt = datetime.datetime.utcfromtimestamp(new_start)
            if dt.month == 12:
                next_month = datetime.datetime(dt.year + 1, 1, dt.day, dt.hour, dt.minute, dt.second)
            else:
                # Handle months with fewer days
                try:
                    next_month = datetime.datetime(dt.year, dt.month + 1, dt.day, dt.hour, dt.minute, dt.second)
                except ValueError:
                    # Day doesn't exist in next month, use last day
                    import calendar
                    last_day = calendar.monthrange(dt.year, dt.month + 1)[1]
                    next_month = datetime.datetime(dt.year, dt.month + 1, last_day, dt.hour, dt.minute, dt.second)
            
            new_end = int(next_month.timestamp())
            
            sub.current_period_start = new_start
            sub.current_period_end = new_end
            sub.updated_at = now
            db.commit()
            db.refresh(sub)
            return UserSubscriptionModel.model_validate(sub)

    @staticmethod
    def grant_monthly_tokens(user_id: str, tier_id: str) -> int:
        """Grant monthly token allocation for a tier.
        
        Returns the number of tokens granted.
        """
        from open_webui.env import BILLING_TIERS
        
        tier = BILLING_TIERS.get(tier_id, {})
        tokens_to_grant = tier.get("tokens_included", 0)
        
        if tokens_to_grant <= 0:
            return 0
        
        with get_db() as db:
            bal = db.query(UserTokenBalance).filter_by(user_id=user_id).first()
            if bal:
                bal.tokens_balance += tokens_to_grant
                bal.updated_at = int(time.time())
            else:
                bal = UserTokenBalance(
                    user_id=user_id,
                    tokens_balance=tokens_to_grant,
                    updated_at=int(time.time()),
                )
                db.add(bal)
            db.commit()
        
        return tokens_to_grant

    @staticmethod
    def run_billing(stripe_api_key: str, as_of: int | None = None) -> dict:
        """Run billing for all users whose period has ended.
        
        Uses a file lock to prevent concurrent billing runs.
        
        Returns summary: {
            "checked": int,
            "invoiced": int,
            "charged": int,
            "failed": int,
            "skipped": int,
            "details": [...]
        }
        """
        import logging
        import fcntl
        log = logging.getLogger(__name__)
        
        # File-based lock to prevent concurrent billing runs
        lock_file = "/tmp/autotech_billing.lock"
        lock_fd = None
        
        try:
            lock_fd = open(lock_file, "w")
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            log.warning("Billing run already in progress, skipping")
            if lock_fd:
                lock_fd.close()
            return {
                "checked": 0,
                "invoiced": 0,
                "charged": 0,
                "failed": 0,
                "skipped": 0,
                "details": [],
                "error": "Billing run already in progress",
            }
        
        try:
            as_of = as_of or int(time.time())
            users_to_bill = Billing.get_users_to_bill(as_of)
            
            results = {
                "checked": len(users_to_bill),
                "invoiced": 0,
                "charged": 0,
                "failed": 0,
                "skipped": 0,
                "details": [],
            }
            
            for user_info in users_to_bill:
                user_id = user_info["user_id"]
                period_start = user_info["period_start"]
                period_end = user_info["period_end"]
                
                detail = {"user_id": user_id, "period_start": period_start, "period_end": period_end}
                
                try:
                    # Create invoice
                    invoice = Billing.create_invoice(user_id, period_start, period_end)
                    results["invoiced"] += 1
                    detail["invoice_id"] = invoice.id
                    detail["amount_cents"] = invoice.total_amount_cents
                    
                    # Charge invoice
                    charge_result = Billing.charge_invoice(invoice.id, stripe_api_key)
                    
                    if charge_result["success"]:
                        results["charged"] += 1
                        detail["status"] = "paid"
                        detail["payment_intent_id"] = charge_result.get("payment_intent_id")
                        
                        # Advance to next billing period
                        new_sub = Billing.advance_billing_period(user_id)
                        
                        # Grant monthly token allocation
                        if new_sub:
                            tokens_to_grant = Billing.grant_monthly_tokens(user_id, new_sub.tier_id)
                            detail["tokens_granted"] = tokens_to_grant
                    else:
                        results["failed"] += 1
                        detail["status"] = "failed"
                        detail["error"] = charge_result.get("error")
                        
                except Exception as e:
                    log.exception(f"Error billing user {user_id}")
                    results["failed"] += 1
                    detail["status"] = "error"
                    detail["error"] = str(e)
                
                results["details"].append(detail)
            
            return results
        finally:
            # Release lock
            if lock_fd:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()

    @staticmethod
    def get_user_invoices(user_id: str, limit: int = 12) -> list[BillingInvoiceModel]:
        """Get user's invoice history."""
        with get_db() as db:
            invoices = (
                db.query(BillingInvoice)
                .filter_by(user_id=user_id)
                .order_by(BillingInvoice.period_start.desc())
                .limit(limit)
                .all()
            )
            return [BillingInvoiceModel.model_validate(inv) for inv in invoices]

    @staticmethod
    def get_pending_invoices() -> list[BillingInvoiceModel]:
        """Get all pending/failed invoices for admin review."""
        with get_db() as db:
            invoices = (
                db.query(BillingInvoice)
                .filter(BillingInvoice.status.in_(["pending", "failed"]))
                .order_by(BillingInvoice.created_at.desc())
                .all()
            )
            return [BillingInvoiceModel.model_validate(inv) for inv in invoices]


# Expose simple API for other modules
record_usage_event = Billing.record_usage_event
get_user_balance = Billing.get_user_balance
has_user_balance_record = Billing.has_user_balance_record
get_auto_renew_settings = Billing.get_auto_renew_settings
set_auto_renew_settings = Billing.set_auto_renew_settings
purchase_tokens = Billing.purchase_tokens
confirm_purchase = Billing.confirm_purchase
reconcile_one = Billing.reconcile_one
reconcile_pending_purchases = Billing.reconcile_pending_purchases

# Subscription management
get_user_subscription = Billing.get_user_subscription
set_user_subscription = Billing.set_user_subscription
get_tier_info = Billing.get_tier_info
get_all_tiers = Billing.get_all_tiers
calculate_monthly_bill = Billing.calculate_monthly_bill

# Usage analytics
get_daily_usage = Billing.get_daily_usage
get_usage_by_model = Billing.get_usage_by_model
get_usage_summary = Billing.get_usage_summary



def list_user_token_usage(period_start: int, period_end: int, page: int = 1, page_size: int = 50) -> tuple[list[UserTokenUsageModel], int]:
    """Return a paginated list of UserTokenUsageModel for the given period and the total count."""
    with get_db() as db:
        query = db.query(UserTokenUsage).filter_by(period_start=period_start, period_end=period_end)
        total = query.count()
        items = (
            query.order_by(UserTokenUsage.tokens_total.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return ([UserTokenUsageModel.model_validate(item) for item in items], int(total))


def list_token_purchases(status: str | None = None, page: int = 1, page_size: int = 50) -> tuple[list[TokenPurchaseModel], int]:
    """Return a paginated list of TokenPurchaseModel filtered by status and the total count."""
    with get_db() as db:
        query = db.query(TokenPurchase)
        if status:
            query = query.filter_by(status=status)
        total = query.count()
        items = (
            query.order_by(TokenPurchase.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return ([TokenPurchaseModel.model_validate(item) for item in items], int(total))


def compute_cost_for_tokens(tokens_total: int, rate_per_token: float) -> str:
    """Return formatted cost string for tokens at given per-token USD rate."""
    cost = float(tokens_total or 0) * float(rate_per_token)
    return f"{cost:.6f}"


def check_and_trigger_auto_renew(user_id: str) -> dict | None:
    """Check if user's balance is <= 0 and auto-renew is enabled. If so, trigger an automatic charge.
    
    Returns a dict with the result or None if no action was taken.
    This should be called asynchronously after recording usage.
    """
    import logging
    log = logging.getLogger(__name__)
    
    with get_db() as db:
        bal = db.query(UserTokenBalance).filter_by(user_id=user_id).first()
        if not bal:
            return None
        
        # Check if auto-renew should trigger
        if not bal.auto_renew_enabled or bal.auto_renew_tokens <= 0:
            return None
        
        if bal.tokens_balance > 0:
            return None  # Still have tokens, no need to renew
        
        # Check if there's already a pending auto-renew purchase in the last 5 minutes
        # to avoid duplicate charges
        five_mins_ago = int(time.time()) - 300
        pending = db.query(TokenPurchase).filter(
            TokenPurchase.user_id == user_id,
            TokenPurchase.status == "pending",
            TokenPurchase.created_at >= five_mins_ago
        ).first()
        if pending:
            log.info(f"Auto-renew skipped for user {user_id}: pending purchase exists")
            return {"action": "skipped", "reason": "pending_purchase_exists"}
    
    # Trigger the auto-charge outside the DB context
    return _execute_auto_renew(user_id, bal.auto_renew_tokens)


def _execute_auto_renew(user_id: str, tokens: int) -> dict:
    """Execute the automatic token purchase using the user's saved payment method."""
    import logging
    log = logging.getLogger(__name__)
    
    stripe_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_key:
        log.warning(f"Auto-renew failed for user {user_id}: Stripe not configured")
        return {"action": "failed", "reason": "stripe_not_configured"}
    
    try:
        import stripe
        stripe.api_key = stripe_key
        
        # Get user's Stripe customer ID
        from open_webui.models.users import Users
        u = Users.get_user_by_id(user_id)
        if not u:
            return {"action": "failed", "reason": "user_not_found"}
        
        info = u.info or {}
        customer_id = info.get("stripe_customer_id")
        if not customer_id:
            log.warning(f"Auto-renew failed for user {user_id}: no Stripe customer ID")
            return {"action": "failed", "reason": "no_stripe_customer"}
        
        # Get the token rate from env
        rate = float(os.environ.get("BILLING_TOKEN_USD_RATE", "0.00003"))
        from decimal import Decimal, ROUND_HALF_UP
        amount_cents = int((Decimal(int(tokens)) * Decimal(str(rate)) * Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        ))
        amount_cents = max(50, amount_cents)  # Stripe minimum is $0.50
        
        computed_cost = f"{(Decimal(amount_cents) / Decimal('100')):.2f}"
        
        # Create a pending purchase record
        tp = purchase_tokens(
            user_id=user_id,
            tokens=tokens,
            cost=computed_cost,
            currency="USD",
            status="pending"
        )
        
        # Get customer's default payment method
        customer = stripe.Customer.retrieve(customer_id)
        default_pm = customer.get("invoice_settings", {}).get("default_payment_method")
        
        if not default_pm:
            # Try to find any attached payment method
            pms = stripe.PaymentMethod.list(customer=customer_id, type="card", limit=1)
            if pms.data:
                default_pm = pms.data[0].id
        
        if not default_pm:
            log.warning(f"Auto-renew failed for user {user_id}: no payment method")
            return {"action": "failed", "reason": "no_payment_method", "purchase_id": tp.id}
        
        # Create and confirm a PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            customer=customer_id,
            payment_method=default_pm,
            off_session=True,
            confirm=True,
            metadata={"purchase_id": tp.id, "user_id": user_id, "auto_renew": "true"},
            description=f"Auto-renew: {tokens} tokens"
        )
        
        if intent.status == "succeeded":
            # Confirm the purchase to credit the balance
            confirm_purchase(tp.id, stripe_payment_id=intent.id)
            log.info(f"Auto-renew succeeded for user {user_id}: {tokens} tokens, ${computed_cost}")
            return {"action": "succeeded", "tokens": tokens, "cost": computed_cost, "purchase_id": tp.id}
        else:
            log.warning(f"Auto-renew payment not succeeded for user {user_id}: {intent.status}")
            return {"action": "failed", "reason": f"payment_status_{intent.status}", "purchase_id": tp.id}
            
    except stripe.error.CardError as e:
        log.warning(f"Auto-renew card error for user {user_id}: {e.user_message}")
        # Optionally disable auto-renew on card failure
        set_auto_renew_settings(user_id, False, 0)
        return {"action": "failed", "reason": "card_declined", "message": e.user_message}
    except Exception as e:
        log.exception(f"Auto-renew error for user {user_id}")
        return {"action": "failed", "reason": str(e)}

