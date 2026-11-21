<script lang="ts">
	import { goto } from '$app/navigation';
	import EmptyState from '#lib/components/EmptyState.svelte';
	import Composer from '#lib/components/Composer.svelte';
	import ListPane from '#lib/components/ListPane.svelte';
	import { get, post } from '#lib/api.ts';
	import type { Chat, Project } from '#lib/types.ts';

	let projects = $state<Project[]>([]);
	let chats = $state<Chat[]>([]);
	let sending = $state(false);
	let failure = $state('');

	$effect(() => {
		let alive = true;
		(async () => {
			try {
				const [nextProjects, nextChats] = await Promise.all([
					get<Project[]>('/projects'),
					get<Chat[]>('/chats?limit=10')
				]);
				if (!alive) return;
				projects = nextProjects;
				chats = nextChats;
			} catch (error) {
				failure = error instanceof Error ? error.message : 'failed to load';
			}
		})();
		return () => {
			alive = false;
		};
	});

	async function start(text: string) {
		if (!text.trim() || sending) return;
		sending = true;
		try {
			let projectId = projects[0]?.id;
			if (!projectId) {
				const created = await post<Project>('/projects', { name: 'Personal' });
				projectId = created.id;
			}
			const chat = await post<Chat>(`/projects/${projectId}/chats`, {});
			await post(`/chat/${chat.id}`, { content: text });
			await goto(`/chat/${chat.id}`);
		} catch (error) {
			failure = error instanceof Error ? error.message : 'failed to start chat';
		} finally {
			sending = false;
		}
	}

	const suggestions = [
		{ title: 'คำนวณ', body: '9.8-9.11=?' },
		{ title: 'แก้สมการ', body: '3^x=x^9' },
		{ title: 'วางแผน', body: 'วางแผน ทำระบบล็อกอิน' }
	];
</script>

<div class="mx-auto flex h-full max-w-3xl flex-col px-4">
	{#if failure}
		<p class="pt-4 text-xs text-red-600">{failure}</p>
	{/if}
	<EmptyState {suggestions} ongreet={start} />
	<div class="pb-4">
		<Composer onsend={start} disabled={sending} placeholder="พิมพ์ข้อความ…" />
	</div>
</div>
