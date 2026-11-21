<script lang="ts">
	import Brain from '@lucide/svelte/icons/brain';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import type { Pattern } from '#lib/types.ts';

	let {
		pattern,
		onpromote,
		ontoggle,
		ondelete
	}: {
		pattern: Pattern;
		onpromote: () => void;
		ontoggle: (enabled: boolean) => void;
		ondelete: () => void;
	} = $props();
</script>

<div class="rounded-xl border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-950">
	<div class="flex items-start justify-between gap-2">
		<div class="min-w-0">
			<p class="truncate text-sm font-medium text-neutral-900 dark:text-neutral-100">{pattern.name}</p>
			<p class="mt-0.5 truncate text-xs text-neutral-500">{pattern.intent}</p>
		</div>
		<span class="shrink-0 rounded-full bg-neutral-100 px-2 py-0.5 text-[11px] text-neutral-600 dark:bg-neutral-800 dark:text-neutral-300">
			{pattern.success}/{Math.max(pattern.uses, 1)}
		</span>
	</div>

	<div class="mt-3 flex items-center gap-2">
		<label class="flex items-center gap-1 text-[11px] text-neutral-500">
			<input
				type="checkbox"
				checked={pattern.enabled}
				onchange={(event) => ontoggle((event.currentTarget as HTMLInputElement).checked)}
				class="size-3"
			/>
			enabled
		</label>
		<button
			type="button"
			onclick={onpromote}
			class="ml-auto rounded-md border border-neutral-300 px-2 py-1 text-[11px] hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800"
		>
			<Brain size={11} class="mr-1 inline" /> promote
		</button>
		<button
			type="button"
			aria-label="Delete pattern"
			onclick={ondelete}
			class="rounded-md border border-neutral-300 p-1 text-neutral-500 hover:bg-red-50 hover:text-red-600 dark:border-neutral-700 dark:hover:bg-red-950"
		>
			<Trash2 size={11} />
		</button>
	</div>
</div>
