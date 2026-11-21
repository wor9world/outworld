<script lang="ts">
	import type { Chat, Project } from '#lib/types.ts';

	interface Section {
		title: string;
		actionHref: string;
		actionLabel: string;
		items: { id: string; label: string; meta?: string; href: string }[];
	}

	let {
		projects = [],
		chats = []
	}: { projects?: Project[]; chats?: Chat[] } = $props();

	let sections = $derived<Section[]>([
		{
			title: 'Projects',
			actionHref: '/projects',
			actionLabel: '+ New project',
			items: projects.map((project) => ({
				id: project.id,
				label: project.name,
				meta: `${project.chat_count ?? 0} chats`,
				href: `/projects/${project.id}`
			}))
		},
		{
			title: 'Chats',
			actionHref: '/',
			actionLabel: '+ New chat',
			items: chats.map((chat) => ({
				id: chat.id,
				label: chat.title,
				meta: chat.project_name ?? 'unfiled',
				href: `/chat/${chat.id}`
			}))
		}
	]);
</script>

<div class="flex h-full flex-col gap-4 overflow-y-auto p-3">
	{#each sections as section (section.title)}
		<section>
			<div class="flex items-center justify-between px-2 pb-1">
				<h2 class="text-[11px] font-medium uppercase tracking-wide text-neutral-500">
					{section.title}
				</h2>
			</div>
			<a
				href={section.actionHref}
				class="block rounded-md px-2 py-1.5 text-sm text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-neutral-800 dark:hover:text-white"
			>
				{section.actionLabel}
			</a>
			{#if section.items.length === 0}
				<p class="px-2 py-1.5 text-xs text-neutral-400">ยังไม่มี</p>
			{/if}
			<ul class="mt-0.5 flex flex-col gap-0.5">
				{#each section.items as item (item.id)}
					<li>
						<a
							href={item.href}
							class="flex items-baseline justify-between gap-2 rounded-md px-2 py-1.5 text-sm text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
						>
							<span class="truncate">{item.label}</span>
							{#if item.meta}
								<span class="shrink-0 text-[11px] text-neutral-400">{item.meta}</span>
							{/if}
						</a>
					</li>
				{/each}
			</ul>
		</section>
	{/each}
</div>
