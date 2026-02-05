<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	import {
		WEBUI_NAME,
		banners,
		chatId,
		config,
		mobile,
		settings,
		showArchivedChats,
		showControls,
		showSidebar,
		temporaryChatEnabled,
user,
			models
	} from '$lib/stores';
	import { 
		scannerConnected, 
		scannerConnecting, 
		connectScanner, 
		disconnectScanner, 
		isBluetoothSupported,
		performFullScan 
	} from '$lib/stores/scanner';

	import { slide } from 'svelte/transition';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';

	import ShareChatModal from '../chat/ShareChatModal.svelte';
	import ModelSelector from '../chat/ModelSelector.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import Menu from '$lib/components/layout/Navbar/Menu.svelte';
	import UserMenu from '$lib/components/layout/Sidebar/UserMenu.svelte';
	import AdjustmentsHorizontal from '../icons/AdjustmentsHorizontal.svelte';

	import PencilSquare from '../icons/PencilSquare.svelte';
	import Banner from '../common/Banner.svelte';
	import Sidebar from '../icons/Sidebar.svelte';

	import ChatBubbleDotted from '../icons/ChatBubbleDotted.svelte';
	import ChatBubbleDottedChecked from '../icons/ChatBubbleDottedChecked.svelte';

	import EllipsisHorizontal from '../icons/EllipsisHorizontal.svelte';
	import ChatPlus from '../icons/ChatPlus.svelte';
	import ChatCheck from '../icons/ChatCheck.svelte';
	import Knobs from '../icons/Knobs.svelte';
	import { WEBUI_API_BASE_URL } from '$lib/constants';

	const i18n = getContext('i18n');

	export let initNewChat: Function;
	export let shareEnabled: boolean = false;
	export let scrollTop = 0;

	export let chat;
	export let history;
	export let selectedModels;
	export let showModelSelector = true;
	export let onSaveTempChat: () => {};
	export let archiveChatHandler: (id: string) => void;
	export let moveChatHandler: (id: string, folderId: string) => void;

	let closedBannerIds = [];

	let showShareChatModal = false;
	let showDownloadChatModal = false;
</script>

<ShareChatModal bind:show={showShareChatModal} chatId={$chatId} />

<button
	id="new-chat-button"
	class="hidden"
	on:click={() => {
		initNewChat();
	}}
	aria-label="New Chat"
/>

<nav
	class="sticky top-0 z-30 w-full {chat?.id
		? 'pt-0.5 pb-1'
		: 'pt-1 pb-1'} -mb-12 flex flex-col items-center drag-region"
>
	<div class="flex items-center w-full pl-1.5 pr-1">
		<div
			id="navbar-bg-gradient-to-b"
			class="{chat?.id
				? 'visible'
				: 'invisible'} bg-linear-to-b via-40% to-97% from-white/90 via-white/50 to-transparent dark:from-gray-900/90 dark:via-gray-900/50 dark:to-transparent pointer-events-none absolute inset-0 -bottom-10 z-[-1]"
		></div>

		<div class=" flex max-w-full w-full mx-auto px-1.5 md:px-2 pt-0.5 bg-transparent">
			<div class="flex items-center w-full max-w-full">
				{#if $mobile && !$showSidebar}
					<div
						class="-translate-x-0.5 mr-1 mt-1 self-start flex flex-none items-center text-gray-600 dark:text-gray-400"
					>
						<Tooltip content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}>
							<button
								class=" cursor-pointer flex rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition"
								on:click={() => {
									showSidebar.set(!$showSidebar);
								}}
							>
								<div class=" self-center p-1.5">
									<Sidebar />
								</div>
							</button>
						</Tooltip>
					</div>
				{/if}

				<div
					class="flex-1 overflow-hidden max-w-full py-0.5
			{$showSidebar ? 'ml-1' : ''}
			"
				>
					{#if showModelSelector}
						<ModelSelector bind:selectedModels showSetDefault={!shareEnabled} />
					{/if}
				</div>

				<div class="self-start flex flex-none items-center text-gray-600 dark:text-gray-400">
					<!-- <div class="md:hidden flex self-center w-[1px] h-5 mx-2 bg-gray-300 dark:bg-stone-700" /> -->

					{#if $user?.role === 'user' ? ($user?.permissions?.chat?.temporary ?? true) && !($user?.permissions?.chat?.temporary_enforced ?? false) : true}
						{#if !chat?.id}
							<Tooltip content={$i18n.t(`Temporary Chat`)}>
								<button
									class="flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
									id="temporary-chat-button"
									on:click={async () => {
										if (($settings?.temporaryChatByDefault ?? false) && $temporaryChatEnabled) {
											// for proper initNewChat handling
											await temporaryChatEnabled.set(null);
										} else {
											await temporaryChatEnabled.set(!$temporaryChatEnabled);
										}

										await goto('/');

										// add 'temporary-chat=true' to the URL
										if ($temporaryChatEnabled) {
											window.history.replaceState(null, '', '?temporary-chat=true');
										} else {
											window.history.replaceState(null, '', location.pathname);
										}
									}}
								>
									<div class=" m-auto self-center">
										{#if $temporaryChatEnabled}
											<ChatBubbleDottedChecked className=" size-4.5" strokeWidth="1.5" />
										{:else}
											<ChatBubbleDotted className=" size-4.5" strokeWidth="1.5" />
										{/if}
									</div>
								</button>
							</Tooltip>
						{:else if $temporaryChatEnabled}
							<Tooltip content={$i18n.t(`Save Chat`)}>
								<button
									class="flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
									id="save-temporary-chat-button"
									on:click={async () => {
										onSaveTempChat();
									}}
								>
									<div class=" m-auto self-center">
										<ChatCheck className=" size-4.5" strokeWidth="1.5" />
									</div>
								</button>
							</Tooltip>
						{/if}
					{/if}

					{#if $mobile && !$temporaryChatEnabled && chat && chat.id}
						<Tooltip content={$i18n.t('New Chat')}>
							<button
								class=" flex {$showSidebar
									? 'md:hidden'
									: ''} cursor-pointer px-2 py-2 rounded-xl text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-850 transition"
								on:click={() => {
									initNewChat();
								}}
								aria-label="New Chat"
							>
								<div class=" m-auto self-center">
									<ChatPlus className=" size-4.5" strokeWidth="1.5" />
								</div>
							</button>
						</Tooltip>
					{/if}

					{#if shareEnabled && chat && (chat.id || $temporaryChatEnabled)}
						<Menu
							{chat}
							{shareEnabled}
							shareHandler={() => {
								showShareChatModal = !showShareChatModal;
							}}
							archiveChatHandler={() => {
								archiveChatHandler(chat.id);
							}}
							{moveChatHandler}
						>
							<button
								class="flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
								id="chat-context-menu-button"
							>
								<div class=" m-auto self-center">
									<EllipsisHorizontal className=" size-5" strokeWidth="1.5" />
								</div>
							</button>
						</Menu>
					{/if}

{#if $user?.role === 'admin'}
						<!-- OBD Scanner Connect Button -->
						<Tooltip content={$scannerConnected ? $i18n.t('Scanner Connected') : $i18n.t('Connect Scanner')}>
							<button
								class="flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition {$scannerConnected ? 'text-green-500' : ''} {$scannerConnecting ? 'animate-pulse' : ''}"
								on:click={async () => {
									if ($scannerConnected) {
										disconnectScanner();
										toast.success($i18n.t('Scanner disconnected'));
									} else {
										if (!isBluetoothSupported()) {
											toast.error($i18n.t('Web Bluetooth not supported. Use Chrome on Android.'));
											return;
										}
										const connected = await connectScanner();
										if (connected) {
											toast.success($i18n.t('Scanner connected! Reading vehicle data...'));
											// Auto-read all data on connect
											await performFullScan();
											toast.success($i18n.t('Vehicle data loaded'));
										}
									}
								}}
								aria-label="Connect Scanner"
								disabled={$scannerConnecting}
							>
								<div class="m-auto self-center">
									<!-- Wrench icon -->
									<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
										<path stroke-linecap="round" stroke-linejoin="round" d="M11.42 15.17 17.25 21A2.652 2.652 0 0 0 21 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 1 1-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 0 0 4.486-6.336l-3.276 3.277a3.004 3.004 0 0 1-2.25-2.25l3.276-3.276a4.5 4.5 0 0 0-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437 1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008Z" />
									</svg>
								</div>
							</button>
						</Tooltip>

						<Tooltip content={$i18n.t('Controls')}>
							<button
								class=" flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
								on:click={async () => {
									await showControls.set(!$showControls);
								}}
								aria-label="Controls"
							>
								<div class=" m-auto self-center">
									<Knobs className=" size-5" strokeWidth="1" />
								</div>
							</button>
						</Tooltip>
					{/if}

					{#if $user !== undefined && $user !== null}
						<UserMenu
							className="max-w-[240px]"
							role={$user?.role}
							help={true}
							on:show={(e) => {
								if (e.detail === 'archived-chat') {
									showArchivedChats.set(true);
								}
							}}
						>
							<div
								class="select-none flex rounded-xl p-1.5 w-full hover:bg-gray-50 dark:hover:bg-gray-850 transition"
							>
								<div class=" self-center">
									<span class="sr-only">{$i18n.t('User menu')}</span>
									<img
										src={`${WEBUI_API_BASE_URL}/users/${$user?.id}/profile/image`}
										class="size-6 object-cover rounded-full"
										alt=""
										draggable="false"
									/>
								</div>
							</div>
						</UserMenu>
					{/if}
				</div>
			</div>
		</div>
	</div>

	{#if $temporaryChatEnabled && ($chatId ?? '').startsWith('local:')}
		<div class=" w-full z-30 text-center">
			<div class="text-xs text-gray-500">{$i18n.t('Temporary Chat')}</div>
		</div>
	{/if}

	<div class="absolute top-[100%] left-0 right-0 h-fit">
		{#if !history.currentId && !$chatId && ($banners.length > 0 || ($config?.license_metadata?.type ?? null) === 'trial' || (($config?.license_metadata?.seats ?? null) !== null && $config?.user_count > $config?.license_metadata?.seats))}
			<div class=" w-full z-30">
				<div class=" flex flex-col gap-1 w-full">
					{#if ($config?.license_metadata?.type ?? null) === 'trial'}
						<Banner
							banner={{
								type: 'info',
								title: 'Trial License',
								content: $i18n.t(
									'You are currently using a trial license. Please contact support to upgrade your license.'
								)
							}}
						/>
					{/if}

					{#if ($config?.license_metadata?.seats ?? null) !== null && $config?.user_count > $config?.license_metadata?.seats}
						<Banner
							banner={{
								type: 'error',
								title: 'License Error',
								content: $i18n.t(
									'Exceeded the number of seats in your license. Please contact support to increase the number of seats.'
								)
							}}
						/>
					{/if}

					{#each $banners.filter((b) => ![...JSON.parse(localStorage.getItem('dismissedBannerIds') ?? '[]'), ...closedBannerIds].includes(b.id)) as banner (banner.id)}
						<Banner
							{banner}
							on:dismiss={(e) => {
								const bannerId = e.detail;

								if (banner.dismissible) {
									localStorage.setItem(
										'dismissedBannerIds',
										JSON.stringify(
											[
												bannerId,
												...JSON.parse(localStorage.getItem('dismissedBannerIds') ?? '[]')
											].filter((id) => $banners.find((b) => b.id === id))
										)
									);
								} else {
									closedBannerIds = [...closedBannerIds, bannerId];
								}
							}}
						/>
					{/each}
				</div>
			</div>
		{/if}
	</div>
</nav>
