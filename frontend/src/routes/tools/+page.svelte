<script lang="ts">
	import ApprovalModal from '#lib/components/ApprovalModal.svelte';
	import JsonBench from '#lib/components/JsonBench.svelte';
	import { get, post } from '#lib/api.ts';
	import type { ApprovalRequest, Tool } from '#lib/types.ts';

	let tools = $state<Tool[]>([]);
	let result = $state<Record<string, unknown> | null>(null);
	let approval = $state<ApprovalRequest | null>(null);
	let pending = $state<{ tool: string; args: Record<string, unknown> } | null>(null);
	let failure = $state('');

	$effect(() => {
		(get<Tool[]>('/tools') as Promise<Tool[]>)
			.then((rows) => (tools = rows))
			.catch((error: unknown) => {
				failure = error instanceof Error ? error.message : 'failed to load tools';
			});
	});

	async function run(tool: string, args: Record<string, unknown>): Promise<void> {
		failure = '';
		try {
			result = await post<Record<string, unknown>>(`/tools/${tool}`, args);
		} catch (error) {
			const maybe = error as { status?: number; message?: string } & Record<string, unknown>;
			if (maybe.status === 409) {
				result = maybe as unknown as Record<string, unknown>;
				const token = maybe.approval_token as string | undefined;
				if (token) {
					approval = { token, tool, args };
					pending = { tool, args };
				}
			} else {
				failure = maybe.message ?? 'run failed';
			}
		}
	}

	async function decide(approve: boolean): Promise<void> {
		if (!approval) return;
		const token = approval.token;
		approval = null;
		try {
			const body = await post<{ result?: Record<string, unknown> }>(
				`/approvals/${token}`,
				{ decision: approve ? 'approve' : 'deny' }
			);
			result = body.result ?? null;
		} catch (error) {
			failure = error instanceof Error ? error.message : 'approval failed';
		} finally {
			pending = null;
		}
	}
</script>

<div class="mx-auto grid max-w-5xl gap-4 p-4 lg:grid-cols-2">
	<section>
		<h1 class="text-lg font-semibold">Tool bench</h1>
		<p class="mt-1 text-xs text-neutral-500">รัน tool เดี่ยว ๆ ได้โดยไม่ต้องมี LLM</p>
		{#if failure}<p class="mt-2 text-xs text-red-600">{failure}</p>{/if}
		<div class="mt-4">
			<JsonBench {tools} onrun={run} />
		</div>
	</section>

	<section>
		<h2 class="text-[11px] uppercase tracking-wide text-neutral-500">Result</h2>
		<pre class="mt-1 min-h-40 overflow-auto rounded-xl border border-neutral-200 bg-white p-3 font-mono text-xs dark:border-neutral-800 dark:bg-neutral-950">{result
				? JSON.stringify(result, null, 2)
				: 'ยังไม่มีผลลัพธ์'}</pre>
	</section>
</div>

{#if approval}
	<ApprovalModal request={approval} ondecide={decide} />
{/if}
