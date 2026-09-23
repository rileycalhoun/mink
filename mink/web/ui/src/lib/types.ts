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
	verdict?: SummaryVerdict;
}

export interface SummaryVerdict {
	faithfulness: 'faithful' | 'minor_drift' | 'unfaithful';
	faithfulness_confidence: number;
	quality_score: number;
	quality_confidence: number;
	action_items_probability: number;
	review_recommended: boolean;
	model: string;
	created_at: string;
}

export interface SessionDetail {
	id: string;
	title: string;
	course: string;
	teacher: string;
	folder_id: string | null;
	created_at: string;
	audio_path: string | null;
	transcript: Transcript | null;
	summary: Summary | null;
}

export interface SessionListItem {
	id: string;
	title: string;
	course: string;
	teacher: string;
	folder_id: string | null;
	created_at: string;
	has_transcript: boolean;
	has_summary: boolean;
	has_audio: boolean;
}

export interface Folder {
	id: string;
	name: string;
	created_at: string;
}

export interface SessionMetadataPatch {
	title?: string;
	course?: string;
	teacher?: string;
	folder_id?: string | null;
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

/** On-demand engine (RunPod pod) status. */
export interface EngineStatus {
	state: 'off' | 'provisioning' | 'ready' | 'error';
	configured: boolean;
	pod_id: string | null;
	gpu: string | null;
	price_per_hr: number | null;
	engine_url: string;
	uptime_s: number | null;
	idle_s: number | null;
	idle_timeout_s: number;
	error: string | null;
}

/** Cached tail of the provisioning pod's boot log. */
export interface EngineLog {
	pod_id: string | null;
	state: EngineStatus['state'];
	log: string;
}
