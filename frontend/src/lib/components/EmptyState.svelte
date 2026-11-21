<script lang="ts">
	let {
		ongreet,
		suggestions = []
	}: {
		ongreet: (text: string) => void;
		suggestions?: { title: string; body: string }[];
	} = $props();
</script>

<div class="flex flex-1 flex-col items-center justify-center gap-6 py-10">
	<div class="text-center">
		<h1 class="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">
			มีอะไรให้ช่วยวันนี้
		</h1>
		<p class="mt-1 text-sm text-neutral-500">ทำงานในเครื่องนี้ ไม่ต้องมี key ก็ใช้ tool ได้</p>
	</div>

	<div class="grid w-full gap-3 sm:grid-cols-3">
		{#each suggestions as card (card.title)}
			<button
				type="button"
				onclick={() => ongreet(card.body)}
				class="rounded-xl border border-neutral-200 bg-white p-4 text-left hover:border-neutral-400 dark:border-neutral-800 dark:bg-neutral-950 dark:hover:border-neutral-600"
			>
				<span class="block text-[13px] font-medium text-neutral-900 dark:text-neutral-100">
					{card.title}
				</span>
				<span class="mt-1 block font-mono text-[13px] text-neutral-500">{card.body}</span>
			</button>
		{/each}
	</div>
</div>
