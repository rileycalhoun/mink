/** Typed fetch wrappers for the Mink FastAPI backend (same origin). */

import type {
	EngineStatus,
	HealthResponse,
	SearchHit,
	SessionDetail,
	SessionListItem,
	Summary
} from './types';

export class ApiError extends Error {
	readonly status: number;

	constructor(status: number, message: string) {
		super(message);
		this.name = 'ApiError';
		this.status = status;
	}
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
	const res = await fetch(path, init);
	if (!res.ok) {
		let detail = res.statusText || `Request failed (${res.status})`;
		try {
			const body = await res.json();
			if (typeof body?.detail === 'string') detail = body.detail;
		} catch {
			/* keep default */
		}
		throw new ApiError(res.status, detail);
	}
	return (await res.json()) as T;
}

export const getHealth = () => api<HealthResponse>('/api/health');

export const getEngineStatus = () => api<EngineStatus>('/api/engine');

export const startEngine = () =>
	api<EngineStatus>('/api/engine/start', { method: 'POST' });

export const stopEngine = () =>
	api<EngineStatus>('/api/engine/stop', { method: 'POST' });

export const listSessions = () => api<SessionListItem[]>('/api/sessions');

export const getSession = (id: string) =>
	api<SessionDetail>(`/api/sessions/${encodeURIComponent(id)}`);

export const searchSessions = (q: string) =>
	api<SearchHit[]>(`/api/search?q=${encodeURIComponent(q)}`);

export const getSummary = (id: string) =>
	api<Summary>(`/api/sessions/${encodeURIComponent(id)}/summary`);

export const generateSummary = (id: string) =>
	api<Summary>(`/api/sessions/${encodeURIComponent(id)}/summary`, { method: 'POST' });

export const audioUrl = (id: string) => `/api/sessions/${encodeURIComponent(id)}/audio`;

export type ExportFormat = 'md' | 'txt' | 'srt' | 'vtt';

export const exportUrl = (id: string, format: ExportFormat) =>
	`/api/sessions/${encodeURIComponent(id)}/export?format=${format}`;

export interface UploadMeta {
	title?: string;
	course?: string;
	model?: string;
	language?: string;
}

/**
 * Upload an audio file for transcription. Uses XHR because fetch has no
 * upload-progress events.
 */
export function uploadAudio(
	file: File,
	meta: UploadMeta,
	onProgress?: (fraction: number) => void
): Promise<{ id: string; path: string }> {
	return new Promise((resolve, reject) => {
		const xhr = new XMLHttpRequest();
		xhr.open('POST', '/api/transcribe');
		xhr.responseType = 'json';

		xhr.upload.onprogress = (e) => {
			if (e.lengthComputable) onProgress?.(e.loaded / e.total);
		};
		xhr.onload = () => {
			if (xhr.status >= 200 && xhr.status < 300) {
				resolve(xhr.response as { id: string; path: string });
			} else {
				const detail =
					typeof xhr.response?.detail === 'string'
						? xhr.response.detail
						: `Upload failed (${xhr.status})`;
				reject(new ApiError(xhr.status, detail));
			}
		};
		xhr.onerror = () => reject(new ApiError(0, 'Upload failed: network error'));
		xhr.onabort = () => reject(new ApiError(0, 'Upload cancelled'));

		const form = new FormData();
		form.append('file', file);
		if (meta.title) form.append('title', meta.title);
		if (meta.course) form.append('course', meta.course);
		if (meta.model) form.append('model', meta.model);
		if (meta.language) form.append('language', meta.language);
		xhr.send(form);
	});
}
