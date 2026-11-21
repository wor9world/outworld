<script lang="ts">
	let {
		role,
		content,
		createdAt
	}: { role: string; content: string; createdAt?: string } = $props();

	let stamp = $derived(
		createdAt ? new Date(createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
	);
</script>

<article class="flex w-full flex-col gap-1 {role === 'user' ? 'items-end' : 'items-start'}">
	<div
		class="max-w-[85%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap {role === 'user'
			? 'bg-neutral-900 text-white dark:bg-white dark:text-neutral-900'
			: 'border border-neutral-200 bg-white text-neutral-800 dark:border-neutral-800 dark:bg-neutral-950 dark:text-neutral-200'}"
	>
		{content}
	</div>
	{#if stamp}
		<span class="px-1 text-[11px] text-neutral-400">{stamp}</span>
	{/if}
</article>
