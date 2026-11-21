<script lang="ts">
	import Send from '@lucide/svelte/icons/send';

	let {
		onsend,
		disabled = false,
		placeholder = 'Message'
	}: {
		onsend: (text: string) => void;
		disabled?: boolean;
		placeholder?: string;
	} = $props();

	let text = $state('');
	let area = $state<HTMLTextAreaElement | null>(null);

	function grow(): void {
		if (!area) return;
		area.style.height = 'auto';
		area.style.height = `${Math.min(area.scrollHeight, 160)}px`;
	}

	function submit(): void {
		if (!text.trim() || disabled) return;
		onsend(text);
		text = '';
		grow();
	}

	function onkeydown(event: KeyboardEvent): void {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			submit();
		}
	}
</script>

<form
	onsubmit={(event) => {
		event.preventDefault();
		submit();
	}}
	class="flex items-end gap-2 rounded-2xl border border-neutral-300 bg-white p-2 dark:border-neutral-700 dark:bg-neutral-950"
>
	<textarea
		bind:this={area}
		bind:value={text}
		oninput={grow}
		{onkeydown}
		rows={1}
		{placeholder}
		aria-label="Message"
		class="max-h-40 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-neutral-400"
	></textarea>
	<button
		type="submit"
		disabled={disabled || !text.trim()}
		aria-label="Send message"
		class="flex size-9 items-center justify-center rounded-xl bg-neutral-900 text-white disabled:opacity-40 dark:bg-white dark:text-neutral-900"
	>
		<Send size={16} strokeWidth={1.75} />
	</button>
</form>
