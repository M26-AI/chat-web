<script lang="ts">
	import { onMount } from 'svelte';
	import { getUsageDashboard, redeemCoupon } from '$lib/apis/usage';
	let data:any = null; let error=''; let code=''; let range='30';
	const load=async()=>{ try { data=await getUsageDashboard(localStorage.token); } catch(e) { error=String(e); } };
	onMount(load);
	$: pct=data ? Math.max(0, Math.min(100, (data.monthly_remaining/data.monthly_total)*100)) : 0;
</script>
<svelte:head><title>Usage &amp; Credits – ThatAI Chat</title></svelte:head>
<main class="max-w-6xl mx-auto p-6 text-gray-900 dark:text-gray-100">
	<h1 class="text-2xl font-semibold mb-6">Usage &amp; Credits</h1>
	{#if error}<p class="text-red-500">{error}</p>{:else if !data}<p>Loading usage…</p>{:else}
		<section class="grid md:grid-cols-3 gap-4 mb-6">
			<div class="rounded-2xl bg-white dark:bg-gray-850 shadow p-6 flex items-center gap-5"><div class="rounded-full border-8 border-indigo-500 w-28 h-28 grid place-items-center text-center"><b>{data.monthly_remaining.toFixed(2)}</b><small>credits</small></div><div><p class="font-medium">{data.tier.name}</p><p class="text-sm opacity-70">{data.consumed.toFixed(2)} of {data.monthly_total} used</p><p class="text-sm opacity-70">Resets {new Date(data.next_reset*1000).toLocaleDateString()}</p></div></div>
			<div class="rounded-2xl bg-white dark:bg-gray-850 shadow p-6"><p class="font-medium">Credit balances</p><p class="mt-3">Monthly <b>{data.monthly_remaining.toFixed(2)}</b></p><p>Bonus <b>{data.bonus_remaining.toFixed(2)}</b></p><p class="mt-4 text-sm opacity-70">Planned prices are not charges during Closed Beta.</p></div>
			<form class="rounded-2xl bg-white dark:bg-gray-850 shadow p-6" on:submit|preventDefault={async()=>{error='';try{await redeemCoupon(localStorage.token,code);code='';await load()}catch(e){error=String(e)}}}><label class="font-medium">Redeem a coupon</label><input bind:value={code} class="w-full mt-3 p-2 rounded border dark:bg-gray-900" placeholder="CODE" /><button class="mt-2 px-3 py-2 rounded bg-indigo-600 text-white">Redeem</button></form>
		</section>
		<section class="rounded-2xl bg-white dark:bg-gray-850 shadow p-6 mb-6"><div class="flex justify-between"><h2 class="font-medium">Daily usage</h2><select bind:value={range} class="dark:bg-gray-900"><option value="7">7 days</option><option value="30">30 days</option><option value="custom">Custom</option></select></div><div class="mt-4 flex items-end gap-2 h-32">{#each data.daily.slice(0, range==='7'?7:30).reverse() as d}<div class="flex-1 bg-indigo-500 rounded-t" style={`height:${Math.max(4,Math.min(100,d.credits*10))}%`} title={`${d.day}: ${d.credits} credits`}></div>{/each}</div></section>
		<section class="grid md:grid-cols-2 gap-4"><div class="rounded-2xl bg-white dark:bg-gray-850 shadow p-6"><h2 class="font-medium mb-3">By model</h2>{#each data.by_model as r}<p class="border-b py-2">{r.model_id}<span class="float-right">{r.input_tokens+r.output_tokens} tokens · {Number(r.credits).toFixed(3)} credits</span></p>{/each}</div><div class="rounded-2xl bg-white dark:bg-gray-850 shadow p-6"><h2 class="font-medium mb-3">Credit history</h2>{#each data.transactions as t}<p class="border-b py-2 text-sm">{new Date(t.created_at*1000).toLocaleString()} — {t.kind}<span class="float-right">{Number(t.amount).toFixed(3)}</span></p>{/each}</div></section>
	{/if}
</main>
