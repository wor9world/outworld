<script lang="ts">
	import type { Component } from 'svelte';
	import { page } from '$app/state';

	interface Item {
		href: string;
		label: string;
		icon: Component;
	}

	let { items = [] }: { items?: Item[] } = $props();

	let path = $derived(page.url.pathname);

	function isActive(href: string): boolean {
		if (href === '/') return path === '/';
		return path === href || path.startsWith(href + '/');
	}
</script>

<nav
	aria-label="Primary"
	class="flex h-full w-16 flex-col items-center gap-1 border-r border-neutral-200 bg-white py-3 dark:border-neutral-800 dark:bg-neutral-950"
>
	<div
		class="mb-2 flex size-10 items-center justify-center rounded-xl bg-neutral-900 text-sm font-semibold text-white dark:bg-white dark:text-neutral-900"
		title="Outworld"
	>
		O
	</div>

	{#each items as item (item.href)}
		{@const Icon = item.icon}
		<a
			href={item.href}
			aria-current={isActive(item.href) ? 'page' : undefined}
			title={item.label}
			class="flex size-10 items-center justify-center rounded-lg text-neutral-600 transition-colors hover:bg-neutral-100 hover:text-neutral-900 aria-[current=page]:bg-neutral-900 aria-[current=page]:text-white dark:text-neutral-400 dark:hover:bg-neutral-800 dark:hover:text-white dark:aria-[current=page]:bg-white dark:aria-[current=page]:text-neutral-900"
		>
			<Icon size={20} strokeWidth={1.75} />
			<span class="sr-only">{item.label}</span>
		</a>
	{/each}
</nav>
