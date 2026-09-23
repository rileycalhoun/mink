/** Shared TypeScript types mirroring the FastAPI API contract. */

export interface Segment {
	start: number;
	end: number;
	text: string;
	speaker: string | null;
}

export interface Transcript {
	text: string;
	language: string | null;
	segments: Segment[];
}

export interface Chapter {
	title: string;
	/** "mm:ss" */
	start: string;
	/** "mm:ss" */
	end: string;
	bullets: string[];
}

export interface TermDef {
	term: string;
	definition: string;
}

export interface Summary {
	tldr: string;
	chapters: Chapter[];
	key_points: string[];
	action_items: string[];
	terms: TermDef[];
	model: string;
	created_at: string;
}

export interface SessionDetail {
	id: string;
	title: string;
	course: string;
	created_at: string;
	audio_path: string | null;
	transcript: Transcript | null;
	summary: Summary | null;
}

export interface SessionListItem {
	id: string;
	title: string;
	course: string;
	created_at: string;
	has_transcript: boolean;
	has_summary: boolean;
	has_audio: boolean;
}

export interface SearchHit {
	id: string;
	title: string;
	course: string;
	matches: string[];
}

export interface LlmStatus {
	provider: string | null;
	model: string | null;
	reachable: boolean;
}

export interface HealthResponse {
	status: string;
	version: string;
	engine_reachable: boolean;
	engine_url: string;
	llm: LlmStatus;
}

/** Live-transcription partial segment (no speaker labels until final pass). */
export interface LiveSegment {
	start: number;
	end: number;
	text: string;
}
