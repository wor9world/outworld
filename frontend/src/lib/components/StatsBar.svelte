<script lang="ts">
	import type { LearningStats } from '#lib/types.ts';

	let { stats }: { stats: LearningStats } = $props();

	const cards = $derived([
		{ label: 'runs', value: stats.runs_total },
		{ label: 'ok rate', value: `${Math.round(stats.ok_rate * 100)}%` },
		{ label: 'pipe', value: `${Math.round(stats.pipe_rate * 100)}%` },
		{ label: 'patterns', value: stats.patterns_total },
		{ label: 'recalls', value: stats.recalls_24h }
	]);
</script>

<div class="grid grid-cols-2 gap-2 sm:grid-cols-5">
	{#each cards as card (card.label)}
		<div class="rounded-xl border border-neutral-200 bg-white px-3 py-2 dark:border-neutral-800 dark:bg-neutral-950">
			<p class="text-[11px] uppercase tracking-wide text-neutral-500">{card.label}</p>
			<p class="text-lg font-semibold text-neutral-900 dark:text-neutral-100">{card.value}</p>
		</div>
	{/each}
</div>
