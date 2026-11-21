<script lang="ts">
	import type { Snippet } from 'svelte';
	import BookOpen from '@lucide/svelte/icons/book-open';
	import Brain from '@lucide/svelte/icons/brain';
	import FolderKanban from '@lucide/svelte/icons/folder-kanban';
	import GitBranch from '@lucide/svelte/icons/git-branch';
	import Home from '@lucide/svelte/icons/home';
	import Settings from '@lucide/svelte/icons/settings';
	import Wrench from '@lucide/svelte/icons/wrench';

	import ListPane from './ListPane.svelte';
	import Rail from './Rail.svelte';
	import ThemeToggle from './ThemeToggle.svelte';
	import type { Chat, Health, Project } from '#lib/types.ts';

	let {
		projects = [],
		chats = [],
		health = null,
		children
	}: {
		projects?: Project[];
		chats?: Chat[];
		health?: Health | null;
		children: Snippet;
	} = $props();

	const navigation = [
		{ href: '/', label: 'Home', icon: Home },
		{ href: '/projects', label: 'Projects', icon: FolderKanban },
		{ href: '/knowledge', label: 'Knowledge', icon: BookOpen },
		{ href: '/tools', label: 'Tools', icon: Wrench },
		{ href: '/learning', label: 'Learning', icon: Brain },
		{ href: '/pipe', label: 'Pipe', icon: GitBranch },
		{ href: '/settings', label: 'Settings', icon: Settings }
	];
</script>

<div class="grid h-full grid-cols-[64px_1fr] md:grid-cols-[64px_264px_1fr]">
	<Rail items={navigation} />

	<aside
		class="hidden min-h-0 flex-col border-r border-neutral-200 bg-white md:flex dark:border-neutral-800 dark:bg-neutral-950"
	>
		<div class="min-h-0 flex-1"><ListPane {projects} {chats} /></div>
		<div
			class="flex items-center justify-between gap-2 border-t border-neutral-200 px-3 py-2 dark:border-neutral-800"
		>
			<span
				class="rounded-full px-2 py-0.5 text-[11px] {health?.llm === 'enabled'
					? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
					: 'bg-neutral-100 text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400'}"
				title={health ? `${health.tools.length} tools · python ${health.python}` : 'backend offline'}
			>
				LLM: {health?.llm ?? 'offline'}
			</span>
			<ThemeToggle />
		</div>
	</aside>

	<main class="min-w-0 overflow-y-auto bg-neutral-50 dark:bg-neutral-900">
		{@render children()}
	</main>
</div>
