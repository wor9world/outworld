<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import ChatView from '#lib/components/ChatView.svelte';
	import Composer from '#lib/components/Composer.svelte';
	import ApprovalModal from '#lib/components/ApprovalModal.svelte';
	import RouteChip from '#lib/components/RouteChip.svelte';
	import StepLog from '#lib/components/StepLog.svelte';
	import { del, get, post, ApiError } from '#lib/api.ts';
	import { streamChat } from '#lib/stream.ts';
	import type { ApprovalRequest, Message, RouteDecision, ToolCall } from '#lib/types.ts';

	interface ChatPayload {
		chat: { id: string; title: string; project_id: string | null };
		messages: Message[];
		calls: ToolCall[];
		has_more: boolean;
	}

	let id = $derived(page.params.id ?? '');
	let chat = $state<ChatPayload['chat'] | null>(null);
	let messages = $state<Message[]>([]);
	let calls = $state<ToolCall[]>([]);
	let hasMore = $state(false);
	let route = $state<RouteDecision | null>(null);
	let running = $state(false);
	let streaming = $state('');
	let approval = $state<ApprovalRequest | null>(null);
	let error = $state('');
	let controller: AbortController | null = null;

	async function load(before?: number): Promise<void> {
		try {
			const query = before ? `?limit=100&before=${before}` : '?limit=100';
			const payload = await get<ChatPayload>(`/chats/${id}${query}`);
			chat = payload.chat;
			calls = payload.calls;
			hasMore = payload.has_more;
			messages = before ? [...payload.messages, ...messages] : payload.messages;
			error = '';
		} catch (caught) {
			error = caught instanceof Error ? caught.message : 'failed to load chat';
		}
	}

	$effect(() => {
		const chatId = id;
		if (!chatId) return;
		messages = [];
		calls = [];
		route = null;
		void load();
		return () => {
			controller?.abort();
			controller = null;
		};
	});

	async function send(text: string): Promise<void> {
		if (!id || running) return;
		running = true;
		error = '';
		streaming = '';
		messages = [
			...messages,
			{
				id: Date.now(),
				chat_id: id,
				role: 'user',
				content: text,
				meta_json: '{}',
				created_at: new Date().toISOString()
			}
		];
		controller = new AbortController();
		try {
			await streamChat(
				id,
				text,
				(event, data) => {
					if (event === 'delta') {
						streaming += String(data.text ?? '');
					} else if (event === 'route') {
						route = {
							intent: (data.intent as string) ?? null,
							rule_id: (data.rule_id as string) ?? null,
							confidence: 1,
							steps: null,
							explain: [],
							source: String(data.source ?? 'pipe')
						};
					} else if (event === 'tool') {
						calls = [
							...calls,
							{
								tool: String(data.tool ?? ''),
								status: 'running',
								ms: 0,
								args: (data.args as Record<string, unknown>) ?? {}
							}
						];
					} else if (event === 'tool_result') {
						calls = calls.map((call, index) =>
							index === calls.length - 1
								? { ...call, status: String(data.status ?? 'ok'), ms: Number(data.ms ?? 0) }
								: call
						);
					} else if (event === 'approval') {
						approval = {
							token: String(data.token ?? ''),
							tool: String(data.tool ?? ''),
							args: (data.args as Record<string, unknown>) ?? {}
						};
					} else if (event === 'error') {
						error = String(data.message ?? 'run failed');
					}
				},
				controller.signal
			);
		} catch (caught) {
			if (caught instanceof ApiError && caught.status === 409) {
				error = 'ยังไม่ได้ตั้ง provider — ข้อความนี้ไม่มี rule ใน pipe';
			} else if (!(caught instanceof DOMException)) {
				error = caught instanceof Error ? caught.message : 'stream failed';
			}
		} finally {
			running = false;
			streaming = '';
			controller = null;
			await load();
		}
	}

	async function decide(approve: boolean): Promise<void> {
		if (!approval) return;
		const token = approval.token;
		approval = null;
		try {
			await post(`/approvals/${token}`, { decision: approve ? 'approve' : 'deny' });
		} catch (caught) {
			error = caught instanceof Error ? caught.message : 'approval failed';
		}
	}

	async function removeChat(): Promise<void> {
		if (!id || !window.confirm('ลบแชทนี้?')) return;
		try {
			await del(`/chats/${id}`);
			await goto('/');
		} catch (caught) {
			error = caught instanceof Error ? caught.message : 'delete failed';
		}
	}
</script>

<div class="flex h-full flex-col">
	<header class="flex items-center gap-3 border-b border-neutral-200 px-4 py-3 dark:border-neutral-800">
		<h1 class="truncate text-sm font-medium">{chat?.title ?? 'Chat'}</h1>
		{#if route}
			<RouteChip {route} />
		{/if}
		<button
			type="button"
			onclick={removeChat}
			class="ml-auto rounded px-2 text-[11px] text-neutral-400 hover:text-red-600"
		>
			ลบแชท
		</button>
	</header>

	{#if error}
		<p class="border-b border-amber-300 bg-amber-50 px-4 py-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
			{error}
		</p>
	{/if}

	<ChatView
		{messages}
		{running}
		{hasMore}
		onmore={() => {
			const first = messages[0];
			if (first) void load(first.id);
		}}
	/>

	{#if streaming}
		<div class="px-4 pb-2">
			<p class="mx-auto max-w-3xl rounded-2xl border border-neutral-200 bg-white px-3 py-2 text-sm whitespace-pre-wrap dark:border-neutral-800 dark:bg-neutral-950">
				{streaming}
			</p>
		</div>
	{/if}

	<div class="px-4 pb-2">
		<div class="mx-auto max-w-3xl">
			<StepLog {calls} />
		</div>
	</div>

	<div class="px-4 pb-4">
		<div class="mx-auto max-w-3xl">
			<Composer onsend={send} disabled={running} placeholder="พิมพ์ข้อความ…" />
		</div>
	</div>
</div>

{#if approval}
	<ApprovalModal request={approval} ondecide={decide} />
{/if}
