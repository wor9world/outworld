<script lang="ts">
	import { untrack } from 'svelte';
	import type { Note } from '#lib/types.ts';

	let {
		note = null,
		onsave
	}: { note?: (Note & { body?: string }) | null; onsave: (data: Record<string, unknown>) => void } =
		$props();

	let title = $state(untrack(() => note?.title ?? ''));
	let tags = $state(untrack(() => note?.tags ?? ''));
	let body = $state(untrack(() => note?.body ?? ''));

	function submit(): void {
		if (!title.trim()) return;
		onsave({ title: title.trim(), tags: tags.trim(), body });
	}
</script>

<form
	onsubmit={(event) => {
		event.preventDefault();
		submit();
	}}
	class="flex flex-col gap-2 rounded-xl border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-950"
>
	<input
		bind:value={title}
		placeholder="title"
		required
		aria-label="Note title"
		class="rounded-md border border-neutral-300 bg-transparent px-2 py-1.5 text-sm dark:border-neutral-700"
	/>
	<input
		bind:value={tags}
		placeholder="tags (space separated)"
		aria-label="Note tags"
		class="rounded-md border border-neutral-300 bg-transparent px-2 py-1.5 text-xs dark:border-neutral-700"
	/>
	<textarea
		bind:value={body}
		rows={8}
		placeholder="markdown body…"
		aria-label="Note body"
		class="rounded-md border border-neutral-300 bg-transparent px-2 py-1.5 font-mono text-xs dark:border-neutral-700"
	></textarea>
	<div class="flex items-center justify-between">
		<span class="text-[11px] text-neutral-400">{body.length} chars</span>
		<button type="submit" class="rounded-lg bg-neutral-900 px-3 py-1.5 text-xs text-white dark:bg-white dark:text-neutral-900">
			บันทึก note
		</button>
	</div>
</form>
