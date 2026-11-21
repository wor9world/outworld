<script lang="ts">
	import { page } from '$app/state';
	import { del, get, patch, post } from '#lib/api.ts';
	import { refreshAll } from '$app/navigation';
	import type { Chat, Note, Project } from '#lib/types.ts';

	interface Payload {
		project: Project;
		chats: Chat[];
		notes: Note[];
		commands: { id: string; name: string; template: string; params: string[] }[];
	}

	let id = $derived(page.params.id ?? '');
	let payload = $state<Payload | null>(null);
	let instructions = $state('');
	let failure = $state('');
	let commandName = $state('');
	let commandTemplate = $state('');

	async function load(): Promise<void> {
		try {
			payload = await get<Payload>(`/projects/${id}`);
			instructions = payload.project.instructions ?? '';
		} catch (error) {
			failure = error instanceof Error ? error.message : 'failed to load';
		}
	}

	$effect(() => {
		void id;
		void load();
	});

	async function saveInstructions(): Promise<void> {
		await patch(`/projects/${id}`, { instructions });
		await refreshAll();
		await load();
	}

	async function newChat(): Promise<void> {
		const chat = await post<Chat>(`/projects/${id}/chats`, {});
		await load();
		window.location.href = `/chat/${chat.id}`;
	}

	async function addCommand(): Promise<void> {
		if (!commandName.trim() || !commandTemplate.trim()) return;
		await post(`/projects/${id}/commands`, {
			name: commandName.trim(),
			template: commandTemplate.trim()
		});
		commandName = '';
		commandTemplate = '';
		await load();
	}

	async function runCommand(command: { id: string; params: string[] }): Promise<void> {
		const params: Record<string, string> = {};
		for (const key of command.params) {
			const value = window.prompt(`ค่า ${key}`, '');
			if (value === null) return;
			params[key] = value;
		}
		try {
			const result = await post<{ data?: { stdout?: string } }>(`/commands/${command.id}/run`, {
				params
			});
			failure = result.data?.stdout?.trim() || 'ok';
		} catch (error) {
			failure =
				error instanceof Error && 'status' in error && error.status === 409
					? 'ต้องอนุมัติคำสั่งนี้ที่หน้า Tools'
					: error instanceof Error
						? error.message
						: 'run failed';
		}
	}

	async function remove(commandId: string): Promise<void> {
		await del(`/commands/${commandId}`);
		await load();
	}
</script>

<div class="mx-auto max-w-3xl p-4">
	{#if payload}
		<div class="flex items-center justify-between gap-2">
			<h1 class="text-lg font-semibold">{payload.project.name}</h1>
			<button type="button" onclick={newChat} class="rounded-lg bg-neutral-900 px-3 py-1.5 text-xs text-white dark:bg-white dark:text-neutral-900">
				+ New chat
			</button>
		</div>
		<p class="mt-1 text-xs text-neutral-500">{payload.project.root_path}</p>

		{#if failure}<p class="mt-2 text-xs text-amber-700">{failure}</p>{/if}

		<section class="mt-5">
			<h2 class="text-[11px] uppercase tracking-wide text-neutral-500">Instructions</h2>
			<textarea
				bind:value={instructions}
				rows={4}
				aria-label="Project instructions"
				class="mt-1 w-full rounded-lg border border-neutral-300 bg-white p-2 text-xs dark:border-neutral-700 dark:bg-neutral-950"
			></textarea>
			<button type="button" onclick={saveInstructions} class="mt-2 rounded-lg border border-neutral-300 px-3 py-1.5 text-xs dark:border-neutral-700">
				บันทึก
			</button>
		</section>

		<section class="mt-5">
			<h2 class="text-[11px] uppercase tracking-wide text-neutral-500">Chats</h2>
			<ul class="mt-1 divide-y divide-neutral-200 rounded-xl border border-neutral-200 dark:divide-neutral-800 dark:border-neutral-800">
				{#each payload.chats as chat (chat.id)}
					<li><a href={`/chat/${chat.id}`} class="block px-3 py-2 text-sm hover:bg-neutral-50 dark:hover:bg-neutral-900">{chat.title}</a></li>
				{:else}
					<li class="px-3 py-3 text-xs text-neutral-400">ยังไม่มีแชท</li>
				{/each}
			</ul>
		</section>

		<section class="mt-5">
			<h2 class="text-[11px] uppercase tracking-wide text-neutral-500">Commands</h2>
			<form
				onsubmit={(event) => {
					event.preventDefault();
					addCommand();
				}}
				class="mt-1 flex flex-col gap-2 sm:flex-row"
			>
				<input bind:value={commandName} placeholder="name" aria-label="Command name" class="rounded-lg border border-neutral-300 bg-white px-2 py-1.5 text-xs sm:w-32 dark:border-neutral-700 dark:bg-neutral-950" />
				<input bind:value={commandTemplate} placeholder={'git status {{path}}'} aria-label="Command template" class="flex-1 rounded-lg border border-neutral-300 bg-white px-2 py-1.5 font-mono text-xs dark:border-neutral-700 dark:bg-neutral-950" />
				<button type="submit" class="rounded-lg border border-neutral-300 px-3 py-1.5 text-xs dark:border-neutral-700">เพิ่ม</button>
			</form>
			<ul class="mt-2 space-y-1">
				{#each payload.commands as command (command.id)}
					<li class="flex items-center gap-2 rounded-lg border border-neutral-200 px-2 py-1.5 dark:border-neutral-800">
						<span class="text-xs font-medium">{command.name}</span>
						<code class="truncate font-mono text-[11px] text-neutral-500">{command.template}</code>
						<button type="button" onclick={() => runCommand(command)} class="ml-auto text-[11px] underline">run</button>
						<button type="button" onclick={() => remove(command.id)} class="text-[11px] text-red-600">ลบ</button>
					</li>
				{:else}
					<li class="text-xs text-neutral-400">ยังไม่มีคำสั่ง</li>
				{/each}
			</ul>
		</section>
	{:else}
		<p class="text-xs text-neutral-400">loading…</p>
	{/if}
</div>
