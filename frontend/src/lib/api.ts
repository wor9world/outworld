const base: string = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';

export class ApiError extends Error {
	status: number;

	constructor(status: number, message: string) {
		super(message);
		this.status = status;
	}
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
	const response = await fetch(`${base}/api${path}`, {
		...init,
		headers: { 'content-type': 'application/json', ...(init.headers ?? {}) }
	});
	if (response.status === 204) {
		return undefined as T;
	}
	const text = await response.text();
	let data: unknown = null;
	if (text) {
		try {
			data = JSON.parse(text);
		} catch {
			data = { message: text };
		}
	}
	if (!response.ok) {
		const message =
			data && typeof data === 'object' && 'message' in data
				? String((data as { message: unknown }).message)
				: response.statusText;
		throw new ApiError(response.status, message);
	}
	return data as T;
}

export function get<T>(path: string): Promise<T> {
	return request<T>(path);
}

export function post<T>(path: string, body: unknown = {}): Promise<T> {
	return request<T>(path, { method: 'POST', body: JSON.stringify(body) });
}

export function patch<T>(path: string, body: unknown): Promise<T> {
	return request<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
}

export function del(path: string): Promise<void> {
	return request<void>(path, { method: 'DELETE' });
}

export function absolute(path: string): string {
	return `${base}/api${path}`;
}

export { base };
