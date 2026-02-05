import { WEBUI_API_BASE_URL } from '$lib/constants';

export async function listUsage(period?: string, page = 1, page_size = 50, token?: string) {
  const params = new URLSearchParams();
  if (period) params.set('period', period);
  params.set('page', String(page));
  params.set('page_size', String(page_size));

  const res = await fetch(`${WEBUI_API_BASE_URL}/billing/admin/usage?${params.toString()}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token && { authorization: `Bearer ${token}` }),
    },
  });

  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function exportUsageCsv(period?: string, token?: string) {
  const params = new URLSearchParams();
  if (period) params.set('period', period);

  const res = await fetch(`${WEBUI_API_BASE_URL}/billing/admin/usage/export?${params.toString()}`, {
    headers: {
      ...(token && { authorization: `Bearer ${token}` }),
    },
  });

  if (!res.ok) throw new Error(`API error ${res.status}`);
  const blob = await res.blob();
  return blob;
}

export async function dryRunInvoice(period?: string, rate?: number, token?: string) {
  const params = new URLSearchParams();
  if (period) params.set('period', period);
  if (rate !== undefined) params.set('rate', String(rate));

  const res = await fetch(`${WEBUI_API_BASE_URL}/billing/admin/usage/dry_run?${params.toString()}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { authorization: `Bearer ${token}` }),
    },
  });

  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function getUserBalance(token?: string) {
  const res = await fetch(`${WEBUI_API_BASE_URL}/billing/user/balance`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token && { authorization: `Bearer ${token}` }),
    },
  });

  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function listPurchases(status?: string, page = 1, page_size = 50, token?: string) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  params.set('page', String(page));
  params.set('page_size', String(page_size));

  const res = await fetch(`${WEBUI_API_BASE_URL}/billing/admin/purchases?${params.toString()}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token && { authorization: `Bearer ${token}` }),
    },
  });

  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function reconcilePurchase(purchaseId: string, token?: string) {
  const res = await fetch(`${WEBUI_API_BASE_URL}/billing/admin/purchases/${purchaseId}/reconcile`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { authorization: `Bearer ${token}` }),
    },
  });

  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function reconcileAllPurchases(older_than_seconds?: number, token?: string) {
  const params = new URLSearchParams();
  if (older_than_seconds !== undefined) params.set('older_than_seconds', String(older_than_seconds));

  const res = await fetch(`${WEBUI_API_BASE_URL}/billing/admin/purchases/reconcile_all?${params.toString()}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { authorization: `Bearer ${token}` }),
    },
  });

  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function grantTrialTokens(payload: { user_id?: string; email?: string; tokens: number }, token?: string) {
  const res = await fetch(`${WEBUI_API_BASE_URL}/billing/admin/trial_tokens`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { authorization: `Bearer ${token}` }),
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let detail: string | undefined;
    try {
      const data = await res.json();
      detail = data?.detail ?? data?.message;
      if (typeof detail !== 'string') detail = undefined;
    } catch {
      // ignore
    }
    if (!detail) {
      try {
        const text = await res.text();
        detail = text || undefined;
      } catch {
        // ignore
      }
    }

    throw new Error(detail ? `API error ${res.status}: ${detail}` : `API error ${res.status}`);
  }
  return res.json();
}

export async function getTokenPricing(token?: string) {
  const res = await fetch(`${WEBUI_API_BASE_URL}/billing/admin/token_pricing`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token && { authorization: `Bearer ${token}` }),
    },
  });

  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function updateTokenPricing(token_usd_rate: number, token?: string) {
  const res = await fetch(`${WEBUI_API_BASE_URL}/billing/admin/token_pricing`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { authorization: `Bearer ${token}` }),
    },
    body: JSON.stringify({ token_usd_rate }),
  });

  if (!res.ok) {
    let detail: string | undefined;
    try {
      const data = await res.json();
      detail = data?.detail ?? data?.message;
      if (typeof detail !== 'string') detail = undefined;
    } catch {
      // ignore
    }
    throw new Error(detail ? `API error ${res.status}: ${detail}` : `API error ${res.status}`);
  }
  return res.json();
}

export async function purchaseTokens(tokens: number, cost?: string, currency?: string, token?: string) {
  const body: any = { tokens };
  if (cost !== undefined) body.cost = cost;
  if (currency) body.currency = currency;

  const res = await fetch(`${WEBUI_API_BASE_URL}/billing/user/purchase`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { authorization: `Bearer ${token}` }),
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function listSubscriptions(token?: string) {
  const res = await fetch(`${WEBUI_API_BASE_URL}/billing/admin/subscriptions`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token && { authorization: `Bearer ${token}` }),
    },
  });

  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}
