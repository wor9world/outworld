<script lang="ts">
	import KnowledgeEditor from '#lib/components/KnowledgeEditor.svelte';
	import { del, get, patch, post } from '#lib/api.ts';
	import type { Note } from '#lib/types.ts';

	let query = $state('');
	let notes = $state<Note[]>([]);
	let selected = $state<(Note & { body?: string }) | null>(null);
	let failure = $state('');

	async function search(): Promise<void> {
		try {
			const suffix = query.trim() ? `?q=${encodeURIComponent(query.trim())}&snippets=1` : '';
			notes = await get<Note[]>(`/knowledge${suffix}`);
		} catch (error) {
			failure = error instanceof Error ? error.message : 'search failed';
		}
	}

	$effect(() => {
		void search();
	});

	async function open(note: Note): Promise<void> {
		selected = await get<Note & { body?: string }>(`/knowledge/${note.id}`);
	}

	async function save(data: Record<string, unknown>): Promise<void> {
		if (selected) {
			await patch(`/knowledge/${selected.id}`, data);
		} else {
			await post('/knowledge', data);
		}
		selected = null;
		await search();
	}

	async function remove(): Promise<void> {
		if (!selected) return;
		await del(`/knowledge/${selected.id}`);
		selected = null;
		await search();
	}
</script>

<div class="mx-auto grid max-w-5xl gap-4 p-4 md:grid-cols-[1fr_360px]">
	<section>
		<div class="flex gap-2">
			<input
				bind:value={query}
				placeholder="ค้นหา note…"
				aria-label="Search notes"
				oninput={search}
				class="flex-1 rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-950"
			/>
			<button type="button" onclick={() => (selected = null)} class="rounded-lg border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700">
				+ ใหม่
			</button>
		</div>

		{#if failure}<p class="mt-2 text-xs text-red-600">{failure}</p>{/if}

		<ul class="mt-3 divide-y divide-neutral-200 rounded-xl border border-neutral-200 bg-white dark:divide-neutral-800 dark:border-neutral-800 dark:bg-neutral-950">
			{#each notes as note (note.id)}
				<li>
					<button type="button" onclick={() => open(note)} class="block w-full px-3 py-2 text-left hover:bg-neutral-50 dark:hover:bg-neutral-900">
						<span class="text-sm">{note.title}</span>
						{#if note.snippet}
							<span class="mt-1 block text-[11px] text-neutral-500">{@html note.snippet}</span>
						{/if}
					</button>
				</li>
			{:else}
				<li class="px-3 py-6 text-center text-xs text-neutral-400">ยังไม่มี note</li>
			{/each}
		</ul>
	</section>

	<section class="flex flex-col gap-2">
		<KnowledgeEditor note={selected} onsave={save} />
		{#if selected}
			<button type="button" onclick={remove} class="self-start rounded-lg border border-red-300 px-3 py-1.5 text-xs text-red-600 dark:border-red-800">
				ลบ note นี้
			</button>
		{/if}
	</section>
</div>
