<script lang="ts">
	import AppShell from '#lib/components/AppShell.svelte';
	import { get } from '#lib/api.ts';
	import type { Chat, Health, Project } from '#lib/types.ts';

	let { children } = $props();

	let projects = $state<Project[]>([]);
	let chats = $state<Chat[]>([]);
	let health = $state<Health | null>(null);
	let failure = $state('');

	$effect(() => {
		let alive = true;
		(async () => {
			try {
				const [nextProjects, nextChats, nextHealth] = await Promise.all([
					get<Project[]>('/projects'),
					get<Chat[]>('/chats?limit=20'),
					get<Health>('/health')
				]);
				if (!alive) return;
				projects = nextProjects;
				chats = nextChats;
				health = nextHealth;
				failure = '';
			} catch (error) {
				if (!alive) return;
				failure = error instanceof Error ? error.message : 'backend unreachable';
			}
		})();
		return () => {
			alive = false;
		};
	});
</script>

{#if failure}
	<div
		class="border-b border-amber-300 bg-amber-50 px-4 py-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200"
	>
		Backend unavailable: {failure} — start it with
		<code class="font-mono">uv run uvicorn app.main:app --port 8000</code>
	</div>
{/if}

<AppShell {projects} {chats} {health}>
	{@render children()}
</AppShell>
