<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import CircleDashed from '@lucide/svelte/icons/circle-dashed';
	import CircleSlash from '@lucide/svelte/icons/circle-slash';
	import X from '@lucide/svelte/icons/x';
	import type { ToolCall } from '#lib/types.ts';

	let { calls = [] }: { calls?: ToolCall[] } = $props();
</script>

{#if calls.length > 0}
	<details class="rounded-xl border border-neutral-200 bg-white text-xs dark:border-neutral-800 dark:bg-neutral-950">
		<summary class="cursor-pointer px-3 py-2 text-neutral-600 dark:text-neutral-300">
			tool calls ({calls.length})
		</summary>
		<ul class="divide-y divide-neutral-100 dark:divide-neutral-800">
			{#each calls as call (call.id ?? call.tool + call.status)}
				<li class="flex items-center gap-2 px-3 py-1.5">
					{#if call.status === 'ok'}
						<Check size={12} class="text-emerald-600" />
					{:else if call.status === 'running'}
						<CircleDashed size={12} class="text-neutral-400" />
					{:else if call.status === 'denied'}
						<CircleSlash size={12} class="text-amber-600" />
					{:else}
						<X size={12} class="text-red-600" />
					{/if}
					<span class="font-mono text-[12px] text-neutral-700 dark:text-neutral-300">{call.tool}</span>
					<span class="ml-auto text-[11px] text-neutral-400">{call.ms}ms</span>
				</li>
			{/each}
		</ul>
	</details>
{/if}
