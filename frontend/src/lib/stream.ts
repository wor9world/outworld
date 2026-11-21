import { ApiError, base } from '#lib/api.ts';

export type StreamHandler = (event: string, data: Record<string, unknown>) => void;

/** POST a message and dispatch each SSE event as it arrives. */
export async function streamChat(
	chatId: string,
	content: string,
	onEvent: StreamHandler,
	signal?: AbortSignal
): Promise<void> {
	const response = await fetch(`${base}/api/chat/${encodeURIComponent(chatId)}/stream`, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify({ content }),
		signal
	});

	if (!response.ok) {
		const body = await response.json().catch(() => ({ message: response.statusText }));
		throw new ApiError(response.status, String(body.message ?? response.statusText));
	}
	if (!response.body) {
		throw new ApiError(500, 'stream unavailable');
	}

	const reader = response.body.getReader();
	const decoder = new TextDecoder();
	let buffer = '';

	for (;;) {
		const { done, value } = await reader.read();
		if (done) break;
		buffer += decoder.decode(value, { stream: true });

		let boundary = buffer.indexOf('\n\n');
		while (boundary >= 0) {
			const block = buffer.slice(0, boundary);
			buffer = buffer.slice(boundary + 2);
			dispatch(block, onEvent);
			boundary = buffer.indexOf('\n\n');
		}
	}
}

function dispatch(block: string, onEvent: StreamHandler): void {
	let event = 'message';
	const payload: string[] = [];
	for (const line of block.split('\n')) {
		if (line.startsWith('event: ')) {
			event = line.slice(7).trim();
		} else if (line.startsWith('data: ')) {
			payload.push(line.slice(6));
		}
	}
	if (payload.length === 0) return;
	try {
		onEvent(event, JSON.parse(payload.join('\n')) as Record<string, unknown>);
	} catch {
		// A malformed frame is dropped rather than breaking the stream.
	}
}
