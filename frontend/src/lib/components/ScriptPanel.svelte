<script lang="ts">
	import PackagePlus from '@lucide/svelte/icons/package-plus';
	import Play from '@lucide/svelte/icons/play';
	import { post } from '#lib/api.ts';

	interface ScriptInfo {
		name: string;
		description: string;
		language: string;
		params: string[];
	}

	let {
		onresult
	}: { onresult: (result: Record<string, unknown>) => void } = $props();

	let scripts = $state<ScriptInfo[]>([]);
	let busy = $state('');
	let error = $state('');

	async function call(body: Record<string, unknown>): Promise<Record<string, unknown>> {
		return post<Record<string, unknown>>('/tools/script', body);
	}

	async function load(): Promise<void> {
		try {
			const response = await call({ op: 'list' });
			scripts = (response.data as { scripts: ScriptInfo[] }).scripts;
			error = '';
		} catch (caught) {
			error = caught instanceof Error ? caught.message : 'failed to list scripts';
		}
	}

	$effect(() => {
		void load();
	});

	async function install(): Promise<void> {
		try {
			const response = await call({ op: 'seed' });
			onresult(response);
			await load();
		} catch (caught) {
			error = caught instanceof Error ? caught.message : 'seed failed';
		}
	}

	async function run(script: ScriptInfo): Promise<void> {
		const params: Record<string, string> = {};
		for (const param of script.params) {
			const value = window.prompt(`ค่า ${param}`, '');
			if (value === null) return;
			params[param] = value;
		}
		busy = script.name;
		try {
			onresult(await call({ op: 'run', name: script.name, params_values: params }));
		} catch (caught) {
			error = caught instanceof Error ? caught.message : 'run failed';
		} finally {
			busy = '';
		}
	}
</script>

<section class="mt-6">
	<div class="flex items-center justify-between">
		<h2 class="text-[11px] uppercase tracking-wide text-neutral-500">Scripts</h2>
		<button
			type="button"
			onclick={install}
			class="inline-flex items-center gap-1 rounded-lg border border-neutral-300 px-2 py-1 text-[11px] dark:border-neutral-700"
		>
			<PackagePlus size={12} /> ติดตั้งชุดเริ่มต้น
		</button>
	</div>

	{#if error}
		<p class="mt-1 text-[11px] text-red-600">{error}</p>
	{/if}

	<ul class="mt-2 space-y-1">
		{#each scripts as script (script.name)}
			<li
				class="flex items-center gap-2 rounded-lg border border-neutral-200 px-2 py-1.5 dark:border-neutral-800"
			>
				<span class="font-mono text-xs">{script.name}</span>
				<span class="truncate text-[11px] text-neutral-500">{script.description}</span>
				{#if script.params.length > 0}
					<span class="shrink-0 rounded bg-neutral-100 px-1 text-[10px] dark:bg-neutral-800">
						{script.params.join(', ')}
					</span>
				{/if}
				<button
					type="button"
					onclick={() => run(script)}
					disabled={busy === script.name}
					aria-label={`Run ${script.name}`}
					class="ml-auto inline-flex items-center gap-1 rounded px-1.5 text-[11px] underline disabled:opacity-40"
				>
					<Play size={10} /> run
				</button>
			</li>
		{:else}
			<li class="text-[11px] text-neutral-400">
				ยังไม่มีสคริปต์ — กด "ติดตั้งชุดเริ่มต้น" เพื่อลง 7 ตัวที่ใช้บ่อย
			</li>
		{/each}
	</ul>
</section>
