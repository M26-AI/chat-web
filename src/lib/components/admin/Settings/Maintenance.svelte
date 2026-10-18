<script lang="ts">
	import { onMount, createEventDispatcher } from 'svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import { getMaintenanceConfig, setMaintenanceConfig, type MaintenanceModeConfig } from '$lib/apis/configs';

	const dispatch = createEventDispatcher();
	let maintenance: MaintenanceModeConfig = {
		enabled: false, title: 'We’ll be right back.',
		description: 'ThatAI Chat is currently undergoing maintenance. We’re working on making your experience better.',
		estimated_end: null, reason: null, show_estimated_end: true
	};
	let estimatedEndInput = '';
	let reason = '';

	onMount(async () => {
		maintenance = await getMaintenanceConfig(localStorage.token);
		estimatedEndInput = maintenance.estimated_end ? maintenance.estimated_end.slice(0, 16) : '';
		reason = maintenance.reason ?? '';
	});

	const save = async () => {
		maintenance = await setMaintenanceConfig(localStorage.token, {
			...maintenance,
			estimated_end: estimatedEndInput ? new Date(estimatedEndInput).toISOString() : null,
			reason: reason || null
		});
		dispatch('save');
	};
</script>

<form class="flex flex-col h-full justify-between space-y-3 text-sm" on:submit|preventDefault={save}>
	<div class="overflow-y-scroll scrollbar-hidden h-full pr-1.5">
		<div class="mb-3.5 text-base font-medium">Maintenance Mode</div>
		<hr class="border-gray-100 dark:border-gray-850 my-2" />
		<div class="mb-5 flex items-center justify-between">
			<div><div class="font-medium">Enable maintenance mode</div><div class="mt-1 text-xs text-gray-500">Regular users will see the maintenance page immediately.</div></div>
			<Switch bind:state={maintenance.enabled} />
		</div>
		<div class="space-y-4">
			<label class="block"><div class="mb-1 text-xs font-medium">Title</div><input class="w-full rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-hidden" bind:value={maintenance.title} required maxlength="160" /></label>
			<label class="block"><div class="mb-1 text-xs font-medium">Description</div><Textarea bind:value={maintenance.description} required /></label>
			<label class="block"><div class="mb-1 text-xs font-medium">Reason <span class="font-normal text-gray-500">(optional)</span></div><Textarea bind:value={reason} placeholder="Optional maintenance reason" /></label>
			<label class="block"><div class="mb-1 text-xs font-medium">Estimated completion <span class="font-normal text-gray-500">(optional)</span></div><input class="w-full rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-hidden" type="datetime-local" bind:value={estimatedEndInput} /></label>
			<div class="flex items-center justify-between"><div><div class="font-medium">Show estimated completion</div><div class="mt-1 text-xs text-gray-500">Only shown when a completion time is set.</div></div><Switch bind:state={maintenance.show_estimated_end} /></div>
		</div>
	</div>
	<div class="flex justify-end pt-3"><button class="px-4 py-2 rounded-lg bg-black text-white dark:bg-white dark:text-black" type="submit">Save maintenance settings</button></div>
</form>
