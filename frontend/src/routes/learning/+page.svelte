<script lang="ts">
	import PatternCard from '#lib/components/PatternCard.svelte';
	import StatsBar from '#lib/components/StatsBar.svelte';
	import { del, get, patch, post } from '#lib/api.ts';
	import type { LearningStats, Pattern, Project, Run } from '#lib/types.ts';

	let stats = $state<LearningStats | null>(null);
	let patterns = $state<Pattern[]>([]);
	let runs = $state<Run[]>([]);
	let projects = $state<Project[]>([]);
	let failure = $state('');

	async function load(): Promise<void> {
		try {
			[stats, patterns, runs, projects] = await Promise.all([
				get<LearningStats>('/learning/stats'),
				get<Pattern[]>('/patterns'),
				get<Run[]>('/runs?limit=20'),
				get<Project[]>('/projects')
			]);
		} catch (error) {
			failure = error instanceof Error ? error.message : 'failed to load learning';
		}
	}

	$effect(() => {
		void load();
	});

	async function toggle(pattern: Pattern, enabled: boolean): Promise<void> {
		await patch(`/patterns/${pattern.id}`, { enabled });
		await load();
	}

	async function promote(pattern: Pattern): Promise<void> {
		const project = projects[0];
		if (!project) {
			failure = 'ต้องมีโปรเจกต์ก่อนจึงจะ promote ได้';
			return;
		}
		await post(`/patterns/${pattern.id}/promote`, { project_id: project.id });
		failure = `promoted เข้า ${project.name}`;
		await load();
	}

	async function remove(pattern: Pattern): Promise<void> {
		await del(`/patterns/${pattern.id}`);
		await load();
	}

	async function verdict(run: Run, value: 'good' | 'bad'): Promise<void> {
		await post(`/runs/${run.id}/feedback`, { verdict: value });
		await load();
	}
</script>

<div class="mx-auto flex max-w-4xl flex-col gap-5 p-4">
	<h1 class="text-lg font-semibold">Learning</h1>
	{#if failure}<p class="text-xs text-amber-700">{failure}</p>{/if}

	{#if stats}
		<StatsBar {stats} />
	{/if}

	<section>
		<h2 class="text-[11px] uppercase tracking-wide text-neutral-500">Patterns</h2>
		<div class="mt-2 grid gap-2 sm:grid-cols-2">
			{#each patterns as pattern (pattern.id)}
				<PatternCard
					{pattern}
					onpromote={() => promote(pattern)}
					ontoggle={(enabled) => toggle(pattern, enabled)}
					ondelete={() => remove(pattern)}
				/>
			{:else}
				<p class="text-xs text-neutral-400">
					ยังไม่มี pattern — pattern เกิดจาก run ที่สำเร็จและใช้ tool ≥ 2 ตัว
				</p>
			{/each}
		</div>
	</section>

	<section>
		<h2 class="text-[11px] uppercase tracking-wide text-neutral-500">Runs</h2>
		<ul class="mt-2 divide-y divide-neutral-200 rounded-xl border border-neutral-200 bg-white dark:divide-neutral-800 dark:border-neutral-800 dark:bg-neutral-950">
			{#each runs as run (run.id)}
				<li class="flex items-center gap-2 px-3 py-2 text-xs">
					<span class="truncate">{run.intent}</span>
					<span class="rounded-full bg-neutral-100 px-1.5 text-[10px] dark:bg-neutral-800">{run.intent_source}</span>
					<span class="text-neutral-400">{run.tool_count} tools</span>
					<span class="ml-auto flex items-center gap-1">
						<button type="button" aria-label="good run" onclick={() => verdict(run, 'good')} class="rounded px-1 hover:bg-emerald-50">👍</button>
						<button type="button" aria-label="bad run" onclick={() => verdict(run, 'bad')} class="rounded px-1 hover:bg-red-50">👎</button>
						{#if run.verdict}<span class="text-[10px] text-neutral-500">{run.verdict}</span>{/if}
					</span>
				</li>
			{:else}
				<li class="px-3 py-4 text-center text-xs text-neutral-400">ยังไม่มี run</li>
			{/each}
		</ul>
	</section>
</div>
