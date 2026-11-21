<script lang="ts">
	import { untrack } from 'svelte';
	import type { Provider } from '#lib/types.ts';

	let {
		provider = null,
		onsave,
		ondelete
	}: {
		provider?: Provider | null;
		onsave: (data: Record<string, unknown>) => void;
		ondelete?: () => void;
	} = $props();

	let name = $state(untrack(() => provider?.name ?? ''));
	let kind = $state<'openai' | 'ollama'>(untrack(() => provider?.kind ?? 'openai'));
	let baseUrl = $state(untrack(() => provider?.base_url ?? 'https://api.openai.com/v1'));
	let model = $state(untrack(() => provider?.model ?? ''));
	let apiKey = $state('');
	let enabled = $state(untrack(() => provider?.enabled ?? false));

	function submit(): void {
		const payload: Record<string, unknown> = {
			name: name.trim(),
			kind,
			base_url: baseUrl.trim(),
			model: model.trim(),
			enabled
		};
		if (apiKey) payload.api_key = apiKey;
		onsave(payload);
	}
</script>

<form
	onsubmit={(event) => {
		event.preventDefault();
		submit();
	}}
	class="grid gap-2 rounded-xl border border-neutral-200 bg-white p-3 sm:grid-cols-2 dark:border-neutral-800 dark:bg-neutral-950"
>
	<label class="text-xs text-neutral-500">
		name
		<input bind:value={name} required class="mt-1 w-full rounded-md border border-neutral-300 bg-transparent px-2 py-1.5 text-sm dark:border-neutral-700" />
	</label>
	<label class="text-xs text-neutral-500">
		kind
		<select bind:value={kind} class="mt-1 w-full rounded-md border border-neutral-300 bg-transparent px-2 py-1.5 text-sm dark:border-neutral-700">
			<option value="openai">openai-compatible</option>
			<option value="ollama">ollama</option>
		</select>
	</label>
	<label class="text-xs text-neutral-500">
		base_url
		<input bind:value={baseUrl} required class="mt-1 w-full rounded-md border border-neutral-300 bg-transparent px-2 py-1.5 text-sm dark:border-neutral-700" />
	</label>
	<label class="text-xs text-neutral-500">
		model
		<input bind:value={model} required class="mt-1 w-full rounded-md border border-neutral-300 bg-transparent px-2 py-1.5 text-sm dark:border-neutral-700" />
	</label>
	<label class="text-xs text-neutral-500 sm:col-span-2">
		api_key
		<input
			bind:value={apiKey}
			type="password"
			placeholder={provider ? 'ว่าง = ใช้ key เดิม' : 'sk-…'}
			class="mt-1 w-full rounded-md border border-neutral-300 bg-transparent px-2 py-1.5 font-mono text-sm dark:border-neutral-700"
		/>
	</label>
	<div class="flex items-center justify-between sm:col-span-2">
		<label class="flex items-center gap-2 text-xs text-neutral-500">
			<input type="checkbox" bind:checked={enabled} /> enabled
		</label>
		<div class="flex gap-2">
			{#if ondelete}
				<button type="button" onclick={ondelete} class="rounded-lg border border-neutral-300 px-3 py-1.5 text-xs dark:border-neutral-700">
					ลบ
				</button>
			{/if}
			<button type="submit" class="rounded-lg bg-neutral-900 px-3 py-1.5 text-xs text-white dark:bg-white dark:text-neutral-900">
				บันทึก
			</button>
		</div>
	</div>
</form>
