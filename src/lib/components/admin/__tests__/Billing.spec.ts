/** @vitest-environment jsdom */
import { render, fireEvent, waitFor } from '@testing-library/svelte/svelte5';
import Billing from '../Billing.svelte';
import * as billingApi from '$lib/apis/billing/usage';
import { describe, test, expect, vi } from 'vitest';

let _resolveReconcile: any = null;
vi.mock('$lib/apis/billing/usage', async () => {
  const mod = await vi.importActual<typeof billingApi>('$lib/apis/billing/usage');
  return {
    ...mod,
    listUsage: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    listPurchases: vi.fn().mockResolvedValue({ items: [{ id: 'p1', user_id: 'u1', tokens: 100, cost: '1.00', status: 'pending' }], total: 1 }),
    reconcileAllPurchases: vi.fn().mockImplementation(() => new Promise((res) => { _resolveReconcile = res; })),
    getTokenPricing: vi.fn().mockResolvedValue({ token_usd_rate: 0.00002 }),
    updateTokenPricing: vi.fn().mockResolvedValue({ token_usd_rate: 0.00002 }),
  };
});

describe('Billing admin bulk reconcile', () => {
  test('reconcile all button triggers reconcile and polls until empty', async () => {
    const { getByText, getByRole } = render(Billing);

    // Load pending purchases first
    const loadPendingBtn = getByText('Load Pending');
    await fireEvent.click(loadPendingBtn);
    await waitFor(() => expect(billingApi.listPurchases).toHaveBeenCalled());

    const reconcileBtn = getByRole('button', { name: /Reconcile/ });

    // Click and assert spinner appears while reconcile promise is pending
    await fireEvent.click(reconcileBtn);
    await waitFor(() => getByText('Reconciling…'));

    // Now resolve the reconcile promise with results
    _resolveReconcile({ count: 1, results: [{ purchase_id: 'p1', action: 'confirmed', reason: 'test' }] });

    // Simulate that subsequent listPurchases returns empty after reconcile so polling exits
    (billingApi.listPurchases as any).mockResolvedValueOnce({ items: [], total: 0 });

    // Ensure reconcile helper was called
    await waitFor(() => expect(billingApi.reconcileAllPurchases).toHaveBeenCalled());

    // The per-item status should reflect the reconcile result
    await waitFor(() => getByText('confirmed'));
    await waitFor(() => getByText('p1'));

    // After polling completes, button should be back (Reconcile All text)
    await waitFor(() => getByText('Reconcile All'));
  });
});
