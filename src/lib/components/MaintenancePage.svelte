<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { WEBUI_BASE_URL } from '$lib/constants';
	import { userSignOut } from '$lib/apis/auths';

	export let maintenance: {
		title: string;
		description: string;
		reason?: string | null;
		estimated_end?: string | null;
		show_estimated_end?: boolean;
		status?: string;
	};

	const dispatch = createEventDispatcher();
	$: endTime = maintenance.estimated_end
		? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(
				new Date(maintenance.estimated_end)
			)
		: null;

	const openAdministratorLogin = async () => {
		try {
			await userSignOut();
		} finally {
			localStorage.removeItem('token');
			window.location.assign('/auth?maintenance-login=1&redirect=/');
		}
	};
</script>

<main class="min-h-screen w-full bg-white text-gray-900 dark:bg-gray-950 dark:text-gray-100 flex items-center justify-center px-5 py-10">
	<section class="w-full max-w-xl text-center">
		<img src="{WEBUI_BASE_URL}/static/favicon.png" alt="ThatAI Chat" class="size-16 mx-auto mb-8 rounded-2xl" />
		<div class="inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-800 dark:bg-amber-950/50 dark:text-amber-200">
			<span class="size-1.5 rounded-full bg-amber-500"></span>
			{maintenance.status ?? 'Maintenance in progress'}
		</div>
		<h1 class="mt-6 text-3xl sm:text-4xl font-semibold tracking-tight">{maintenance.title}</h1>
		<p class="mt-4 text-base leading-7 text-gray-600 dark:text-gray-300">{maintenance.description}</p>
		{#if maintenance.reason}
			<p class="mt-3 text-sm text-gray-500 dark:text-gray-400">{maintenance.reason}</p>
		{/if}
		{#if maintenance.show_estimated_end && endTime}
			<p class="mt-6 text-sm text-gray-500 dark:text-gray-400">Estimated completion: {endTime}</p>
		{/if}
		<button class="mt-8 rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-700 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-300" on:click={() => dispatch('retry')}>
			Try Again
		</button>
		<button class="block mt-5 mx-auto text-sm text-gray-500 underline underline-offset-4 hover:text-gray-900 dark:hover:text-white" on:click={openAdministratorLogin}>
			Administrator sign in
		</button>
	</section>
</main>
