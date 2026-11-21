<script lang="ts">
	import ShieldAlert from '@lucide/svelte/icons/shield-alert';
	import type { ApprovalRequest } from '#lib/types.ts';

	let {
		request,
		ondecide
	}: { request: ApprovalRequest; ondecide: (approve: boolean) => void } = $props();
</script>

<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
	<div
		role="dialog"
		aria-modal="true"
		aria-labelledby="approval-title"
		class="w-full max-w-lg rounded-2xl border border-neutral-200 bg-white p-4 shadow-xl dark:border-neutral-700 dark:bg-neutral-950"
	>
		<div class="flex items-center gap-2">
			<ShieldAlert size={18} class="text-amber-600" />
			<h2 id="approval-title" class="text-sm font-semibold">ต้องอนุมัติก่อนรัน</h2>
		</div>

		<p class="mt-2 text-xs text-neutral-500">
			tool <span class="font-mono">{request.tool}</span> ไม่อยู่ใน allowlist
		</p>

		<pre
			class="mt-3 max-h-40 overflow-auto rounded-lg bg-neutral-100 p-3 font-mono text-xs dark:bg-neutral-900">{JSON.stringify(
				request.args,
				null,
				2
			)}</pre>

		<div class="mt-4 flex justify-end gap-2">
			<button
				type="button"
				onclick={() => ondecide(false)}
				class="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm dark:border-neutral-700"
			>
				ปฏิเสธ
			</button>
			<button
				type="button"
				onclick={() => ondecide(true)}
				class="rounded-lg bg-neutral-900 px-3 py-1.5 text-sm text-white dark:bg-white dark:text-neutral-900"
			>
				อนุมัติ
			</button>
		</div>
	</div>
</div>
