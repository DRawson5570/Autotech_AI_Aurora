import { WEBUI_API_BASE_URL } from '$lib/constants';

export const createBillingPortal = async (token: string) => {
  let error = null;

  const res = await fetch(`${WEBUI_API_BASE_URL}/billing/portal`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { authorization: `Bearer ${token}` }),
    },
  })
    .then(async (res) => {
      if (!res.ok) throw await res.json();
      return res.json();
    })
    .catch((err) => {
      console.error(err);
      error = err.detail;
      return null;
    });

  if (error) throw error;
  return res;
};

export async function createCheckoutSession(tokens: number, cost: string, token?: string) {
  const res = await fetch(`${WEBUI_API_BASE_URL}/billing/user/create_checkout_session`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { authorization: `Bearer ${token}` }),
    },
    body: JSON.stringify({ tokens, cost, currency: 'USD' }),
  });

  const bodyText = await res.text();
  let bodyJson: any = null;
  try {
    bodyJson = bodyText ? JSON.parse(bodyText) : null;
  } catch {
    bodyJson = null;
  }

  if (!res.ok) {
    const message = bodyJson?.detail || bodyJson?.message || bodyText || `API error ${res.status}`;
    throw new Error(message);
  }

  if (bodyJson) return bodyJson;
  throw new Error('Empty response from server');
}

export async function getTokenPricing(token?: string): Promise<{ token_usd_rate: number; token_bundles?: number[] }> {
  const endpoints = token
    ? [`${WEBUI_API_BASE_URL}/billing/user/token_pricing`, `${WEBUI_API_BASE_URL}/billing/public/token_pricing`]
    : [`${WEBUI_API_BASE_URL}/billing/public/token_pricing`];

  let lastError: unknown = null;
  for (const url of endpoints) {
    try {
      const res = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...(token && url.includes('/billing/user/') && { authorization: `Bearer ${token}` })
        },
        credentials: 'include'
      });

      if (!res.ok) {
        const text = await res.text();
        let detail: any = null;
        try {
          detail = JSON.parse(text);
        } catch {
          // ignore
        }
        throw new Error(detail?.detail || detail?.message || `API error ${res.status}`);
      }

      return await res.json();
    } catch (e) {
      lastError = e;
    }
  }

  throw lastError instanceof Error ? lastError : new Error('Failed to load token pricing');
}

export const confirmCheckoutSession = async (
  params: { session_id?: string | null; purchase_id?: string | null },
  token?: string
) => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/user/confirm_checkout`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		},
    body: JSON.stringify({
      session_id: params?.session_id ?? undefined,
      purchase_id: params?.purchase_id ?? undefined
    })
	});

	if (!res.ok) {
		const text = await res.text();
		let detail: any = null;
		try {
			detail = JSON.parse(text);
		} catch {
			// ignore
		}
		throw new Error(detail?.detail || detail?.message || `API error ${res.status}`);
	}

	return await res.json();
};

export async function getAutoRenewSettings(token?: string): Promise<{ auto_renew_enabled: boolean; auto_renew_tokens: number }> {
	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/user/auto_renew`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	});

	if (!res.ok) {
		const text = await res.text();
		let detail: any = null;
		try {
			detail = JSON.parse(text);
		} catch {
			// ignore
		}
		throw new Error(detail?.detail || detail?.message || `API error ${res.status}`);
	}

	return await res.json();
}

export async function setAutoRenewSettings(
	enabled: boolean,
	tokens: number,
	token?: string
): Promise<{ auto_renew_enabled: boolean; auto_renew_tokens: number }> {
	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/user/auto_renew`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		},
		body: JSON.stringify({ enabled, tokens })
	});

	if (!res.ok) {
		const text = await res.text();
		let detail: any = null;
		try {
			detail = JSON.parse(text);
		} catch {
			// ignore
		}
		throw new Error(detail?.detail || detail?.message || `API error ${res.status}`);
	}

	return await res.json();
}

// ===== TIERED BILLING API FUNCTIONS =====

export interface BillingStatus {
	has_billing_setup: boolean;
	has_payment_method: boolean;
	stripe_configured: boolean;
	is_trial?: boolean;
	customer_id?: string;
	message: string;
}

export async function getBillingStatus(token?: string): Promise<BillingStatus> {
	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/user/billing-status`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	});

	if (!res.ok) {
		const text = await res.text();
		let detail: any = null;
		try { detail = JSON.parse(text); } catch { /* ignore */ }
		throw new Error(detail?.detail || detail?.message || `API error ${res.status}`);
	}

	return await res.json();
}

export interface SubscriptionTier {
	name: string;
	monthly_price_cents: number;
	tokens_included: number;
	overage_rate_per_1k_cents: number;
}

export interface UserSubscription {
	user_id: string;
	tier_id: string;
	pending_tier_id: string | null;
	stripe_subscription_id: string | null;
	current_period_start: number | null;
	current_period_end: number | null;
	status: string;
	created_at: number;
	updated_at: number;
}

export interface MonthlyBill {
	tier_id: string;
	tier_name: string;
	base_price_cents: number;
	tokens_included: number;
	tokens_used: number;
	tokens_overage: number;
	overage_rate_per_1k_cents: number;
	overage_cost_cents: number;
	total_cost_cents: number;
	usage_percent: number;
}

export interface DailyUsage {
	id: string;
	user_id: string;
	date: string;
	model_id: string | null;
	tokens_prompt: number;
	tokens_completion: number;
	tokens_total: number;
	request_count: number;
	created_at: number;
	updated_at: number;
}

export interface UsageByModel {
	model_id: string;
	tokens_total: number;
	request_count: number;
}

export interface UsageSummary {
	bill: MonthlyBill;
	daily_usage: DailyUsage[];
	by_model: UsageByModel[];
	period_start: string;
	period_end: string;
	subscription: UserSubscription | null;
	pending_tier: SubscriptionTier | null;
}

export async function getSubscriptionTiers(token?: string): Promise<{ tiers: Record<string, SubscriptionTier> }> {
	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/tiers`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	});

	if (!res.ok) {
		const text = await res.text();
		let detail: any = null;
		try { detail = JSON.parse(text); } catch { /* ignore */ }
		throw new Error(detail?.detail || detail?.message || `API error ${res.status}`);
	}

	return await res.json();
}

export async function getUserSubscription(token?: string): Promise<{
	subscription: UserSubscription | null;
	tier: SubscriptionTier | null;
	default_tier?: string;
}> {
	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/user/subscription`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	});

	if (!res.ok) {
		const text = await res.text();
		let detail: any = null;
		try { detail = JSON.parse(text); } catch { /* ignore */ }
		throw new Error(detail?.detail || detail?.message || `API error ${res.status}`);
	}

	return await res.json();
}

export async function setUserSubscription(tierId: string, token?: string): Promise<{
	subscription: UserSubscription;
	tier: SubscriptionTier;
	pending_tier?: SubscriptionTier;
	message?: string;
}> {
	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/user/subscription`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		},
		body: JSON.stringify({ tier_id: tierId })
	});

	if (!res.ok) {
		const text = await res.text();
		let detail: any = null;
		try { detail = JSON.parse(text); } catch { /* ignore */ }
		throw new Error(detail?.detail || detail?.message || `API error ${res.status}`);
	}

	return await res.json();
}

export async function createSubscriptionCheckout(tierId: string, token?: string): Promise<{
	url: string;
	session_id: string;
}> {
	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/user/subscription/checkout`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		},
		body: JSON.stringify({ tier_id: tierId })
	});

	if (!res.ok) {
		const text = await res.text();
		let detail: any = null;
		try { detail = JSON.parse(text); } catch { /* ignore */ }
		throw new Error(detail?.detail || detail?.message || `API error ${res.status}`);
	}

	return await res.json();
}

export async function confirmSubscriptionCheckout(sessionId: string, token?: string): Promise<{
	success: boolean;
	subscription: UserSubscription;
	tier: SubscriptionTier;
	tokens_granted: number;
	message: string;
}> {
	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/user/subscription/confirm?session_id=${encodeURIComponent(sessionId)}`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	});

	if (!res.ok) {
		const text = await res.text();
		let detail: any = null;
		try { detail = JSON.parse(text); } catch { /* ignore */ }
		throw new Error(detail?.detail || detail?.message || `API error ${res.status}`);
	}

	return await res.json();
}

export async function getMonthlyBill(token?: string): Promise<MonthlyBill> {
	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/user/bill`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	});

	if (!res.ok) {
		const text = await res.text();
		let detail: any = null;
		try { detail = JSON.parse(text); } catch { /* ignore */ }
		throw new Error(detail?.detail || detail?.message || `API error ${res.status}`);
	}

	return await res.json();
}

export async function getUsageSummary(token?: string): Promise<UsageSummary> {
	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/user/usage/summary`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	});

	if (!res.ok) {
		const text = await res.text();
		let detail: any = null;
		try { detail = JSON.parse(text); } catch { /* ignore */ }
		throw new Error(detail?.detail || detail?.message || `API error ${res.status}`);
	}

	return await res.json();
}

export async function getDailyUsage(
	startDate?: string,
	endDate?: string,
	token?: string
): Promise<{ daily_usage: DailyUsage[] }> {
	const params = new URLSearchParams();
	if (startDate) params.set('start_date', startDate);
	if (endDate) params.set('end_date', endDate);

	const url = `${WEBUI_API_BASE_URL}/billing/user/usage/daily${params.toString() ? '?' + params.toString() : ''}`;
	const res = await fetch(url, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	});

	if (!res.ok) {
		const text = await res.text();
		let detail: any = null;
		try { detail = JSON.parse(text); } catch { /* ignore */ }
		throw new Error(detail?.detail || detail?.message || `API error ${res.status}`);
	}

	return await res.json();
}

export async function getUsageByModel(
	startDate?: string,
	endDate?: string,
	token?: string
): Promise<{ by_model: UsageByModel[] }> {
	const params = new URLSearchParams();
	if (startDate) params.set('start_date', startDate);
	if (endDate) params.set('end_date', endDate);

	const url = `${WEBUI_API_BASE_URL}/billing/user/usage/by_model${params.toString() ? '?' + params.toString() : ''}`;
	const res = await fetch(url, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	});

	if (!res.ok) {
		const text = await res.text();
		let detail: any = null;
		try { detail = JSON.parse(text); } catch { /* ignore */ }
		throw new Error(detail?.detail || detail?.message || `API error ${res.status}`);
	}

	return await res.json();
}

export interface OverageStatus {
	in_overage: boolean;
	current_tier?: string;
	tokens_over?: number;
	projected_overage_cost?: number;
	upgrade_tier?: string | null;
	upgrade_tier_name?: string | null;
	upgrade_price?: number | null;
	projected_total_current?: number;
	projected_total_upgrade?: number | null;
	savings?: number | null;
}

export async function getOverageStatus(token: string): Promise<OverageStatus> {
	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/user/overage-status`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	});

	if (!res.ok) {
		const text = await res.text();
		let detail: any = null;
		try { detail = JSON.parse(text); } catch { /* ignore */ }
		throw new Error(detail?.detail || detail?.message || `API error ${res.status}`);
	}

	return await res.json();
}
