<script lang="ts">
	import ProviderForm from '#lib/components/ProviderForm.svelte';
	import ThemeToggle from '#lib/components/ThemeToggle.svelte';
	import { absolute, del, get, patch, post } from '#lib/api.ts';
	import type { Health, Provider } from '#lib/types.ts';

	let providers = $state<Provider[]>([]);
	let health = $state<Health | null>(null);
	let failure = $state('');
	let notice = $state('');
	let editing = $state<Provider | null>(null);

	async function load(): Promise<void> {
		try {
			[providers, health] = await Promise.all([
				get<Provider[]>('/providers'),
				get<Health>('/health')
			]);
		} catch (error) {
			failure = error instanceof Error ? error.message : 'failed to load settings';
		}
	}

	$effect(() => {
		void load();
	});

	async function save(data: Record<string, unknown>): Promise<void> {
		try {
			if (editing) {
				await patch(`/providers/${editing.id}`, data);
			} else {
				await post('/providers', data);
			}
			editing = null;
			notice = 'บันทึกแล้ว';
			await load();
		} catch (error) {
			failure = error instanceof Error ? error.message : 'save failed';
		}
	}

	async function remove(): Promise<void> {
		if (!editing) return;
		await del(`/providers/${editing.id}`);
		editing = null;
		await load();
	}

	async function probe(provider: Provider): Promise<void> {
		notice = 'testing…';
		try {
			const body = await post<{ ok: boolean; latency_ms?: number; error?: string }>(
				`/providers/${provider.id}/test`
			);
			notice = body.ok ? `ok in ${body.latency_ms}ms` : `failed: ${body.error}`;
		} catch (error) {
			notice = error instanceof Error ? error.message : 'test failed';
		}
	}
</script>

<div class="mx-auto flex max-w-3xl flex-col gap-6 p-4">
	<header class="flex items-center justify-between">
		<h1 class="text-lg font-semibold">Settings</h1>
		<ThemeToggle />
	</header>

	{#if failure}<p class="text-xs text-red-600">{failure}</p>{/if}
	{#if notice}<p class="text-xs text-emerald-600">{notice}</p>{/if}

	<section>
		<h2 class="text-[11px] uppercase tracking-wide text-neutral-500">Runtime</h2>
		<div class="mt-1 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
			<div class="rounded-lg border border-neutral-200 px-2 py-1.5 dark:border-neutral-800">
				<p class="text-neutral-500">python</p>
				<p class="font-mono">{health?.python ?? '—'}</p>
			</div>
			<div class="rounded-lg border border-neutral-200 px-2 py-1.5 dark:border-neutral-800">
				<p class="text-neutral-500">tools</p>
				<p class="font-mono">{health?.tools.length ?? 0}</p>
			</div>
			<div class="rounded-lg border border-neutral-200 px-2 py-1.5 dark:border-neutral-800">
				<p class="text-neutral-500">llm</p>
				<p class="font-mono">{health?.llm ?? '—'}</p>
			</div>
			<div class="rounded-lg border border-neutral-200 px-2 py-1.5 dark:border-neutral-800">
				<p class="text-neutral-500">schema</p>
				<p class="font-mono">{health?.schema ?? '—'}</p>
			</div>
		</div>
		<a href={absolute('/backup')} class="mt-2 inline-block text-xs underline">ดาวน์โหลด backup (.db)</a>
	</section>

	<section>
		<h2 class="text-[11px] uppercase tracking-wide text-neutral-500">Providers</h2>
		<ul class="mt-1 space-y-1">
			{#each providers as provider (provider.id)}
				<li class="flex items-center gap-2 rounded-lg border border-neutral-200 px-2 py-1.5 text-xs dark:border-neutral-800">
					<span class="font-medium">{provider.name}</span>
					<span class="text-neutral-500">{provider.kind} · {provider.model}</span>
					<span class="rounded-full px-1.5 {provider.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-neutral-100 text-neutral-500'}">
						{provider.enabled ? 'on' : 'off'}
					</span>
					<button type="button" onclick={() => probe(provider)} class="ml-auto underline">test</button>
					<button type="button" onclick={() => (editing = provider)} class="underline">แก้ไข</button>
				</li>
			{:else}
				<li class="text-xs text-neutral-400">ยังไม่มี provider — LLM จะเป็น disabled</li>
			{/each}
		</ul>

		<div class="mt-3">
			<ProviderForm
				provider={editing}
				onsave={save}
				ondelete={editing ? remove : undefined}
			/>
		</div>
	</section>
</div>
