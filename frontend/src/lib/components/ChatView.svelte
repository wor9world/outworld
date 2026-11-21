<script lang="ts">
	import MessageBubble from './MessageBubble.svelte';
	import type { Message } from '#lib/types.ts';

	let {
		messages = [],
		running = false,
		hasMore = false,
		onmore
	}: {
		messages?: Message[];
		running?: boolean;
		hasMore?: boolean;
		onmore?: () => void;
	} = $props();

	let scroller = $state<HTMLDivElement | null>(null);

	$effect(() => {
		void messages.length;
		void running;
		const node = scroller;
		if (!node) return;
		node.scrollTop = node.scrollHeight;
	});
</script>

<div bind:this={scroller} class="flex-1 overflow-y-auto px-4 py-4">
	{#if hasMore && onmore}
		<div class="mb-3 flex justify-center">
			<button
				type="button"
				onclick={onmore}
				class="rounded-full border border-neutral-300 px-3 py-1 text-xs text-neutral-600 hover:bg-neutral-100 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
			>
				โหลดข้อความเก่า
			</button>
		</div>
	{/if}

	<div class="mx-auto flex max-w-3xl flex-col gap-4">
		{#each messages as message (message.id)}
			<MessageBubble
				role={message.role}
				content={message.content}
				createdAt={message.created_at}
			/>
		{/each}

		{#if running}
			<p class="text-xs text-neutral-400" aria-live="polite">กำลังทำงาน…</p>
		{/if}
	</div>
</div>
