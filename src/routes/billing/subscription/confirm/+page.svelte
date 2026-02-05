<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { confirmSubscriptionCheckout } from '$lib/apis/billing';
	import { toast } from 'svelte-sonner';

	let loading = true;
	let success = false;
	let message = '';
	let tokensGranted = 0;
	let tierName = '';
	let error = '';

	const getAuthToken = () => localStorage?.token ?? '';

	onMount(async () => {
		const sessionId = $page.url.searchParams.get('session_id');
		
		if (!sessionId) {
			error = 'Missing session ID';
			loading = false;
			return;
		}

		try {
			const result = await confirmSubscriptionCheckout(sessionId, getAuthToken());
			success = result.success;
			message = result.message;
			tokensGranted = result.tokens_granted;
			tierName = result.tier?.name || 'your plan';
		} catch (err: any) {
			console.error('Failed to confirm subscription:', err);
			error = err?.message || 'Failed to confirm subscription';
		} finally {
			loading = false;
		}
	});

	const handleContinue = () => {
		goto('/?settings=account');
	};
</script>

<svelte:head>
	<title>Subscription Confirmed - Autotech AI</title>
</svelte:head>

<div class="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900 p-4">
	<div class="max-w-md w-full bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8 text-center">
		{#if loading}
			<div class="py-8">
				<div class="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-500 mx-auto mb-4"></div>
				<p class="text-gray-600 dark:text-gray-300">Confirming your subscription...</p>
			</div>
		{:else if success}
			<div class="py-4">
				<!-- Success checkmark -->
				<div class="w-16 h-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mx-auto mb-6">
					<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
						<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
					</svg>
				</div>
				
				<h1 class="text-2xl font-bold text-gray-800 dark:text-gray-100 mb-2">
					Welcome to {tierName}!
				</h1>
				
				<p class="text-gray-600 dark:text-gray-300 mb-6">
					{message}
				</p>
				
				<div class="bg-teal-50 dark:bg-teal-900/20 rounded-xl p-4 mb-6">
					<div class="text-sm text-teal-700 dark:text-teal-300">Tokens Added</div>
					<div class="text-3xl font-bold text-teal-600 dark:text-teal-400">
						{tokensGranted.toLocaleString()}
					</div>
				</div>
				
				<button
					on:click={handleContinue}
					class="w-full px-6 py-3 bg-teal-500 hover:bg-teal-600 text-white font-medium rounded-xl transition"
				>
					Start Chatting →
				</button>
			</div>
		{:else}
			<div class="py-4">
				<!-- Error icon -->
				<div class="w-16 h-16 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mx-auto mb-6">
					<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
						<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</div>
				
				<h1 class="text-2xl font-bold text-gray-800 dark:text-gray-100 mb-2">
					Something went wrong
				</h1>
				
				<p class="text-red-600 dark:text-red-400 mb-6">
					{error}
				</p>
				
				<button
					on:click={handleContinue}
					class="w-full px-6 py-3 bg-gray-500 hover:bg-gray-600 text-white font-medium rounded-xl transition"
				>
					Go Back to Settings
				</button>
			</div>
		{/if}
	</div>
</div>
