<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { onMount, getContext, tick } from 'svelte';

	import { user, config, settings } from '$lib/stores';
	import { updateUserProfile, createAPIKey, getAPIKey, getSessionUser } from '$lib/apis/auths';
	import { createBillingPortal, createCheckoutSession, getTokenPricing, getAutoRenewSettings, setAutoRenewSettings } from '$lib/apis/billing';
	import { getUserBalance } from '$lib/apis/billing/usage';
	import { WEBUI_BASE_URL } from '$lib/constants';

	import UpdatePassword from './Account/UpdatePassword.svelte';
	import UsageBreakdown from './Account/UsageBreakdown.svelte';
	import { getGravatarUrl } from '$lib/apis/utils';
	import { generateInitialsImage, canvasPixelTest } from '$lib/utils';
	import { copyToClipboard } from '$lib/utils';
	import Plus from '$lib/components/icons/Plus.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import { getUserById } from '$lib/apis/users';
	import User from '$lib/components/icons/User.svelte';
	import UserProfileImage from './Account/UserProfileImage.svelte';

	const i18n = getContext('i18n');

	export let saveHandler: Function;
	export let saveSettings: Function;

	let loaded = false;

	let profileImageUrl = '';
	let name = '';
	let bio = '';

	let _gender = '';
	let gender = '';
	let dateOfBirth = '';

	let phone = '';
	let address = '';

	let webhookUrl = '';
	let showAPIKeys = false;
	let showUsageBreakdown = true;
	let tokenBalance: number | null = null;
	let tokenUsdRate: number | null = null;

	// Token bundles - loaded from API, with fallback defaults
	let tokenBundles: number[] = [10000, 20000, 50000];
	let buyTokensAmount: number = tokenBundles[0];
	let buyTokensCost: string | null = null;

	// Auto-renew settings
	let autoRenewEnabled: boolean = false;
	let autoRenewTokens: number = 0;
	let autoRenewSaving: boolean = false;

	const getAuthToken = () => (localStorage?.token ?? $user?.token) as string | undefined;

	const loadTokenPricing = async () => {
		try {
			const authToken = getAuthToken();
			const pricing = await getTokenPricing(authToken);
			if (pricing?.token_usd_rate && pricing.token_usd_rate > 0) {
				tokenUsdRate = pricing.token_usd_rate;
			} else {
				tokenUsdRate = null;
			}
			// Load token bundles from API if available
			if (pricing?.token_bundles && Array.isArray(pricing.token_bundles) && pricing.token_bundles.length > 0) {
				tokenBundles = pricing.token_bundles;
				buyTokensAmount = tokenBundles[0];
			}
		} catch (e) {
			// Non-fatal; fall back to the historical default label.
			console.error('Failed to load token pricing', e);
			tokenUsdRate = null;
		}
	};

	const formatUsd = (amount: number) => {
		// Keep this simple and consistent with Stripe display: 2 decimals.
		return amount.toFixed(2);
	};

	const getBuyTokensCost = (tokens: number) => {
		if (!tokenUsdRate || !(tokenUsdRate > 0)) return null;
		return formatUsd(tokens * tokenUsdRate);
	};

	// Ensure this recomputes when pricing arrives (tokenUsdRate changes).
	$: buyTokensCost = tokenUsdRate && tokenUsdRate > 0 ? getBuyTokensCost(buyTokensAmount) : null;

	let JWTTokenCopied = false;

	let APIKey = '';
	let APIKeyCopied = false;
	let profileImageInputElement: HTMLInputElement;

	const submitHandler = async () => {
		if (name !== $user?.name) {
			if (profileImageUrl === generateInitialsImage($user?.name) || profileImageUrl === '') {
				profileImageUrl = generateInitialsImage(name);
			}
		}

		if (webhookUrl !== $settings?.notifications?.webhook_url) {
			saveSettings({
				notifications: {
					...$settings.notifications,
					webhook_url: webhookUrl
				}
			});
		}

		const updatedUser = await updateUserProfile(localStorage.token, {
			name: name,
			profile_image_url: profileImageUrl,
			bio: bio ? bio : null,
			gender: gender ? gender : null,
			date_of_birth: dateOfBirth ? dateOfBirth : null,
			phone: phone ? phone : null,
			address: address ? address : null
		}).catch((error) => {
			toast.error(`${error}`);
		});

		if (updatedUser) {
			// Get Session User Info
			const sessionUser = await getSessionUser(localStorage.token).catch((error) => {
				toast.error(`${error}`);
				return null;
			});

			await user.set(sessionUser);
			return true;
		}
		return false;
	};

	const createAPIKeyHandler = async () => {
		APIKey = await createAPIKey(localStorage.token);
		if (APIKey) {
			toast.success($i18n.t('API Key created.'));
		} else {
			toast.error($i18n.t('Failed to create API Key.'));
		}
	};

	const createBillingHandler = async () => {
		try {
			const res = await createBillingPortal(localStorage.token);
			if (res?.url) {
				window.location.href = res.url;
			} else {
				toast.error($i18n.t('Failed to create billing portal session.'));
			}
		} catch (err) {
			toast.error(`${err}`);
		}
	};

	const buyTokensHandler = async (tokens: number, cost: string) => {
		try {
			const res = await createCheckoutSession(tokens, cost, localStorage.token);
			if (res?.url) {
				window.location.href = res.url;
			} else {
				toast.error($i18n.t('Failed to create checkout session.'));
			}
		} catch (err) {
			toast.error(`${err}`);
		}
	};

	const loadAutoRenewSettings = async () => {
		try {
			const settings = await getAutoRenewSettings(localStorage.token);
			autoRenewEnabled = settings.auto_renew_enabled;
			autoRenewTokens = settings.auto_renew_tokens || tokenBundles[0];
		} catch (e) {
			console.error('Failed to load auto-renew settings', e);
		}
	};

	const saveAutoRenewSettings = async () => {
		autoRenewSaving = true;
		try {
			const settings = await setAutoRenewSettings(
				autoRenewEnabled,
				autoRenewEnabled ? autoRenewTokens : 0,
				localStorage.token
			);
			autoRenewEnabled = settings.auto_renew_enabled;
			autoRenewTokens = settings.auto_renew_tokens || tokenBundles[0];
			toast.success($i18n.t('Auto-renew settings saved.'));
		} catch (err) {
			toast.error(`${err}`);
		} finally {
			autoRenewSaving = false;
		}
	};

	onMount(async () => {
		const user = await getSessionUser(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (user) {
			name = user?.name ?? '';
			profileImageUrl = user?.profile_image_url ?? '';
			bio = user?.bio ?? '';

			_gender = user?.gender ?? '';
			gender = _gender;

			dateOfBirth = user?.date_of_birth ?? '';
			phone = user?.phone ?? '';
			address = user?.address ?? '';

			const sessionRate = Number((user as any)?.token_usd_rate);
			if (Number.isFinite(sessionRate) && sessionRate > 0) {
				tokenUsdRate = sessionRate;
			}
		}

		// Always load pricing to get token bundles (session only has rate, not bundles)
		await tick();
		await loadTokenPricing();

		webhookUrl = $settings?.notifications?.webhook_url ?? '';

		try {
			const bal = await getUserBalance(localStorage.token);
			tokenBalance = Number(bal?.tokens_balance);
			if (!Number.isFinite(tokenBalance)) tokenBalance = null;
		} catch (err) {
			tokenBalance = null;
		}

		// Load auto-renew settings
		await loadAutoRenewSettings();

		// Only fetch API key if the feature is enabled and user has permission
		if (
			user &&
			($config?.features?.enable_api_keys ?? true) &&
			(user?.role === 'admin' || (user?.permissions?.features?.api_keys ?? false))
		) {
			APIKey = await getAPIKey(localStorage.token).catch((error) => {
				console.log(error);
				return '';
			});
		}

		loaded = true;
	});
</script>

<div id="tab-account" class="flex flex-col h-full justify-between text-sm">
	<div class=" overflow-y-auto scrollbar-hidden max-h-[28rem] md:max-h-full">
		<div class="space-y-1">
			<div>
				<div class="text-base font-medium">{$i18n.t('Your Account')}</div>

				<div class="text-xs text-gray-500 mt-0.5">
					{$i18n.t('Manage your account information.')}
				</div>
			</div>

			<!-- <div class=" text-sm font-medium">{$i18n.t('Account')}</div> -->

			<div class="flex space-x-5 my-4">
				<UserProfileImage bind:profileImageUrl user={$user} />

				<div class="flex flex-1 flex-col">
					<div class=" flex-1">
						<div class="flex flex-col w-full">
							<div class=" mb-1 text-xs font-medium">{$i18n.t('Name')}</div>

							<div class="flex-1">
								<input
									class="w-full text-sm dark:text-gray-300 bg-transparent outline-hidden"
									type="text"
									bind:value={name}
									required
									placeholder={$i18n.t('Enter your name')}
								/>
							</div>
						</div>

						<div class="flex flex-col w-full mt-2">
							<div class=" mb-1 text-xs font-medium">{$i18n.t('Bio')}</div>

							<div class="flex-1">
								<Textarea
									className="w-full text-sm dark:text-gray-300 bg-transparent outline-hidden"
									minSize={60}
									bind:value={bio}
									placeholder={$i18n.t('Share your background and interests')}
								/>
							</div>
						</div>

						<div class="flex flex-col w-full mt-2">
							<div class=" mb-1 text-xs font-medium">{$i18n.t('Gender')}</div>

							<div class="flex-1">
								<select
									class="dark:bg-gray-900 w-full text-sm dark:text-gray-300 bg-transparent outline-hidden"
									bind:value={_gender}
									on:change={(e) => {
										console.log(_gender);

										if (_gender === 'custom') {
											// Handle custom gender input
											gender = '';
										} else {
											gender = _gender;
										}
									}}
								>
									<option value="" selected>{$i18n.t('Prefer not to say')}</option>
									<option value="male">{$i18n.t('Male')}</option>
									<option value="female">{$i18n.t('Female')}</option>
									<option value="custom">{$i18n.t('Custom')}</option>
								</select>
							</div>

							{#if _gender === 'custom'}
								<input
									class="w-full text-sm dark:text-gray-300 bg-transparent outline-hidden mt-1"
									type="text"
									required
									placeholder={$i18n.t('Enter your gender')}
									bind:value={gender}
								/>
							{/if}
						</div>

						<div class="flex flex-col w-full mt-2">
							<div class=" mb-1 text-xs font-medium">{$i18n.t('Birth Date')}</div>

							<div class="flex-1">
								<input
									class="w-full text-sm dark:text-gray-300 dark:placeholder:text-gray-300 bg-transparent outline-hidden"
									type="date"
									bind:value={dateOfBirth}
									required
								/>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Token Dashboard - Primary section after profile -->
		<div class="mt-4 p-4 bg-gradient-to-r from-teal-50 to-cyan-50 dark:from-teal-900/20 dark:to-cyan-900/20 rounded-xl border border-teal-100 dark:border-teal-800/50">
			<div class="flex justify-between items-center mb-3">
				<div class="flex items-center gap-2">
					<div class="text-teal-600 dark:text-teal-400">
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5">
							<path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
						</svg>
					</div>
					<div class="text-base font-semibold text-teal-700 dark:text-teal-300">{$i18n.t('Token Dashboard')}</div>
				</div>
				<button
					class="text-xs font-medium px-3 py-1.5 rounded-lg bg-teal-500 text-white hover:bg-teal-600 transition"
					type="button"
					on:click={() => {
						showUsageBreakdown = !showUsageBreakdown;
					}}
				>
					{showUsageBreakdown ? $i18n.t('Collapse') : $i18n.t('Expand')}
				</button>
			</div>
			{#if showUsageBreakdown}
				<UsageBreakdown />
			{:else}
				<div class="text-sm text-gray-600 dark:text-gray-400">
					{$i18n.t('View your usage, subscription tier, and billing details.')}
				</div>
			{/if}
		</div>

		<!-- Contact info -->
		<div class="flex flex-col w-full mt-2">
			<div class=" mb-1 text-xs font-medium">{$i18n.t('Phone')}</div>

			<div class="flex-1">
				<input
					class="w-full text-sm dark:text-gray-300 bg-transparent outline-hidden"
					type="tel"
					bind:value={phone}
					placeholder={$i18n.t('Enter your phone number')}
				/>
			</div>
		</div>

		<div class="flex flex-col w-full mt-2">
			<div class=" mb-1 text-xs font-medium">{$i18n.t('Home Address')}</div>

			<div class="flex-1">
				<Textarea
					className="w-full text-sm dark:text-gray-300 bg-transparent outline-hidden"
					minSize={40}
					bind:value={address}
					placeholder={$i18n.t('Enter your home address')}
				/>
			</div>
		</div>

		<div class="flex flex-col w-full mt-2">
			<div class=" mb-1 text-xs font-medium">{$i18n.t('Notification Webhook')}</div>

			<div class="flex-1">
				<input
					class="w-full text-sm outline-hidden"
					type="url"
					placeholder={$i18n.t('Enter your webhook URL')}
					bind:value={webhookUrl}
					required
				/>
			</div>
		</div>

		<hr class="border-gray-50 dark:border-gray-850/30 my-4" />

		{#if $config?.features.enable_login_form}
			<div class="mt-2">
				<UpdatePassword />
			</div>
		{/if}

		{#if ($config?.features?.enable_api_keys ?? true) && ($user?.role === 'admin' || ($user?.permissions?.features?.api_keys ?? false))}
			<div class="flex justify-between items-center text-sm mt-2">
				<div class="  font-medium">{$i18n.t('API keys')}</div>
				<button
					class=" text-xs font-medium text-gray-500"
					type="button"
					on:click={() => {
						showAPIKeys = !showAPIKeys;
					}}>{showAPIKeys ? $i18n.t('Hide') : $i18n.t('Show')}</button
				>
			</div>

			{#if showAPIKeys}
				<div class="flex flex-col">
					{#if $user?.role === 'admin'}
						<div class="justify-between w-full mt-2">
							<div class="flex justify-between w-full">
								<div class="self-center text-xs font-medium mb-1">{$i18n.t('JWT Token')}</div>
							</div>

							<div class="flex">
								<SensitiveInput value={localStorage.token} readOnly={true} />

								<button
									class="ml-1.5 px-1.5 py-1 dark:hover:bg-gray-850 transition rounded-lg"
									on:click={() => {
										copyToClipboard(localStorage.token);
										JWTTokenCopied = true;
										setTimeout(() => {
											JWTTokenCopied = false;
										}, 2000);
									}}
								>
									{#if JWTTokenCopied}
										<svg
											xmlns="http://www.w3.org/2000/svg"
											viewBox="0 0 20 20"
											fill="currentColor"
											class="w-4 h-4"
										>
											<path
												fill-rule="evenodd"
												d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
												clip-rule="evenodd"
											/>
										</svg>
									{:else}
										<svg
											xmlns="http://www.w3.org/2000/svg"
											viewBox="0 0 16 16"
											fill="currentColor"
											class="w-4 h-4"
										>
											<path
												fill-rule="evenodd"
												d="M11.986 3H12a2 2 0 0 1 2 2v6a2 2 0 0 1-1.5 1.937V7A2.5 2.5 0 0 0 10 4.5H4.063A2 2 0 0 1 6 3h.014A2.25 2.25 0 0 1 8.25 1h1.5a2.25 2.25 0 0 1 2.236 2ZM10.5 4v-.75a.75.75 0 0 0-.75-.75h-1.5a.75.75 0 0 0-.75.75V4h3Z"
												clip-rule="evenodd"
											/>
											<path
												fill-rule="evenodd"
												d="M3 6a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H3Zm1.75 2.5a.75.75 0 0 0 0 1.5h3.5a.75.75 0 0 0 0-1.5h-3.5ZM4 11.75a.75.75 0 0 1 .75-.75h3.5a.75.75 0 0 1 0 1.5h-3.5a.75.75 0 0 1-.75-.75Z"
												clip-rule="evenodd"
											/>
										</svg>
									{/if}
								</button>
							</div>
						</div>
					{/if}

					{#if ($config?.features?.enable_api_keys ?? true) && ($user?.role === 'admin' || ($user?.permissions?.features?.api_keys ?? false))}
						<div class="justify-between w-full mt-2">
							{#if $user?.role === 'admin'}
								<div class="flex justify-between w-full">
									<div class="self-center text-xs font-medium mb-1">{$i18n.t('API Key')}</div>
								</div>
							{/if}
							<div class="flex">
								{#if APIKey}
									<SensitiveInput value={APIKey} readOnly={true} />

									<button
										class="ml-1.5 px-1.5 py-1 dark:hover:bg-gray-850 transition rounded-lg"
										on:click={() => {
											copyToClipboard(APIKey);
											APIKeyCopied = true;
											setTimeout(() => {
												APIKeyCopied = false;
											}, 2000);
										}}
									>
										{#if APIKeyCopied}
											<svg
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 20 20"
												fill="currentColor"
												class="w-4 h-4"
											>
												<path
													fill-rule="evenodd"
													d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
													clip-rule="evenodd"
												/>
											</svg>
										{:else}
											<svg
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 16 16"
												fill="currentColor"
												class="w-4 h-4"
											>
												<path
													fill-rule="evenodd"
													d="M11.986 3H12a2 2 0 0 1 2 2v6a2 2 0 0 1-1.5 1.937V7A2.5 2.5 0 0 0 10 4.5H4.063A2 2 0 0 1 6 3h.014A2.25 2.25 0 0 1 8.25 1h1.5a2.25 2.25 0 0 1 2.236 2ZM10.5 4v-.75a.75.75 0 0 0-.75-.75h-1.5a.75.75 0 0 0-.75.75V4h3Z"
													clip-rule="evenodd"
												/>
												<path
													fill-rule="evenodd"
													d="M3 6a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H3Zm1.75 2.5a.75.75 0 0 0 0 1.5h3.5a.75.75 0 0 0 0-1.5h-3.5ZM4 11.75a.75.75 0 0 1 .75-.75h3.5a.75.75 0 0 1 0 1.5h-3.5a.75.75 0 0 1-.75-.75Z"
													clip-rule="evenodd"
												/>
											</svg>
										{/if}
									</button>

									<Tooltip content={$i18n.t('Create new key')}>
										<button
											class=" px-1.5 py-1 dark:hover:bg-gray-850transition rounded-lg"
											on:click={() => {
												createAPIKeyHandler();
											}}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="2"
												stroke="currentColor"
												class="size-4"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"
												/>
											</svg>
										</button>
									</Tooltip>
								{:else}
									<button
										class="flex gap-1.5 items-center font-medium px-3.5 py-1.5 rounded-lg bg-gray-100/70 hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-850 transition"
										on:click={() => {
											createAPIKeyHandler();
										}}
									>
										<Plus strokeWidth="2" className=" size-3.5" />
											{$i18n.t('Create new secret key')}
										</button>
								{/if}
							</div>
						</div>
					{/if}
				</div>
			{/if}
		{/if}
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			on:click={async () => {
				const res = await submitHandler();

				if (res) {
					saveHandler();
				}
			}}
		>
			{$i18n.t('Save')}
		</button>
	</div>
</div>
