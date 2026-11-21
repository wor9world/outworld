<script lang="ts">
	let {
		route
	}: {
		route: { intent: string | null; rule_id: string | null; source?: string; confidence?: number };
	} = $props();
</script>

<div
	class="inline-flex items-center gap-2 rounded-full border border-neutral-200 bg-white px-2.5 py-1 text-[11px] text-neutral-600 dark:border-neutral-700 dark:bg-neutral-950 dark:text-neutral-300"
	title={route.rule_id ?? 'no rule matched'}
>
	<span class="size-1.5 rounded-full bg-emerald-500"></span>
	<span class="font-mono">{route.intent ?? 'no_route'}</span>
	<span class="text-neutral-400">·</span>
	<span>{route.source}</span>
	{#if route.confidence !== undefined}
		<span class="text-neutral-400">{route.confidence.toFixed(1)}</span>
	{/if}
</div>
