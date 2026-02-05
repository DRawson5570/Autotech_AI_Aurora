<script lang="ts">
  import { onMount } from 'svelte';
  import { listUsage, exportUsageCsv, dryRunInvoice, grantTrialTokens, getTokenPricing, updateTokenPricing, listSubscriptions } from '$lib/apis/billing/usage';
  import { toast } from 'svelte-sonner';
  import { user } from '$lib/stores';

  let period = null; // format YYYY-MM
  let page = 1;
  let page_size = 50;
  let items = [];
  let total = 0;
  let loading = false;
  let dryRunLoading = false;
  let dryRunResult = null;
  let showDryRun = false;

  // Subscriptions
  let subscriptions: any[] = [];
  let subscriptionsLoading = false;

  // Token pricing (admin-configurable)
  let tokenUsdRate: number | null = null;
  let tokenUsdRateLoading = false;
  let tokenUsdRateSaving = false;

  const getAuthToken = () => localStorage?.token ?? $user?.token;

  async function loadTokenPricing() {
    tokenUsdRateLoading = true;
    try {
      const authToken = getAuthToken();
      const res = await getTokenPricing(authToken);
      const next = Number(res?.token_usd_rate);
      tokenUsdRate = Number.isFinite(next) ? next : null;
    } catch (e) {
      tokenUsdRate = null;
    } finally {
      tokenUsdRateLoading = false;
    }
  }

  async function saveTokenPricing() {
    const next = Number(tokenUsdRate);
    if (!Number.isFinite(next) || next <= 0) {
      toast.error('Enter a token USD rate > 0');
      return;
    }

    tokenUsdRateSaving = true;
    try {
      const authToken = getAuthToken();
      const res = await updateTokenPricing(next, authToken);
      const confirmed = Number(res?.token_usd_rate);
      tokenUsdRate = Number.isFinite(confirmed) ? confirmed : next;
      toast.success('Token pricing updated');
      await load();
    } catch (e) {
      console.error(e);
      const message = e instanceof Error ? e.message : 'Failed to update token pricing';
      toast.error(message || 'Failed to update token pricing');
    } finally {
      tokenUsdRateSaving = false;
    }
  }

  // Trial tokens
  let trialEmail = '';
  let trialTokens: number | null = null;
  let trialLoading = false;

  async function handleGrantTrialTokens() {
    const email = (trialEmail || '').trim();
    const tokens = Number(trialTokens);

    if (!email) {
      toast.error('Enter a user email');
      return;
    }
    if (!Number.isFinite(tokens) || tokens <= 0) {
      toast.error('Enter a token amount > 0');
      return;
    }

    trialLoading = true;
    try {
      const authToken = localStorage?.token ?? $user?.token;
      const res = await grantTrialTokens({ email, tokens }, authToken);
      toast.success(`Granted ${res.granted_tokens} tokens to ${res.email} (balance: ${res.tokens_balance})`);
      await load();
    } catch (e) {
      console.error(e);
      const message = e instanceof Error ? e.message : 'Failed to grant trial tokens';
      toast.error(message || 'Failed to grant trial tokens');
    } finally {
      trialLoading = false;
    }
  }

  async function load() {
    loading = true;
    try {
      const authToken = getAuthToken();
      const res = await listUsage(period, page, page_size, authToken);
      items = res.items;
      total = res.total;

      // Prefer displaying the server-provided rate in the pricing input (if not set yet)
      if (tokenUsdRate === null) {
        const rateFromServer = Number(res?.rate);
        if (Number.isFinite(rateFromServer) && rateFromServer > 0) tokenUsdRate = rateFromServer;
      }
    } catch (e) {
      console.error(e);
      toast.error('Failed to load billing data');
    } finally {
      loading = false;
    }
  }

  async function exportCsv() {
    try {
      const authToken = getAuthToken();
      const blob = await exportUsageCsv(period, authToken);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `usage_${period || 'current'}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
      toast.error('Export failed');
    }
  }

  async function handleDryRun() {
    dryRunLoading = true;
    dryRunResult = null;
    try {
      const authToken = getAuthToken();
      const res = await dryRunInvoice(period, undefined, authToken);
      dryRunResult = res;
      showDryRun = true;
    } catch (e) {
      console.error(e);
      toast.error('Dry-run failed');
    } finally {
      dryRunLoading = false;
    }
  }

  async function loadSubscriptions() {
    subscriptionsLoading = true;
    try {
      const authToken = getAuthToken();
      const res = await listSubscriptions(authToken);
      subscriptions = res.subscriptions || [];
    } catch (e) {
      console.error(e);
      toast.error('Failed to load subscriptions');
    } finally {
      subscriptionsLoading = false;
    }
  }

  // Filter out orphaned users (those showing as UUIDs)
  function isOrphanedUser(item: any): boolean {
    const display = item.name || item.email || item.user_id;
    // UUID pattern check - if the display is a UUID, it's orphaned
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(display);
  }

  $: filteredItems = items.filter(it => !isOrphanedUser(it));

  onMount(() => {
    loadTokenPricing();
    load();
    loadSubscriptions();
  });
</script>

<div class="p-4">
  <div class="flex items-center justify-between mb-4">
    <div class="flex items-center gap-2">
      <label class="text-sm">Period (YYYY-MM)</label>
      <input class="border rounded px-2 py-1" bind:value={period} placeholder="2024-12" />
      <button class="btn" on:click={() => { page = 1; load(); }}>Load</button>
    </div>
    <div>
      <button class="btn mr-2" on:click={exportCsv}>Export CSV</button>
      <button class="btn" on:click={handleDryRun} disabled={dryRunLoading}>
        {#if dryRunLoading}Running…{:else}Dry-run Invoice{/if}
      </button>
    </div>
  </div>

  <div class="mb-4 flex items-center gap-2">
    <div class="font-semibold">Token Price (USD per token)</div>
    <input
      class="border rounded px-2 py-1 w-48"
      type="number"
      min="0"
      step="0.000001"
      bind:value={tokenUsdRate}
      placeholder="0.00002"
      disabled={tokenUsdRateLoading}
    />
    <button class="btn" on:click={saveTokenPricing} disabled={tokenUsdRateSaving || tokenUsdRateLoading}>
      {#if tokenUsdRateSaving}Saving…{:else}Save{/if}
    </button>
  </div>

  <div class="mb-4 flex items-center gap-2">
    <div class="font-semibold">Grant Trial Tokens</div>
    <input class="border rounded px-2 py-1" bind:value={trialEmail} placeholder="user@email.com" />
    <input class="border rounded px-2 py-1 w-32" type="number" min="1" step="1" bind:value={trialTokens} placeholder="Tokens" />
    <button class="btn" on:click={handleGrantTrialTokens} disabled={trialLoading}>
      {#if trialLoading}Granting…{:else}Grant{/if}
    </button>
  </div>

  {#if loading}
    <div>Loading…</div>
  {:else}
    <!-- User Subscriptions Table -->
    <div class="mb-6 p-4 border rounded bg-white dark:bg-gray-900">
      <div class="flex items-center justify-between mb-2">
        <div class="font-semibold">User Subscriptions</div>
        <button class="btn" on:click={loadSubscriptions} disabled={subscriptionsLoading}>
          {#if subscriptionsLoading}Loading…{:else}Refresh{/if}
        </button>
      </div>
      {#if subscriptionsLoading}
        <div>Loading…</div>
      {:else if subscriptions.length === 0}
        <div class="text-gray-500">No subscriptions found</div>
      {:else}
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left">
              <th>User</th>
              <th>Plan</th>
              <th>Tokens Used</th>
              <th>Token Balance</th>
              <th>Renew Date</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {#each subscriptions as sub}
              <tr>
                <td>{sub.name || sub.email}</td>
                <td>{sub.tier_name}{#if sub.pending_tier_id} <span class="text-xs text-amber-500">(→{sub.pending_tier_id})</span>{/if}</td>
                <td>{sub.tokens_used?.toLocaleString()} / {sub.tokens_included?.toLocaleString()}</td>
                <td class={sub.token_balance < 0 ? 'text-red-500' : ''}>{sub.token_balance?.toLocaleString()}</td>
                <td>{sub.renew_date || '—'}</td>
                <td>{sub.status}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>

    <!-- Usage Table (Period) -->
    <div class="font-semibold mb-2">Usage by Period</div>
    <table class="w-full text-sm">
      <thead>
        <tr class="text-left">
          <th>User</th>
          <th>Tokens Used (period)</th>
          <th>Token Balance</th>
          <th>Cost (USD)</th>
        </tr>
      </thead>
      <tbody>
        {#each filteredItems as it}
          <tr>
            <td>{it.name || it.email || it.user_id}</td>
            <td>{it.tokens_total}</td>
            <td>{it.tokens_balance ?? '—'}</td>
            <td>{it.cost_total || '—'}</td>
          </tr>
        {/each}
      </tbody>
    </table>

    <div class="mt-4 flex items-center justify-between">
      <div>Showing {filteredItems.length} of {total}</div>
      <div>
        <button class="btn mr-2" on:click={() => { if (page > 1) { page -= 1; load(); } }}>Prev</button>
        <button class="btn" on:click={() => { page += 1; load(); }}>Next</button>
      </div>
    </div>

    {#if showDryRun && dryRunResult}
      <div class="mt-6 p-4 border rounded bg-gray-50 dark:bg-gray-900">
        <div class="flex items-center justify-between mb-2">
          <div class="font-semibold">Dry-run invoice result (period: {period || 'current'})</div>
          <div>Total users: {dryRunResult.total_users} — Tokens: {dryRunResult.grand_total_tokens} — Cost (USD): {dryRunResult.grand_total_cost}</div>
        </div>
        <div class="overflow-auto max-h-64">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left">
                <th>User</th>
                <th>Tokens</th>
                <th>Cost (USD)</th>
              </tr>
            </thead>
            <tbody>
              {#each dryRunResult.items as it}
                <tr>
                  <td>{it.name || it.email || it.user_id}</td>
                  <td>{it.tokens_total}</td>
                  <td>{it.cost_usd}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}
  {/if}
</div>
