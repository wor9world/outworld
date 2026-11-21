<script lang="ts">
	import { get, post } from '#lib/api.ts';
	import type { Project } from '#lib/types.ts';

	let projects = $state<Project[]>([]);
	let name = $state('');
	let failure = $state('');

	async function load(): Promise<void> {
		try {
			projects = await get<Project[]>('/projects');
		} catch (error) {
			failure = error instanceof Error ? error.message : 'failed to load';
		}
	}

	$effect(() => {
		void load();
	});

	async function create(): Promise<void> {
		if (!name.trim()) return;
		try {
			await post<Project>('/projects', { name: name.trim() });
			name = '';
			await load();
		} catch (error) {
			failure = error instanceof Error ? error.message : 'create failed';
		}
	}
</script>

<div class="mx-auto max-w-3xl p-4">
	<h1 class="text-lg font-semibold">Projects</h1>
	{#if failure}<p class="mt-2 text-xs text-red-600">{failure}</p>{/if}

	<form
		onsubmit={(event) => {
			event.preventDefault();
			create();
		}}
		class="mt-4 flex gap-2"
	>
		<input
			bind:value={name}
			placeholder="ชื่อโปรเจกต์"
			aria-label="Project name"
			class="flex-1 rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-950"
		/>
		<button type="submit" class="rounded-lg bg-neutral-900 px-3 py-2 text-sm text-white dark:bg-white dark:text-neutral-900">
			สร้าง
		</button>
	</form>

	<ul class="mt-4 divide-y divide-neutral-200 rounded-xl border border-neutral-200 bg-white dark:divide-neutral-800 dark:border-neutral-800 dark:bg-neutral-950">
		{#each projects as project (project.id)}
			<li>
				<a href={`/projects/${project.id}`} class="flex items-center justify-between px-3 py-2.5 hover:bg-neutral-50 dark:hover:bg-neutral-900">
					<span class="text-sm">{project.name}</span>
					<span class="text-[11px] text-neutral-400">{project.chat_count ?? 0} chats · {project.root_path}</span>
				</a>
			</li>
		{:else}
			<li class="px-3 py-6 text-center text-xs text-neutral-400">ยังไม่มีโปรเจกต์</li>
		{/each}
	</ul>
</div>
