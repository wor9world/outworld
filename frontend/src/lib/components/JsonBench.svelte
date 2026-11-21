<script lang="ts">
	import Play from '@lucide/svelte/icons/play';
	import type { Tool } from '#lib/types.ts';

	let {
		tools = [],
		onrun
	}: { tools?: Tool[]; onrun: (tool: string, args: Record<string, unknown>) => void } = $props();

	let selected = $state('');
	let body = $state('{}');
	let parseError = $state('');

	let current = $derived(tools.find((tool) => tool.id === selected) ?? null);

	$effect(() => {
		if (!selected && tools.length > 0) {
			selected = tools[0].id;
		}
	});

	function run(): void {
		try {
			const args = JSON.parse(body || '{}') as Record<string, unknown>;
			parseError = '';
			onrun(selected, args);
		} catch {
			parseError = 'JSON ไม่ถูกต้อง';
		}
	}
</script>

<div class="flex flex-col gap-3">
	<div class="flex flex-wrap gap-2">
		{#each tools as tool (tool.id)}
			<button
				type="button"
				onclick={() => {
					selected = tool.id;
					body = JSON.stringify(tool.input_schema && Object.keys(tool.input_schema).length ? tool.input_schema : {}, null, 2);
				}}
				aria-pressed={selected === tool.id}
				class="rounded-lg border px-2.5 py-1 font-mono text-xs {selected === tool.id
					? 'border-neutral-900 bg-neutral-900 text-white dark:border-white dark:bg-white dark:text-neutral-900'
					: 'border-neutral-300 text-neutral-700 hover:bg-neutral-100 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800'}"
			>
				{tool.id}
			</button>
		{/each}
	</div>

	{#if current}
		<p class="text-xs text-neutral-500">{current.description}</p>
	{/if}

	<textarea
		bind:value={body}
		rows={6}
		aria-label="Tool arguments"
		spellcheck={false}
		class="w-full rounded-lg border border-neutral-300 bg-white p-3 font-mono text-xs dark:border-neutral-700 dark:bg-neutral-950"
	></textarea>

	{#if parseError}
		<p class="text-xs text-red-600">{parseError}</p>
	{/if}

	<button
		type="button"
		onclick={run}
		disabled={!selected}
		class="inline-flex w-fit items-center gap-2 rounded-lg bg-neutral-900 px-3 py-1.5 text-sm text-white disabled:opacity-40 dark:bg-white dark:text-neutral-900"
	>
		<Play size={14} /> Run
	</button>
</div>
