<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { createEventDispatcher, onMount, getContext, tick } from 'svelte';
import { afterNavigate } from '$app/navigation';

	const dispatch = createEventDispatcher();

	import { getOllamaConfig, updateOllamaConfig } from '$lib/apis/ollama';
	import { getOpenAIConfig, updateOpenAIConfig, getOpenAIModels } from '$lib/apis/openai';
	import { getGoogleConfig, updateGoogleConfig } from '$lib/apis/google';
	import { getModels as _getModels, getBackendConfig } from '$lib/apis';
	import { getConnectionsConfig, setConnectionsConfig } from '$lib/apis/configs';

	import { config, models, settings, user } from '$lib/stores';

	import Switch from '$lib/components/common/Switch.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
import Minus from '$lib/components/icons/Minus.svelte';
import PencilSolid from '$lib/components/icons/PencilSolid.svelte';
import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import OpenAIConnection from './Connections/OpenAIConnection.svelte';
	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import AddConnectionModal from '$lib/components/AddConnectionModal.svelte';
	import OllamaConnection from './Connections/OllamaConnection.svelte';
	import GoogleConnection from './Connections/GoogleConnection.svelte';

	const i18n = getContext('i18n');

	const getModels = async () => {
		const models = await _getModels(
			localStorage.token,
			$config?.features?.enable_direct_connections && ($settings?.directConnections ?? null),
			false,
			true
		);
		return models;
	};

	// External
	let OLLAMA_BASE_URLS = [''];
	let OLLAMA_API_CONFIGS = {};

	let OPENAI_API_KEYS = [''];
	let OPENAI_API_BASE_URLS = [''];
	let OPENAI_API_CONFIGS = {};

	let GOOGLE_API_KEYS = [''];
	let GOOGLE_API_BASE_URLS = [''];
	let GOOGLE_API_CONFIGS = {};

	let ENABLE_OPENAI_API: null | boolean = null;
	let ENABLE_OLLAMA_API: null | boolean = null;
	let ENABLE_GOOGLE_API: null | boolean = null;

	let connectionsConfig = null;

	let pipelineUrls = {};
	let showAddOpenAIConnectionModal = false;
	let showAddOllamaConnectionModal = false;
	let showAddGoogleConnectionModal = false;

	const updateOpenAIHandler = async () => {
		if (ENABLE_OPENAI_API !== null) {
			// Remove trailing slashes
			OPENAI_API_BASE_URLS = OPENAI_API_BASE_URLS.map((url) => url.replace(/\/$/, ''));

			// If the UI has empty base URLs (e.g., not populated), preserve server values so we don't accidentally clear them
			if (!OPENAI_API_BASE_URLS || OPENAI_API_BASE_URLS.length === 0 || OPENAI_API_BASE_URLS.every((u) => !u || u.trim() === '')) {
				try {
					const server = await getOpenAIConfig(localStorage.token).catch(() => null);
					if (server) {
						OPENAI_API_BASE_URLS = server.OPENAI_API_BASE_URLS || OPENAI_API_BASE_URLS;
						OPENAI_API_KEYS = server.OPENAI_API_KEYS || OPENAI_API_KEYS;
						OPENAI_API_CONFIGS = server.OPENAI_API_CONFIGS || OPENAI_API_CONFIGS;
					}
				} catch (e) {
					console.warn('Failed to fetch server OpenAI config to preserve values', e);
				}
			}

			// Check if API KEYS length is same than API URLS length
			if (OPENAI_API_KEYS.length !== OPENAI_API_BASE_URLS.length) {
				// if there are more keys than urls, remove the extra keys
				if (OPENAI_API_KEYS.length > OPENAI_API_BASE_URLS.length) {
					OPENAI_API_KEYS = OPENAI_API_KEYS.slice(0, OPENAI_API_BASE_URLS.length);
				}

				// if there are more urls than keys, add empty keys
				if (OPENAI_API_KEYS.length < OPENAI_API_BASE_URLS.length) {
					const diff = OPENAI_API_BASE_URLS.length - OPENAI_API_KEYS.length;
					for (let i = 0; i < diff; i++) {
						OPENAI_API_KEYS.push('');
					}
				}
			}

			const res = await updateOpenAIConfig(localStorage.token, {
				ENABLE_OPENAI_API: ENABLE_OPENAI_API,
				OPENAI_API_BASE_URLS: OPENAI_API_BASE_URLS,
				OPENAI_API_KEYS: OPENAI_API_KEYS,
				OPENAI_API_CONFIGS: OPENAI_API_CONFIGS
			}).catch((error) => {
				toast.error(`${error}`);
			});

			if (res) {
				toast.success($i18n.t('OpenAI API settings updated'));
				await models.set(await getModels());
			}
		}
	};

	const updateOllamaHandler = async () => {
		if (ENABLE_OLLAMA_API !== null) {
			// Remove trailing slashes
			OLLAMA_BASE_URLS = OLLAMA_BASE_URLS.map((url) => url.replace(/\/$/, ''));

			// Preserve server values if UI is empty so we don't clear config accidentally
			if (!OLLAMA_BASE_URLS || OLLAMA_BASE_URLS.length === 0 || OLLAMA_BASE_URLS.every((u) => !u || u.trim() === '')) {
				try {
					const server = await getOllamaConfig(localStorage.token).catch(() => null);
					if (server) {
						OLLAMA_BASE_URLS = server.OLLAMA_BASE_URLS || OLLAMA_BASE_URLS;
						OLLAMA_API_CONFIGS = server.OLLAMA_API_CONFIGS || OLLAMA_API_CONFIGS;
					}
				} catch (e) {
					console.warn('Failed to fetch server Ollama config to preserve values', e);
				}
			}

			const res = await updateOllamaConfig(localStorage.token, {
				ENABLE_OLLAMA_API: ENABLE_OLLAMA_API,
				OLLAMA_BASE_URLS: OLLAMA_BASE_URLS,
				OLLAMA_API_CONFIGS: OLLAMA_API_CONFIGS
			}).catch((error) => {
				toast.error(`${error}`);
			});

			if (res) {
				toast.success($i18n.t('Ollama API settings updated'));
				await models.set(await getModels());
			}
		}
	};

const updateGoogleHandler = async () => {
	if (ENABLE_GOOGLE_API !== null) {
		GOOGLE_API_BASE_URLS = GOOGLE_API_BASE_URLS.map((url) => url.replace(/\/$/, ''));

		// Preserve server values if UI is empty
		if (!GOOGLE_API_BASE_URLS || GOOGLE_API_BASE_URLS.length === 0 || GOOGLE_API_BASE_URLS.every((u) => !u || u.trim() === '')) {
			try {
				const server = await getGoogleConfig(localStorage.token).catch(() => null);
				if (server) {
					GOOGLE_API_BASE_URLS = server.GOOGLE_API_BASE_URLS || GOOGLE_API_BASE_URLS;
					GOOGLE_API_KEYS = server.GOOGLE_API_KEYS || GOOGLE_API_KEYS;
					GOOGLE_API_CONFIGS = server.GOOGLE_API_CONFIGS || GOOGLE_API_CONFIGS;
				}
			} catch (e) {
				console.warn('Failed to fetch server Google config to preserve values', e);
			}
		}

		const res = await updateGoogleConfig(localStorage.token, {
			ENABLE_GOOGLE_API: ENABLE_GOOGLE_API,
			GOOGLE_API_BASE_URLS: GOOGLE_API_BASE_URLS,
			GOOGLE_API_KEYS: GOOGLE_API_KEYS,
			GOOGLE_API_CONFIGS: GOOGLE_API_CONFIGS
		}).catch((error) => {
			toast.error(`${error}`);
		});

		if (res) {
			toast.success($i18n.t('Google API settings updated'));
			await models.set(await getModels());
		}
	}
};

const addGoogleConnectionHandler = async (connection) => {
	// Ensure Google API is enabled when adding a connection
	ENABLE_GOOGLE_API = true;

	const existingIdx = GOOGLE_API_BASE_URLS.indexOf(connection.url);
	if (existingIdx !== -1) {
		// Update existing entry rather than duplicating
		GOOGLE_API_KEYS[existingIdx] = connection.key;
		GOOGLE_API_CONFIGS[existingIdx] = connection.config;
	} else {
		GOOGLE_API_BASE_URLS = [...GOOGLE_API_BASE_URLS, connection.url];
		GOOGLE_API_KEYS = [...GOOGLE_API_KEYS, connection.key];
		GOOGLE_API_CONFIGS[GOOGLE_API_BASE_URLS.length - 1] = connection.config;
	}

	// Persist encrypted provider credential if provided
	if (connection.key) {
		try {
			await setGoogleCredentials(localStorage.token, 'google', connection.key);
		} catch (err) {
			console.warn('Failed to set Google credentials:', err);
		}
	}

	await updateGoogleHandler();
};

// Edit helpers for Google connections
let editingGoogleIdx = null;
let editingGoogleConnection = null;

const editGoogleConnection = (idx) => {
	editingGoogleIdx = idx;
	editingGoogleConnection = {
		url: GOOGLE_API_BASE_URLS[idx],
		key: GOOGLE_API_KEYS[idx],
		config: GOOGLE_API_CONFIGS[idx] || {}
	};
	showAddGoogleConnectionModal = true;
};

const handleGoogleSubmit = async (connection) => {
	// Ensure Google API is enabled when adding or editing
	ENABLE_GOOGLE_API = true;

	if (editingGoogleIdx !== null) {
		GOOGLE_API_BASE_URLS[editingGoogleIdx] = connection.url;
		GOOGLE_API_KEYS[editingGoogleIdx] = connection.key;
		GOOGLE_API_CONFIGS[editingGoogleIdx] = connection.config;
		editingGoogleIdx = null;
		editingGoogleConnection = null;
	} else {
		// Prevent duplicate entries: update existing if url already present
		const existingIdx = GOOGLE_API_BASE_URLS.indexOf(connection.url);
		if (existingIdx !== -1) {
			GOOGLE_API_KEYS[existingIdx] = connection.key;
			GOOGLE_API_CONFIGS[existingIdx] = connection.config;
		} else {
			GOOGLE_API_BASE_URLS = [...GOOGLE_API_BASE_URLS, connection.url];
			GOOGLE_API_KEYS = [...GOOGLE_API_KEYS, connection.key];
			GOOGLE_API_CONFIGS[GOOGLE_API_BASE_URLS.length - 1] = connection.config;
		}
	}

	// Persist encrypted provider credential if provided (best-effort)
	if (connection.key) {
		try {
			await setGoogleCredentials(localStorage.token, 'google', connection.key);
		} catch (err) {
			console.warn('Failed to set Google credentials:', err);
		}
	}

	await updateGoogleHandler();
};

const deleteGoogleConnectionHandler = async () => {
	if (editingGoogleIdx !== null) {
		const idx = editingGoogleIdx;
		GOOGLE_API_BASE_URLS = GOOGLE_API_BASE_URLS.filter((_, i) => i !== idx);
		GOOGLE_API_KEYS = GOOGLE_API_KEYS.filter((_, i) => i !== idx);
		let newConfig = {};
		GOOGLE_API_BASE_URLS.forEach((u, newIdx) => {
			newConfig[newIdx] = GOOGLE_API_CONFIGS[newIdx < idx ? newIdx : newIdx + 1];
		});
		GOOGLE_API_CONFIGS = newConfig;
		editingGoogleIdx = null;
		editingGoogleConnection = null;
		showAddGoogleConnectionModal = false;
		await updateGoogleHandler();

		// If there are no remaining Google connections, clear stored provider credentials
		if (GOOGLE_API_BASE_URLS.length === 0) {
			try {
				await setGoogleCredentials(localStorage.token, 'google', null);
			} catch (err) {
				console.warn('Failed to clear Google credentials:', err);
			}
		}
	}
};

	const updateConnectionsHandler = async () => {
		// Fetch latest server-side connections config and merge to avoid overwriting unchanged fields
		let serverCfg = {};
		try {
			const serverRes = await getConnectionsConfig(localStorage.token).catch((err) => {
				console.warn('Failed to fetch server connections config before saving, proceeding with local values', err);
				return null;
			});
			if (serverRes && serverRes.data) {
				serverCfg = serverRes.data;
			}
		} catch (e) {
			console.warn('Error fetching server config:', e);
		}

		// Merge server config with current UI values to avoid accidental blank overwrites.
		// Preserve server Google values when UI omits them
		if ((!GOOGLE_API_BASE_URLS || GOOGLE_API_BASE_URLS.length === 0) && serverCfg?.GOOGLE_API_BASE_URLS?.length) {
			GOOGLE_API_BASE_URLS = serverCfg.GOOGLE_API_BASE_URLS;
		}
		if ((!GOOGLE_API_KEYS || GOOGLE_API_KEYS.length === 0) && serverCfg?.GOOGLE_API_KEYS?.length) {
			GOOGLE_API_KEYS = serverCfg.GOOGLE_API_KEYS;
		}

		const mergedConfig = {
			...serverCfg,
			...(connectionsConfig || {}),

			// Explicitly include current provider settings from the UI state
			ENABLE_OPENAI_API: ENABLE_OPENAI_API,
			OPENAI_API_BASE_URLS: OPENAI_API_BASE_URLS,
			OPENAI_API_KEYS: OPENAI_API_KEYS,
			OPENAI_API_CONFIGS: OPENAI_API_CONFIGS,

			ENABLE_OLLAMA_API: ENABLE_OLLAMA_API,
			OLLAMA_BASE_URLS: OLLAMA_BASE_URLS,
			OLLAMA_API_CONFIGS: OLLAMA_API_CONFIGS,

			ENABLE_GOOGLE_API: ENABLE_GOOGLE_API,
			GOOGLE_API_BASE_URLS: GOOGLE_API_BASE_URLS,
			GOOGLE_API_KEYS: GOOGLE_API_KEYS,
			GOOGLE_API_CONFIGS: GOOGLE_API_CONFIGS,
		};

		const res = await setConnectionsConfig(localStorage.token, mergedConfig).catch((error) => {
			toast.error(`${error}`);
		});

		if (res) {
			toast.success($i18n.t('Connections settings updated'));
			await models.set(await getModels());
			await config.set(await getBackendConfig());
		}
	};

	const addOpenAIConnectionHandler = async (connection) => {
		OPENAI_API_BASE_URLS = [...OPENAI_API_BASE_URLS, connection.url];
		OPENAI_API_KEYS = [...OPENAI_API_KEYS, connection.key];
		OPENAI_API_CONFIGS[OPENAI_API_BASE_URLS.length - 1] = connection.config;

		await updateOpenAIHandler();
	};

	const addOllamaConnectionHandler = async (connection) => {
		OLLAMA_BASE_URLS = [...OLLAMA_BASE_URLS, connection.url];
		OLLAMA_API_CONFIGS[OLLAMA_BASE_URLS.length - 1] = {
			...connection.config,
			key: connection.key
		};

		await updateOllamaHandler();
	};

const refreshConfigs = async () => {
		if ($user?.role !== 'admin') return;

		let ollamaConfig = {};
		let openaiConfig = {};
		let googleConfig = {};

		const results = await Promise.allSettled([
			getOllamaConfig(localStorage.token),
			getOpenAIConfig(localStorage.token),
			getGoogleConfig(localStorage.token),
			getConnectionsConfig(localStorage.token)
		]);

		// Apply results individually and fall back to sensible defaults on failure
		if (results[0].status === 'fulfilled') {
			ollamaConfig = results[0].value;
		} else {
			console.warn('getOllamaConfig failed', results[0].reason);
			ollamaConfig = {};
		}

		if (results[1].status === 'fulfilled') {
			openaiConfig = results[1].value;
		} else {
			console.warn('getOpenAIConfig failed', results[1].reason);
			openaiConfig = {};
		}

		if (results[2].status === 'fulfilled') {
			googleConfig = results[2].value;
		} else {
			console.warn('getGoogleConfig failed', results[2].reason);
			googleConfig = {};
		}

		if (results[3].status === 'fulfilled') {
			connectionsConfig = results[3].value;
		} else {
			console.warn('getConnectionsConfig failed', results[3].reason);
			connectionsConfig = {};
		}

		ENABLE_OPENAI_API = openaiConfig.ENABLE_OPENAI_API;
		ENABLE_OLLAMA_API = ollamaConfig.ENABLE_OLLAMA_API;
		ENABLE_GOOGLE_API = googleConfig.ENABLE_GOOGLE_API;

		OPENAI_API_BASE_URLS = openaiConfig.OPENAI_API_BASE_URLS;
		OPENAI_API_KEYS = openaiConfig.OPENAI_API_KEYS;
		OPENAI_API_CONFIGS = openaiConfig.OPENAI_API_CONFIGS;

		GOOGLE_API_BASE_URLS = googleConfig.GOOGLE_API_BASE_URLS || [];
		GOOGLE_API_KEYS = googleConfig.GOOGLE_API_KEYS || [];
		GOOGLE_API_CONFIGS = googleConfig.GOOGLE_API_CONFIGS || {};
		OLLAMA_API_CONFIGS = ollamaConfig.OLLAMA_API_CONFIGS;

		if (ENABLE_OPENAI_API) {
			// get url and idx
			for (const [idx, url] of OPENAI_API_BASE_URLS.entries()) {
				if (!OPENAI_API_CONFIGS[idx]) {
					// Legacy support, url as key
					OPENAI_API_CONFIGS[idx] = OPENAI_API_CONFIGS[url] || {};
				}
			}

			OPENAI_API_BASE_URLS.forEach(async (url, idx) => {
				OPENAI_API_CONFIGS[idx] = OPENAI_API_CONFIGS[idx] || {};
				if (!(OPENAI_API_CONFIGS[idx]?.enable ?? true)) {
					return;
				}
				const res = await getOpenAIModels(localStorage.token, idx);
				if (res.pipelines) {
					pipelineUrls[url] = true;
				}
			});
		}

		if (ENABLE_OLLAMA_API) {
			// Ensure base URLs are populated from server config
			OLLAMA_BASE_URLS = ollamaConfig.OLLAMA_BASE_URLS || OLLAMA_BASE_URLS || [];

			for (const [idx, url] of OLLAMA_BASE_URLS.entries()) {
				if (!OLLAMA_API_CONFIGS[idx]) {
					OLLAMA_API_CONFIGS[idx] = OLLAMA_API_CONFIGS[url] || {};
				}
			}
		}
	};

	onMount(async () => {
		await refreshConfigs();

		// Refresh configs whenever user navigates to a different route and returns
		const unsubs = [];
		unsubs.push(afterNavigate(() => {
			// Defer slightly to allow any other route navigation handlers to complete
			setTimeout(() => refreshConfigs(), 50);
		}));

		// Refresh when window regains focus (user returned to tab)
		const onFocus = () => refreshConfigs();
		window.addEventListener('focus', onFocus);

		return () => {
			// cleanup
			try {
				unsubs.forEach((u) => u());
				window.removeEventListener('focus', onFocus);
			} catch (e) {
				console.warn('Error cleaning up navigation handlers', e);
			}
		};
	});

	const submitHandler = async () => {
		// Refresh server values before saving to minimize chance of overwriting with blanks
		await refreshConfigs();

		// Always persist OpenAI flag (user may be toggling it on/off)
		await updateOpenAIHandler();

		// Only update Ollama/Google if UI shows non-empty base URLs (prevents accidental clears)
		if (OLLAMA_BASE_URLS && OLLAMA_BASE_URLS.some((u) => u && u.trim() !== '')) {
			await updateOllamaHandler();
		}

		if (GOOGLE_API_BASE_URLS && GOOGLE_API_BASE_URLS.some((u) => u && u.trim() !== '')) {
			await updateGoogleHandler();
		}

		dispatch('save');

		// Refresh backend-derived config in the UI
		await config.set(await getBackendConfig());
	};
</script>

<AddConnectionModal
	bind:show={showAddOpenAIConnectionModal}
	onSubmit={addOpenAIConnectionHandler}
/>

<AddConnectionModal
	ollama
	bind:show={showAddOllamaConnectionModal}
	onSubmit={addOllamaConnectionHandler}
/>

<AddConnectionModal
	google
	bind:show={showAddGoogleConnectionModal}
	edit={editingGoogleIdx !== null}
	connection={editingGoogleConnection}
	onSubmit={handleGoogleSubmit}
	onDelete={deleteGoogleConnectionHandler}
/>

<form class="flex flex-col h-full justify-between text-sm" on:submit|preventDefault={submitHandler}>
	<div class=" overflow-y-scroll scrollbar-hidden h-full">
		{#if ENABLE_OPENAI_API !== null && ENABLE_OLLAMA_API !== null && connectionsConfig !== null}
			<div class="mb-3.5">
				<div class=" mt-0.5 mb-2.5 text-base font-medium">{$i18n.t('General')}</div>

				<hr class=" border-gray-100/30 dark:border-gray-850/30 my-2" />

				<div class="my-2">
					<div class="mt-2 space-y-2">
					<div class="my-2">


						
					</div>
						<div class="flex justify-between items-center text-sm">
							<div class="  font-medium">{$i18n.t('OpenAI API')}</div>

							<div class="flex items-center">
								<div class="">
									<Switch
										bind:state={ENABLE_OPENAI_API}
										on:change={async () => {
											updateOpenAIHandler();
										}}
									/>
								</div>
							</div>
						</div>

						{#if ENABLE_OPENAI_API}
							<div class="">
								<div class="flex justify-between items-center">
									<div class="font-medium text-xs">{$i18n.t('Manage OpenAI API Connections')}</div>

									<Tooltip content={$i18n.t(`Add Connection`)}>
										<button
											class="px-1"
											on:click={() => {
												showAddOpenAIConnectionModal = true;
											}}
											type="button"
										>
											<Plus />
										</button>
									</Tooltip>
								</div>

								<div class="flex flex-col gap-1.5 mt-1.5">
									{#each OPENAI_API_BASE_URLS as url, idx}
										<OpenAIConnection
											bind:url={OPENAI_API_BASE_URLS[idx]}
											bind:key={OPENAI_API_KEYS[idx]}
											bind:config={OPENAI_API_CONFIGS[idx]}
											pipeline={pipelineUrls[url] ? true : false}
											onSubmit={() => {
												updateOpenAIHandler();
											}}
											onDelete={() => {
												OPENAI_API_BASE_URLS = OPENAI_API_BASE_URLS.filter(
													(url, urlIdx) => idx !== urlIdx
												);
												OPENAI_API_KEYS = OPENAI_API_KEYS.filter((key, keyIdx) => idx !== keyIdx);

												let newConfig = {};
												OPENAI_API_BASE_URLS.forEach((url, newIdx) => {
													newConfig[newIdx] =
														OPENAI_API_CONFIGS[newIdx < idx ? newIdx : newIdx + 1];
												});
												OPENAI_API_CONFIGS = newConfig;
												updateOpenAIHandler();
											}}
										/>
									{/each}
								</div>
							</div>
						{/if}
					</div>
				</div>

				<div class=" my-2">
					<div class="flex justify-between items-center text-sm mb-2">
						<div class="  font-medium">{$i18n.t('Ollama API')}</div>

						<div class="mt-1">
							<Switch
								bind:state={ENABLE_OLLAMA_API}
								on:change={async () => {
									updateOllamaHandler();
								}}
							/>
						</div>
					</div>

					{#if ENABLE_OLLAMA_API}
						<div class="">
							<div class="flex justify-between items-center">
								<div class="font-medium text-xs">{$i18n.t('Manage Ollama API Connections')}</div>

								<Tooltip content={$i18n.t(`Add Connection`)}>
									<button
										class="px-1"
										on:click={() => {
											showAddOllamaConnectionModal = true;
										}}
										type="button"
									>
										<Plus />
									</button>
								</Tooltip>
							</div>

							<div class="flex w-full gap-1.5">
								<div class="flex-1 flex flex-col gap-1.5 mt-1.5">
									{#each OLLAMA_BASE_URLS as url, idx}
										<OllamaConnection
											bind:url={OLLAMA_BASE_URLS[idx]}
											bind:config={OLLAMA_API_CONFIGS[idx]}
											{idx}
											onSubmit={() => {
												updateOllamaHandler();
											}}
											onDelete={() => {
												OLLAMA_BASE_URLS = OLLAMA_BASE_URLS.filter((url, urlIdx) => idx !== urlIdx);

												let newConfig = {};
												OLLAMA_BASE_URLS.forEach((url, newIdx) => {
													newConfig[newIdx] =
														OLLAMA_API_CONFIGS[newIdx < idx ? newIdx : newIdx + 1];
												});
												OLLAMA_API_CONFIGS = newConfig;
											}}
										/>
									{/each}
								</div>
							</div>

							<div class="mt-1 text-xs text-gray-400 dark:text-gray-500">
								{$i18n.t('Trouble accessing Ollama?')}
								<a
									class=" text-gray-300 font-medium underline"
									href="https://github.com/open-webui/open-webui#troubleshooting"
									target="_blank"
								>
									{$i18n.t('Click here for help.')}
								</a>
							</div>
						</div>
					{/if}

					<div class=" my-2">

							<div class="flex justify-between items-center text-sm mb-2">
								<div class="  font-medium">{$i18n.t('Google API')}</div>

								<div class="mt-1">
									<Switch
										bind:state={ENABLE_GOOGLE_API}
										on:change={async () => {
											updateGoogleHandler();
										}}
									/>
								</div>
							</div>
						{#if ENABLE_GOOGLE_API}							<div class="flex flex-col gap-1.5 mt-1.5">
								<div class="flex justify-between items-center">
									<div class="font-medium text-xs">{$i18n.t('Manage Google API Connections')}</div>

									<Tooltip content={$i18n.t(`Add Connection`)}>
										<button
											class="px-1"
											on:click={() => {
											showAddGoogleConnectionModal = true;
											}}
											type="button"
										>
											<Plus />
										</button>
									</Tooltip>
								</div>

								<div class="flex flex-col gap-1.5 mt-1.5">
									{#each GOOGLE_API_BASE_URLS as url, idx}
								<GoogleConnection bind:url={GOOGLE_API_BASE_URLS[idx]} bind:key={GOOGLE_API_KEYS[idx]} bind:config={GOOGLE_API_CONFIGS[idx]} onSubmit={() => { updateGoogleHandler(); }} onDelete={() => { GOOGLE_API_BASE_URLS = GOOGLE_API_BASE_URLS.filter((_, urlIdx) => idx !== urlIdx); GOOGLE_API_KEYS = GOOGLE_API_KEYS.filter((_, keyIdx) => idx !== keyIdx); let newConfig = {}; GOOGLE_API_BASE_URLS.forEach((u, newIdx) => { newConfig[newIdx] = GOOGLE_API_CONFIGS[newIdx < idx ? newIdx : newIdx + 1]; }); GOOGLE_API_CONFIGS = newConfig; }} />
											<div class="flex items-center gap-2">
											<input
												class="text-sm bg-transparent w-full"
												bind:value={GOOGLE_API_BASE_URLS[idx]}
												placeholder={$i18n.t('API Base URL')}
											/>
											<SensitiveInput bind:value={GOOGLE_API_KEYS[idx]} placeholder={$i18n.t('API Key')} />
										<Tooltip content={$i18n.t('Edit Connection')}>
											<button
											class="px-1"
											on:click={() => {
												editGoogleConnection(idx);
											}}
											type="button"
											aria-label={$i18n.t('Edit')}
											>
												<PencilSolid /><Cog6 />
											</button>
										</Tooltip>
										<button
											on:click={() => {
											GOOGLE_API_BASE_URLS = GOOGLE_API_BASE_URLS.filter((_, urlIdx) => idx !== urlIdx);
											GOOGLE_API_KEYS = GOOGLE_API_KEYS.filter((_, keyIdx) => idx !== keyIdx);
											let newConfig = {};
											GOOGLE_API_BASE_URLS.forEach((u, newIdx) => {
												newConfig[newIdx] = GOOGLE_API_CONFIGS[newIdx < idx ? newIdx : newIdx + 1];
											});
											GOOGLE_API_CONFIGS = newConfig;
											}}
										type="button"
											aria-label={$i18n.t('Delete')}
										>
											<Minus />
											</button>
										</div>
									{/each}
								</div>
							</div>
					{/if}
				</div>

				<div class="my-2">
					<div class="flex justify-between items-center text-sm">
						<div class="  font-medium">{$i18n.t('Direct Connections')}</div>

						<div class="flex items-center">
							<div class="">
								<Switch
									bind:state={connectionsConfig.ENABLE_DIRECT_CONNECTIONS}
									on:change={async () => {
										updateConnectionsHandler();
									}}
								/>
							</div>
						</div>
					</div>

					<div class="mt-1 text-xs text-gray-400 dark:text-gray-500">
						{$i18n.t(
							'Direct Connections allow users to connect to their own OpenAI compatible API endpoints.'
						)}
					</div>
				</div>

				<hr class=" border-gray-100/30 dark:border-gray-850/30 my-2" />

				<div class="my-2">
					<div class="flex justify-between items-center text-sm">
						<div class=" text-xs font-medium">{$i18n.t('Cache Base Model List')}</div>

						<div class="flex items-center">
							<div class="">
								<Switch
									bind:state={connectionsConfig.ENABLE_BASE_MODELS_CACHE}
									on:change={async () => {
										updateConnectionsHandler();
									}}
								/>
							</div>
						</div>
					</div>

					<div class="mt-1 text-xs text-gray-400 dark:text-gray-500">
						{$i18n.t(
							'Base Model List Cache speeds up access by fetching base models only at startup or on settings save—faster, but may not show recent base model changes.'
						)}
					</div>
				</div>
			</div>
			</div>
		{:else}
			<div class="flex h-full justify-center">
				<div class="my-auto">
					<Spinner className="size-6" />
				</div>
			</div>
		{/if}
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			type="submit"
		>
			{$i18n.t('Save')}
		</button>
	</div>
</form>
