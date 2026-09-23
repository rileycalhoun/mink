/**
 * Client for the Mink live-transcription WebSocket (`/api/live/ws`).
 *
 * Protocol:
 *   -> {"type":"start","title?","course?","model?"}   <- {"type":"started","session_id"}
 *   -> binary 16-bit PCM mono @16kHz                  <- {"type":"partial","segments","text","duration"}
 *   -> {"type":"stop"}                                <- {"type":"finalizing"} … {"type":"done","session_id"}
 *   <- {"type":"finalize_progress","elapsed_s"}        (heartbeat every 15 s while finalizing)
 *   <- {"type":"error","message"}
 */

import type { LiveSegment } from './types';

export type LiveStatus = 'idle' | 'connecting' | 'listening' | 'finalizing' | 'error';

export interface LiveStartOptions {
	title?: string;
	course?: string;
	teacher?: string;
	folder_id?: string | null;
	model?: string;
}

export interface PartialMessage {
	segments: LiveSegment[];
	text: string;
	duration: number;
}

function wsUrl(): string {
	const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
	return `${proto}://${window.location.host}/api/live/ws`;
}

export class LiveClient {
	onStatus: (status: LiveStatus) => void = () => {};
	onPartial: (partial: PartialMessage) => void = () => {};
	onError: (message: string) => void = () => {};
	onFinalizeProgress: (elapsedS: number) => void = () => {};

	private ws: WebSocket | null = null;
	private startedResolve: ((sessionId: string) => void) | null = null;
	private startedReject: ((err: Error) => void) | null = null;
	private doneResolve: ((sessionId: string) => void) | null = null;
	private doneReject: ((err: Error) => void) | null = null;
	private settled = false;
	/** Watchdog: no server message for this long while finalizing ⇒ dead socket. */
	private finalizeTimer: ReturnType<typeof setTimeout> | null = null;

	private setStatus(status: LiveStatus) {
		this.onStatus(status);
	}

	/** Open the socket, send `start`, resolve with the session id on `started`. */
	connect(options: LiveStartOptions): Promise<string> {
		if (this.ws) throw new Error('Already connected');
		this.settled = false;
		this.setStatus('connecting');

		return new Promise((resolve, reject) => {
			this.startedResolve = resolve;
			this.startedReject = reject;

			let ws: WebSocket;
			try {
				ws = new WebSocket(wsUrl());
			} catch (err) {
				this.fail('Could not open the live transcription socket.');
				reject(err instanceof Error ? err : new Error(String(err)));
				return;
			}
			this.ws = ws;
			ws.binaryType = 'arraybuffer';

			ws.onopen = () => {
				ws.send(
					JSON.stringify({
						type: 'start',
						title: options.title ?? '',
						course: options.course ?? '',
						teacher: options.teacher ?? '',
						folder_id: options.folder_id ?? null,
						...(options.model ? { model: options.model } : {})
					})
				);
			};
			ws.onmessage = (event: MessageEvent) => {
				if (typeof event.data !== 'string') return;
				let msg: Record<string, unknown>;
				try {
					msg = JSON.parse(event.data);
				} catch {
					return;
				}
				this.handleMessage(msg);
			};
			ws.onerror = () => {
				if (!this.settled) this.fail('Connection to the transcription server failed.');
			};
			ws.onclose = () => {
				// A close at any point before done/error means the session died:
				// settle every pending promise so the UI never hangs.
				if (!this.settled) this.fail('The transcription server closed the connection.');
			};
		});
	}

	private handleMessage(msg: Record<string, unknown>): void {
		switch (msg.type) {
			case 'started': {
				this.setStatus('listening');
				this.startedResolve?.(String(msg.session_id ?? ''));
				this.startedResolve = null;
				this.startedReject = null;
				break;
			}
			case 'partial': {
				this.onPartial({
					segments: (msg.segments as LiveSegment[]) ?? [],
					text: String(msg.text ?? ''),
					duration: Number(msg.duration ?? 0)
				});
				break;
			}
			case 'finalizing': {
				this.setStatus('finalizing');
				this.armFinalizeWatchdog();
				break;
			}
			case 'finalize_progress': {
				this.onFinalizeProgress(Number(msg.elapsed_s ?? 0));
				this.armFinalizeWatchdog();
				break;
			}
			case 'done': {
				this.settled = true;
				this.clearFinalizeWatchdog();
				const id = String(msg.session_id ?? '');
				this.doneResolve?.(id);
				this.doneResolve = null;
				this.doneReject = null;
				this.close();
				break;
			}
			case 'error': {
				this.fail(String(msg.message ?? 'Transcription server error'));
				break;
			}
		}
	}

	private fail(message: string): void {
		if (this.settled) return;
		this.settled = true;
		this.clearFinalizeWatchdog();
		this.setStatus('error');
		const err = new Error(message);
		this.startedReject?.(err);
		this.doneReject?.(err);
		this.startedResolve = null;
		this.startedReject = null;
		this.doneResolve = null;
		this.doneReject = null;
		this.onError(message);
		this.close();
	}

	/** Stream one PCM frame to the server (no-op unless listening). */
	sendAudio(buffer: ArrayBuffer): void {
		if (this.ws?.readyState === WebSocket.OPEN) {
			this.ws.send(buffer);
		}
	}

	/**
	 * Ask the server to stop and run the final diarized pass.
	 * Resolves with the session id on `done`. Rejects on `error`.
	 * A watchdog fails the promise if the socket goes silent mid-finalize
	 * (half-open connections otherwise hang on "Finalizing…" forever).
	 */
	stop(): Promise<string> {
		return new Promise((resolve, reject) => {
			if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
				reject(new Error('Not connected'));
				return;
			}
			const prevOnError = this.onError;
			this.doneResolve = resolve;
			this.doneReject = reject;
			this.onError = (message) => {
				prevOnError(message);
				this.doneResolve = null;
				this.doneReject = null;
				reject(new Error(message));
			};
			this.setStatus('finalizing');
			this.armFinalizeWatchdog();
			this.ws.send(JSON.stringify({ type: 'stop' }));
		});
	}

	/**
	 * (Re)start the finalize watchdog: three missed 15 s heartbeats and the
	 * socket is treated as dead.
	 */
	private armFinalizeWatchdog(): void {
		this.clearFinalizeWatchdog();
		this.finalizeTimer = setTimeout(() => {
			this.finalizeTimer = null;
			this.fail('Lost connection to the transcription server during finalization.');
		}, 45_000);
	}

	private clearFinalizeWatchdog(): void {
		if (this.finalizeTimer !== null) {
			clearTimeout(this.finalizeTimer);
			this.finalizeTimer = null;
		}
	}

	close(): void {
		this.startedResolve = null;
		this.startedReject = null;
		this.doneResolve = null;
		this.doneReject = null;
		this.clearFinalizeWatchdog();
		if (this.ws) {
			try {
				this.ws.close();
			} catch {
				/* already closed */
			}
			this.ws = null;
		}
	}
}
