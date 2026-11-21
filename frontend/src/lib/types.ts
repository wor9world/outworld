export interface Project {
	id: string;
	name: string;
	root_path: string;
	instructions?: string;
	updated_at: string;
	chat_count?: number;
}

export interface Chat {
	id: string;
	title: string;
	project_id: string | null;
	project_name?: string;
	updated_at: string;
	message_count?: number;
}

export interface Message {
	id: number;
	chat_id: string;
	role: 'user' | 'assistant' | 'tool' | 'system';
	content: string;
	meta_json: string;
	created_at: string;
}

export interface ToolCall {
	id?: number;
	chat_id?: string | null;
	run_id?: string | null;
	tool: string;
	status: string;
	ms: number;
	created_at?: string;
	error?: string | null;
	args_preview?: string;
	args?: Record<string, unknown>;
}

export interface Note {
	id: string;
	title: string;
	body?: string;
	tags: string;
	project_id: string | null;
	updated_at: string;
	snippet?: string;
}

export interface Tool {
	id: string;
	description: string;
	input_schema: Record<string, unknown>;
}

export interface Provider {
	id: string;
	name: string;
	kind: 'openai' | 'ollama';
	base_url: string;
	model: string;
	enabled: boolean;
}

export interface Health {
	status: string;
	python: string;
	version: string;
	tools: string[];
	llm: 'disabled' | 'enabled';
	db: string;
	schema: number;
	theme: string;
}

export interface Run {
	id: string;
	chat_id: string | null;
	intent: string;
	intent_source: 'pipe' | 'llm' | 'none';
	matched_rule: string | null;
	status: string;
	tool_count: number;
	iterations: number;
	started_at: string;
	ended_at: string | null;
	verdict?: 'good' | 'bad' | null;
}

export interface Pattern {
	id: string;
	name: string;
	intent: string;
	tool_chain: string[];
	uses: number;
	success: number;
	rate: number;
	last_used_at: string | null;
	enabled: boolean;
}

export interface LearningStats {
	runs_total: number;
	ok_rate: number;
	pipe_rate: number;
	patterns_total: number;
	top_patterns: { name: string; uses: number; success: number }[];
	recalls_24h: number;
}

export interface RouteDecision {
	intent: string | null;
	rule_id: string | null;
	confidence: number;
	steps: { tool: string; args: Record<string, unknown> }[] | null;
	explain: string[];
	source?: string;
	error?: string | null;
}

export interface ApprovalRequest {
	token: string;
	tool: string;
	args: Record<string, unknown>;
}
