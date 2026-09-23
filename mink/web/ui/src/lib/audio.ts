/**
 * Microphone capture for live transcription.
 *
 * Uses an AudioWorklet (inlined via Blob URL) that mixes the mic input down
 * to mono, resamples to 16 kHz with linear interpolation, and posts 4096-sample
 * (~256 ms) Int16 frames to the main thread. A parallel AnalyserNode drives
 * the mic level meter.
 */

const WORKLET_SOURCE = `
class MinkCaptureProcessor extends AudioWorkletProcessor {
	constructor() {
		super();
		this.targetRate = 16000;
		this.ratio = sampleRate / this.targetRate;
		this.pos = 0;          // position (input samples) for next output sample
		this.prev = 0;         // last mono input sample of previous block
		this.frame = new Int16Array(4096);
		this.framePos = 0;
	}

	monoAt(input, i) {
		if (i < 0) return this.prev;
		let s = 0;
		for (let c = 0; c < input.length; c++) s += input[c][i];
		return s / input.length;
	}

	process(inputs) {
		const input = inputs[0];
		if (input && input.length > 0) {
			const n = input[0].length;
			for (;;) {
				const idx = this.pos;
				const i0 = Math.floor(idx);
				if (i0 + 1 >= n) break;
				const frac = idx - i0;
				const s = this.monoAt(input, i0) * (1 - frac) + this.monoAt(input, i0 + 1) * frac;
				const v = Math.max(-1, Math.min(1, s));
				this.frame[this.framePos++] = v < 0 ? Math.round(v * 32768) : Math.round(v * 32767);
				if (this.framePos >= this.frame.length) {
					this.port.postMessage(this.frame.buffer, [this.frame.buffer]);
					this.frame = new Int16Array(4096);
					this.framePos = 0;
				}
				this.pos += this.ratio;
			}
			this.prev = this.monoAt(input, n - 1);
			this.pos -= n;
		}
		return true;
	}
}
registerProcessor('mink-capture', MinkCaptureProcessor);
`;

export class AudioCapture {
	private stream: MediaStream | null = null;
	private ctx: AudioContext | null = null;
	private source: MediaStreamAudioSourceNode | null = null;
	private worklet: AudioWorkletNode | null = null;
	private analyser: AnalyserNode | null = null;
	private meterRaf = 0;
	private blobUrl: string | null = null;
	private running = false;

	/** Called with each ~256 ms Int16 mono @16kHz frame (transferred buffer). */
	onChunk: (buffer: ArrayBuffer) => void = () => {};
	/** Called ~60fps with mic level 0..1. */
	onLevel: (level: number) => void = () => {};

	get isRunning(): boolean {
		return this.running;
	}

	static async listDevices(): Promise<MediaDeviceInfo[]> {
		if (!navigator.mediaDevices?.enumerateDevices) return [];
		const devices = await navigator.mediaDevices.enumerateDevices();
		return devices.filter((d) => d.kind === 'audioinput');
	}

	async start(deviceId?: string): Promise<void> {
		if (this.running) return;
		if (!navigator.mediaDevices?.getUserMedia) {
			throw new Error('This browser does not support microphone capture.');
		}

		this.stream = await navigator.mediaDevices.getUserMedia({
			audio: deviceId
				? { deviceId: { exact: deviceId } }
				: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
		});

		this.ctx = new AudioContext();
		// Created from a click handler it should already run, but a suspended
		// context would silently capture nothing — make sure it is running.
		await this.ctx.resume();
		if (!this.blobUrl) {
			this.blobUrl = URL.createObjectURL(new Blob([WORKLET_SOURCE], { type: 'text/javascript' }));
		}
		await this.ctx.audioWorklet.addModule(this.blobUrl);

		this.source = this.ctx.createMediaStreamSource(this.stream);
		this.worklet = new AudioWorkletNode(this.ctx, 'mink-capture');
		this.worklet.port.onmessage = (event: MessageEvent<ArrayBuffer>) => {
			this.onChunk(event.data);
		};
		this.source.connect(this.worklet);

		this.analyser = this.ctx.createAnalyser();
		this.analyser.fftSize = 512;
		this.source.connect(this.analyser);
		const samples = new Uint8Array(this.analyser.fftSize);
		const tick = () => {
			if (!this.running || !this.analyser) return;
			this.analyser.getByteTimeDomainData(samples);
			let peak = 0;
			for (let i = 0; i < samples.length; i++) {
				const v = Math.abs(samples[i] - 128) / 128;
				if (v > peak) peak = v;
			}
			this.onLevel(Math.min(1, peak * 1.6));
			this.meterRaf = requestAnimationFrame(tick);
		};

		this.running = true;
		tick();
	}

	stop(): void {
		this.running = false;
		cancelAnimationFrame(this.meterRaf);
		try {
			this.worklet?.port.close();
		} catch {
			/* already closed */
		}
		this.worklet?.disconnect();
		this.source?.disconnect();
		this.analyser?.disconnect();
		this.stream?.getTracks().forEach((t) => t.stop());
		void this.ctx?.close();
		this.stream = null;
		this.ctx = null;
		this.source = null;
		this.worklet = null;
		this.analyser = null;
	}
}
