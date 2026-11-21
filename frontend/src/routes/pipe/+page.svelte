<script lang="ts">
	import { get, post } from '#lib/api.ts';
	import type { RouteDecision } from '#lib/types.ts';

	let message = $state('9.8-9.11=?');
	let decision = $state<RouteDecision | null>(null);
	let result = $state<Record<string, unknown> | null>(null);
	let failure = $state('');
	let busy = $state(false);

	async function route(): Promise<void> {
		if (!message.trim()) return;
		failure = '';
		try {
			decision = await post<RouteDecision>('/pipe/route', { message });
		} catch (error) {
			failure = error instanceof Error ? error.message : 'route failed';
		}
	}

	async function run(): Promise<void> {
		busy = true;
		failure = '';
		try {
			result = await post<Record<string, unknown>>('/pipe/run', { message });
		} catch (error) {
			failure = error instanceof Error ? error.message : 'run failed';
		} finally {
			busy = false;
		}
	}

	async function reload(): Promise<void> {
		failure = '';
		try {
			const counts = await post<{ intents: number; plans: number }>('/pipe/reload');
			failure = `reloaded: ${counts.intents} intents, ${counts.plans} plans`;
		} catch (error) {
			failure = error instanceof Error ? error.message : 'reload failed';
		}
	}

	$effect(() => {
		void get('/health');
	});
</script>

<div class="mx-auto grid max-w-5xl gap-4 p-4 lg:grid-cols-2">
	<section>
		<div class="flex items-center justify-between">
			<h1 class="text-lg font-semibold">Pipe</h1>
			<button type="button" onclick={reload} class="text-xs underline">reload YAML</button>
		</div>
		<p class="mt-1 text-xs text-neutral-500">
			ทดสอบ routing ก่อนรัน — route ไม่แตะ tool และไม่เขียน audit
		</p>

		<textarea
			bind:value={message}
			rows={3}
			aria-label="Message to route"
			class="mt-3 w-full rounded-lg border border-neutral-300 bg-white p-3 font-mono text-sm dark:border-neutral-700 dark:bg-neutral-950"
		></textarea>

		<div class="mt-2 flex gap-2">
			<button type="button" onclick={route} class="rounded-lg border border-neutral-300 px-3 py-1.5 text-xs dark:border-neutral-700">route</button>
			<button type="button" onclick={run} disabled={busy} class="rounded-lg bg-neutral-900 px-3 py-1.5 text-xs text-white disabled:opacity-40 dark:bg-white dark:text-neutral-900">run</button>
		</div>

		{#if failure}<p class="mt-2 text-xs text-amber-700">{failure}</p>{/if}

		{#if decision}
			<div class="mt-4 rounded-xl border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-950">
				<p class="text-xs text-neutral-500">intent</p>
				<p class="font-mono text-sm">{decision.intent ?? 'no_route'}</p>
				<p class="mt-2 text-xs text-neutral-500">rule · confidence</p>
				<p class="font-mono text-xs">{decision.rule_id ?? '—'} · {decision.confidence}</p>
				{#if decision.steps}
					<p class="mt-2 text-xs text-neutral-500">steps</p>
					<ol class="mt-1 list-decimal space-y-1 pl-5 text-xs">
						{#each decision.steps as step}
							<li><span class="font-mono">{step.tool}</span> {JSON.stringify(step.args)}</li>
						{/each}
					</ol>
				{/if}
			</div>
		{/if}
	</section>

	<section>
		<h2 class="text-[11px] uppercase tracking-wide text-neutral-500">Result</h2>
		<pre class="mt-1 min-h-40 overflow-auto rounded-xl border border-neutral-200 bg-white p-3 font-mono text-xs dark:border-neutral-800 dark:bg-neutral-950">{result
				? JSON.stringify(result, null, 2)
				: 'ยังไม่มีผลลัพธ์'}</pre>
	</section>
</div>
