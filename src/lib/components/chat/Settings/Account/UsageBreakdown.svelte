<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		getUsageSummary,
		getSubscriptionTiers,
		setUserSubscription,
		getBillingStatus,
		createBillingPortal,
		createSubscriptionCheckout,
		type UsageSummary,
		type SubscriptionTier,
		type MonthlyBill,
		type BillingStatus
	} from '$lib/apis/billing';

	const i18n = getContext('i18n');

	let loading = true;
	let summary: UsageSummary | null = null;
	let tiers: Record<string, SubscriptionTier> = {};
	let selectedTierId: string = '';
	let changingTier = false;
	let billingStatus: BillingStatus | null = null;
	let settingUpBilling = false;

	const getAuthToken = () => localStorage?.token ?? '';

	const formatCents = (cents: number): string => {
		return `$${(cents / 100).toFixed(2)}`;
	};

	const formatTokens = (tokens: number): string => {
		if (tokens >= 1000000) {
			return `${(tokens / 1000000).toFixed(1)}M`;
		} else if (tokens >= 1000) {
			return `${(tokens / 1000).toFixed(0)}K`;
		}
		return tokens.toLocaleString();
	};

	const getUsageBarColor = (percent: number): string => {
		if (percent >= 100) return 'bg-red-500';
		if (percent >= 80) return 'bg-yellow-500';
		return 'bg-teal-500';
	};

	const loadData = async () => {
		loading = true;
		try {
			const authToken = getAuthToken();
			const [summaryRes, tiersRes, statusRes] = await Promise.all([
				getUsageSummary(authToken),
				getSubscriptionTiers(authToken),
				getBillingStatus(authToken)
			]);
			summary = summaryRes;
			tiers = tiersRes.tiers || {};
			billingStatus = statusRes;
			// Only pre-select if user has an actual plan (not 'none' or empty)
			const currentTier = summary?.bill?.tier_id;
			selectedTierId = (currentTier && currentTier !== 'none') ? currentTier : '';
		} catch (err) {
			console.error('Failed to load usage data:', err);
			toast.error($i18n.t('Failed to load usage data'));
		} finally {
			loading = false;
		}
	};

	const handleSetupBilling = async () => {
		settingUpBilling = true;
		try {
			const res = await createBillingPortal(getAuthToken());
			if (res?.url) {
				window.location.href = res.url;
			} else {
				toast.error($i18n.t('Failed to open billing setup'));
			}
		} catch (err: any) {
			console.error('Failed to open billing portal:', err);
			toast.error(err?.message || $i18n.t('Failed to open billing setup'));
		} finally {
			settingUpBilling = false;
		}
	};

	const handleChangeTier = async () => {
		if (!selectedTierId || changingTier) return;
		
		// Check if billing is set up first
		if (billingStatus?.stripe_configured && !billingStatus?.has_payment_method) {
			toast.error($i18n.t('Please set up billing first'));
			return;
		}
		
		changingTier = true;
		try {
			const authToken = getAuthToken();
			await setUserSubscription(selectedTierId, authToken);
			toast.success($i18n.t('Subscription tier updated!'));
			await loadData();
		} catch (err: any) {
			console.error('Failed to change tier:', err);
			toast.error(err?.message || $i18n.t('Failed to change tier'));
		} finally {
			changingTier = false;
		}
	};

	// Aggregate daily usage by date for chart
	$: dailyByDate = summary?.daily_usage?.reduce((acc, d) => {
		const existing = acc.find((x) => x.date === d.date);
		if (existing) {
			existing.tokens_total += d.tokens_total;
			existing.request_count += d.request_count;
		} else {
			acc.push({ date: d.date, tokens_total: d.tokens_total, request_count: d.request_count });
		}
		return acc;
	}, [] as { date: string; tokens_total: number; request_count: number }[]) || [];

	$: maxDailyTokens = Math.max(...dailyByDate.map((d) => d.tokens_total), 1);

	onMount(loadData);
</script>

<div class="space-y-6">
	{#if loading}
		<div class="flex items-center justify-center py-8">
			<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-500"></div>
		</div>
	{:else if summary}
		<!-- Current Bill Summary -->
		<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
			<div class="flex items-center justify-between mb-3">
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">
					{$i18n.t('Current Billing Period')}
				</h3>
				<span class="text-xs text-gray-500">
					{summary.period_start} - {summary.period_end}
				</span>
			</div>

			<!-- Usage Bar -->
			<div class="mb-4">
				<div class="flex justify-between text-xs mb-1">
					<span class="text-gray-600 dark:text-gray-400">
						{formatTokens(summary.bill.tokens_used)} / {formatTokens(summary.bill.tokens_included)}
					</span>
					<span class={summary.bill.usage_percent >= 100 ? 'text-red-500 font-medium' : 'text-gray-500'}>
						{summary.bill.usage_percent.toFixed(1)}%
					</span>
				</div>
				<div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
					<div
						class="{getUsageBarColor(summary.bill.usage_percent)} h-2.5 rounded-full transition-all duration-300"
						style="width: {Math.min(100, summary.bill.usage_percent)}%"
					></div>
				</div>
				{#if summary.bill.usage_percent >= 80 && summary.bill.usage_percent < 100}
					<p class="text-xs text-yellow-600 dark:text-yellow-400 mt-1">
						⚠️ {$i18n.t('Approaching quota limit')}
					</p>
				{:else if summary.bill.usage_percent >= 100}
					<p class="text-xs text-red-500 mt-1">
						🚨 {$i18n.t('Quota exceeded! Overage charges apply.')}
					</p>
				{/if}
			</div>

			<!-- Bill Details -->
			<div class="grid grid-cols-2 gap-4 text-sm">
				<div>
					<div class="text-gray-500 dark:text-gray-400 text-xs">{$i18n.t('Plan')}</div>
					<div class="font-medium text-gray-800 dark:text-gray-100">{summary.bill.tier_name}</div>
				</div>
				<div>
					<div class="text-gray-500 dark:text-gray-400 text-xs">{$i18n.t('Base Price')}</div>
					<div class="font-medium text-gray-800 dark:text-gray-100">
						{formatCents(summary.bill.base_price_cents)}/mo
					</div>
				</div>
				{#if summary.bill.tokens_overage > 0}
					<div>
						<div class="text-gray-500 dark:text-gray-400 text-xs">{$i18n.t('Overage')}</div>
						<div class="font-medium text-red-500">
							{formatTokens(summary.bill.tokens_overage)} tokens
						</div>
					</div>
					<div>
						<div class="text-gray-500 dark:text-gray-400 text-xs">{$i18n.t('Overage Cost')}</div>
						<div class="font-medium text-red-500">
							+{formatCents(summary.bill.overage_cost_cents)}
						</div>
					</div>
				{/if}
			</div>

			<!-- Total -->
			<div class="mt-4 pt-3 border-t border-gray-200 dark:border-gray-700 flex justify-between items-center">
				<span class="text-sm font-medium text-gray-700 dark:text-gray-200">
					{$i18n.t('Estimated Total')}
				</span>
				<span class="text-lg font-bold text-teal-600 dark:text-teal-400">
					{formatCents(summary.bill.total_cost_cents)}
				</span>
			</div>
		</div>

		<!-- Billing Setup / Manage Section -->
		{#if billingStatus?.stripe_configured && !billingStatus?.has_payment_method}
			<!-- No payment method - show friendly invitation to select a plan -->
			<div class="bg-teal-50 dark:bg-teal-900/20 border border-teal-200 dark:border-teal-800 rounded-xl p-4">
				<div class="flex items-start gap-3">
					<div class="text-teal-500 mt-0.5">
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z" />
						</svg>
					</div>
					<div class="flex-1">
						<h3 class="text-sm font-semibold text-teal-800 dark:text-teal-200">
							{$i18n.t('Choose a Plan to Get Started')}
						</h3>
						<p class="text-xs text-teal-700 dark:text-teal-300 mt-1">
							{$i18n.t('Select a plan below to set up billing and receive your first month of tokens.')}
						</p>
					</div>
				</div>
			</div>
		{:else if billingStatus?.stripe_configured && billingStatus?.has_payment_method && !billingStatus?.is_trial}
			<!-- Has payment method - show green manage billing -->
			<div class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl p-4">
				<div class="flex items-center justify-between">
					<div class="flex items-center gap-3">
						<div class="text-green-500">
							<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5">
								<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
							</svg>
						</div>
						<div>
							<h3 class="text-sm font-semibold text-green-800 dark:text-green-200">
								{$i18n.t('Billing Active')}
							</h3>
							<p class="text-xs text-green-700 dark:text-green-300">
								{$i18n.t('Your payment method is set up. Select a plan below.')}
							</p>
						</div>
					</div>
					<button
						class="px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium text-sm transition disabled:opacity-50"
						disabled={settingUpBilling}
						on:click={handleSetupBilling}
					>
						{settingUpBilling ? $i18n.t('Opening...') : $i18n.t('Manage Billing')}
					</button>
				</div>
			</div>
		{/if}

		<!-- Change Plan -->
		<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
			<div class="flex items-center justify-between mb-3">
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">
					{$i18n.t('Change Plan')}
				</h3>
				{#if billingStatus?.is_trial}
					<span class="text-xs text-purple-600 dark:text-purple-400 flex items-center gap-1">
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-3.5 h-3.5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z" />
						</svg>
						{$i18n.t('Trial Account')}
					</span>
				{:else if billingStatus?.has_payment_method}
					<span class="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-3.5 h-3.5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
						</svg>
						{$i18n.t('Billing active')}
					</span>
				{/if}
			</div>
			
			<!-- Pending Tier Change Banner -->
			{#if summary?.pending_tier}
				<div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-3 mb-3">
					<div class="flex items-center justify-between">
						<div class="flex items-center gap-2 text-sm text-blue-700 dark:text-blue-300">
							<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
								<path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
							</svg>
							<span>
								{$i18n.t('Your plan will change to')} <strong>{summary.pending_tier.name}</strong> {$i18n.t('on')} {summary.period_end}
							</span>
						</div>
						<button
							class="text-xs text-blue-600 dark:text-blue-400 hover:underline"
							on:click={async () => {
								changingTier = true;
								try {
									const authToken = getAuthToken();
									await setUserSubscription(summary.bill.tier_id, authToken);
									toast.success($i18n.t('Pending change cancelled'));
									await loadData();
								} catch (err) {
									console.error('Failed to cancel pending change:', err);
									toast.error(err?.message || $i18n.t('Failed to cancel'));
								} finally {
									changingTier = false;
								}
							}}
						>
							{$i18n.t('Cancel change')}
						</button>
					</div>
				</div>
			{/if}
			
			<div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
				{#each Object.entries(tiers).filter(([id, t]) => id !== 'none') as [tierId, tier]}
					<button
						class="p-3 rounded-lg border-2 transition-all text-left {tierId === summary?.subscription?.pending_tier_id
							? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
							: tierId === summary.bill.tier_id
								? 'border-teal-500 bg-teal-50 dark:bg-teal-900/20'
								: 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'}
							{changingTier ? 'opacity-50 pointer-events-none' : ''}"
						disabled={changingTier}
						on:click={async () => {
							// If no payment method, redirect to checkout to pay first month
							if (billingStatus?.stripe_configured && !billingStatus?.has_payment_method) {
								changingTier = true;
								try {
									const authToken = getAuthToken();
									const result = await createSubscriptionCheckout(tierId, authToken);
									if (result?.url) {
										window.location.href = result.url;
									} else {
										toast.error($i18n.t('Failed to start checkout'));
									}
								} catch (err: any) {
									console.error('Failed to create checkout:', err);
									toast.error(err?.message || $i18n.t('Failed to start checkout'));
								} finally {
									changingTier = false;
								}
								return;
							}
							// Allow clicking current tier to cancel pending change
							if (tierId === summary.bill.tier_id && !summary?.subscription?.pending_tier_id) {
								// Already on this tier and no pending change
								return;
							}
							if (tierId === summary?.subscription?.pending_tier_id) {
								// Already pending for this tier
								return;
							}
							selectedTierId = tierId;
							// Auto-save immediately
							changingTier = true;
							try {
								const authToken = getAuthToken();
								const result = await setUserSubscription(tierId, authToken);
								if (result.message) {
									toast.success($i18n.t(result.message));
								} else if (result.pending_tier) {
									toast.success($i18n.t('Plan change scheduled for ' + summary.period_end));
								} else {
									toast.success($i18n.t('Plan updated to ' + tier.name + '!'));
								}
								await loadData();
							} catch (err) {
								console.error('Failed to change tier:', err);
								toast.error(err?.message || $i18n.t('Failed to change tier'));
								// Revert selection
								selectedTierId = summary.bill.tier_id;
							} finally {
								changingTier = false;
							}
						}}
					>
						<div class="font-medium text-gray-800 dark:text-gray-100">{tier.name}</div>
						<div class="text-lg font-bold text-teal-600 dark:text-teal-400">
							{formatCents(tier.monthly_price_cents)}<span class="text-xs font-normal">/mo</span>
						</div>
						<div class="text-xs text-gray-500 mt-1">
							{formatTokens(tier.tokens_included)} tokens
						</div>
						<div class="text-xs text-gray-400">
							+{formatCents(tier.overage_rate_per_1k_cents * 10)}/10K overage
						</div>
						{#if tierId === summary.bill.tier_id}
							<div class="text-xs text-teal-600 dark:text-teal-400 mt-1 font-medium">✓ {$i18n.t('Current')}</div>
						{:else if tierId === summary?.subscription?.pending_tier_id}
							<div class="text-xs text-blue-600 dark:text-blue-400 mt-1 font-medium">→ {$i18n.t('Pending')}</div>
						{/if}
					</button>
				{/each}
			</div>
			{#if changingTier}
				<p class="mt-3 text-xs text-gray-500 text-center animate-pulse">
					{$i18n.t('Updating plan...')}
				</p>
			{:else if billingStatus?.stripe_configured && !billingStatus?.has_payment_method}
				<p class="mt-3 text-xs text-gray-500 text-center">
					{$i18n.t('Select a plan to set up billing and get started')}
				</p>
			{/if}
			
			<!-- Cancel/Pause Plan Option -->
			{#if summary.bill.tier_id && summary.bill.tier_id !== 'none'}
				<div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
					<button
						class="text-sm text-gray-500 hover:text-red-500 dark:text-gray-400 dark:hover:text-red-400 transition flex items-center gap-2"
						disabled={changingTier}
						on:click={async () => {
							if (!confirm($i18n.t('Cancel your subscription? Your current plan will remain active until the end of this billing period. Any overage charges will still apply.'))) {
								return;
							}
							changingTier = true;
							try {
								const authToken = getAuthToken();
								await setUserSubscription('none', authToken);
								toast.success($i18n.t('Subscription cancelled. You will not be billed next month.'));
								await loadData();
							} catch (err) {
								console.error('Failed to cancel subscription:', err);
								toast.error(err?.message || $i18n.t('Failed to cancel subscription'));
							} finally {
								changingTier = false;
							}
						}}
					>
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
							<path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 0 0 5.636 5.636m12.728 12.728A9 9 0 0 1 5.636 5.636m12.728 12.728L5.636 5.636" />
						</svg>
						{$i18n.t('Cancel Subscription')}
					</button>
					<p class="text-xs text-gray-400 mt-1">
						{$i18n.t('Cancellation takes effect at the end of the current billing period.')}
					</p>
				</div>
			{:else if summary.bill.tier_id === 'none'}
				<div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
					<div class="flex items-center gap-2 text-sm text-amber-600 dark:text-amber-400">
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
							<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
						</svg>
						{$i18n.t('No active plan. Select a plan above to continue using the service.')}
					</div>
				</div>
			{/if}
		</div>

		<!-- Daily Usage Chart -->
		{#if dailyByDate.length > 0}
			<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
					{$i18n.t('Daily Usage')}
				</h3>
				<div class="flex items-end gap-1 h-32">
					{#each dailyByDate as day}
						<div class="flex-1 flex flex-col items-center group relative">
							<div
								class="w-full bg-teal-500/80 rounded-t transition-all hover:bg-teal-400"
								style="height: {(day.tokens_total / maxDailyTokens) * 100}%"
							></div>
							<div
								class="absolute bottom-full mb-2 hidden group-hover:block bg-gray-900 text-white text-xs p-2 rounded shadow-lg z-10 whitespace-nowrap"
							>
								<div class="font-medium">{day.date}</div>
								<div>{formatTokens(day.tokens_total)} tokens</div>
								<div>{day.request_count} requests</div>
							</div>
						</div>
					{/each}
				</div>
				<div class="flex justify-between text-xs text-gray-400 mt-1">
					<span>{dailyByDate[0]?.date?.slice(5) || ''}</span>
					<span>{dailyByDate[dailyByDate.length - 1]?.date?.slice(5) || ''}</span>
				</div>
			</div>
		{/if}

		<!-- Usage by Model -->
		{#if summary.by_model.length > 0}
			<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
					{$i18n.t('Usage by Model')}
				</h3>
				<div class="space-y-2">
					{#each summary.by_model.sort((a, b) => b.tokens_total - a.tokens_total) as model}
						{@const percent = (model.tokens_total / summary.bill.tokens_used) * 100}
						<div class="flex items-center gap-3">
							<div class="flex-1">
								<div class="flex justify-between text-xs mb-1">
									<span class="text-gray-700 dark:text-gray-300 font-medium truncate">
										{model.model_id || 'Unknown'}
									</span>
									<span class="text-gray-500">
										{formatTokens(model.tokens_total)} ({percent.toFixed(1)}%)
									</span>
								</div>
								<div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
									<div
										class="bg-teal-500 h-1.5 rounded-full"
										style="width: {Math.min(100, percent)}%"
									></div>
								</div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/if}
	{:else}
		<div class="text-center py-8 text-gray-500">
			{$i18n.t('No usage data available')}
		</div>
	{/if}
</div>
