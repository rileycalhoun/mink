<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onDestroy } from 'svelte';
	import { SvelteMap } from 'svelte/reactivity';
	import Icon from '$lib/Icon.svelte';
	import MicMeter from '$lib/ui/MicMeter.svelte';
	import { AudioCapture } from '$lib/audio';
	import { formatClock } from '$lib/format';
	import { LiveClient, type LiveStatus } from '$lib/live';
	import type { LiveSegment } from '$lib/types';

	let title = $state('');
	let course = $state('');
	let devices = $state<MediaDeviceInfo[]>([]);
	let deviceId = $state<string>('');
	let status = $state<LiveStatus>('idle');
	let elapsed = $state(0);
	let level = $state(0);
	let error = $state<string | null>(null);
	let autoScroll = $state(true);

	// Live segments merged by start time as partials stream in. SvelteMap is
	// deeply reactive on its own — no $state wrapper needed.
	const segMap = new SvelteMap<string, LiveSegment>();
	const segments = $derived(
		[...segMap.values()].sort((a, b) => a.start - b.start)
	);

	let capture: AudioCapture | null = null;
	let client: LiveClient | null = null;
	let timer: ReturnType<typeof setInterval> | null = null;
	let startedAt = 0;
	let transcriptEl: HTMLDivElement | undefined = $state();

	const STATUS_LABEL: Record<LiveStatus, string> = {
		idle: 'Ready',
		connecting: 'Connecting…',
		listening: 'Listening — speak now',
		finalizing: 'Finalizing — running the full diarized pass (this can take a few minutes)…',
		error: 'Something went wrong'
	};

	$effect(() => {
		void AudioCapture.listDevices().then((d) => (devices = d));
	});

	// Keep the transcript pinned to the bottom while new partials arrive.
	$effect(() => {
		if (autoScroll && transcriptEl && segments.length > 0) {
			transcriptEl.scrollTop = transcriptEl.scrollHeight;
		}
	});

	function startTimer() {
		startedAt = Date.now();
		elapsed = 0;
		timer = setInterval(() => {
			elapsed = (Date.now() - startedAt) / 1000;
		}, 500);
	}

	function stopTimer() {
		if (timer) clearInterval(timer);
		timer = null;
	}

	function cleanup() {
		stopTimer();
		capture?.stop();
		capture = null;
		client?.close();
		client = null;
		level = 0;
	}

	function friendlyMicError(e: unknown): string {
		if (e instanceof DOMException) {
			if (e.name === 'NotAllowedError')
				return 'Microphone access was denied. Allow microphone access in your browser and try again.';
			if (e.name === 'NotFoundError')
				return 'No microphone was found. Connect one and try again.';
			if (e.name === 'NotReadableError')
				return 'The microphone is in use by another app. Close it and try again.';
		}
		return e instanceof Error ? e.message : 'Could not access the microphone.';
	}

	async function start() {
		error = null;
		segMap.clear();

		const cap = new AudioCapture();
		const live = new LiveClient();
		capture = cap;
		client = live;

		live.onStatus = (s) => (status = s);
		live.onPartial = (p) => {
			for (const s of p.segments) segMap.set(s.start.toFixed(1), s);
		};
		live.onError = (m) => {
			error = m;
			cleanup();
		};

		try {
			// Mic first: the permission prompt (and any denial) surfaces here.
			cap.onChunk = (buf) => live.sendAudio(buf);
			cap.onLevel = (l) => (level = l);
			await cap.start(deviceId || undefined);
			devices = await AudioCapture.listDevices();

			await live.connect({ title: title.trim(), course: course.trim() });
		} catch (e) {
			error = e instanceof DOMException ? friendlyMicError(e) : e instanceof Error ? e.message : String(e);
			cleanup();
			status = 'idle';
			return;
		}

		startTimer();
	}

	async function stop() {
		if (!client) return;
		stopTimer();
		capture?.stop();
		capture = null;
		try {
			const id = await client.stop();
			client = null;
			await goto(resolve(`/s/${id}`));
		} catch (e) {
			error = e instanceof Error ? e.message : 'Finalization failed.';
		}
	}

	function handleUnload() {
		if (status === 'listening' || status === 'connecting') cleanup();
	}

	// Navigating away mid-session (e.g. via the nav) must also release the mic.
	onDestroy(() => cleanup());

	const busy = $derived(status === 'connecting' || status === 'listening' || status === 'finalizing');
</script>

<svelte:window onbeforeunload={handleUnload} />

<div class="live">
	<div class="live-head">
		<div>
			<h1>Live transcription</h1>
			<p class="muted">Transcribe a lecture in real time. A full diarized pass runs when you stop.</p>
		</div>
		<div class="status-line" role="status">
			<span class="pulse-dot" class:live={status === 'listening' || status === 'connecting'}></span>
			<span class={status === 'error' ? 'status-error' : ''}>{STATUS_LABEL[status]}</span>
		</div>
	</div>

	{#if error}
		<div class="notice error-notice" role="alert">
			<Icon name="alert" size={17} /> {error}
		</div>
	{/if}

	<div class="live-grid">
		<div class="controls card">
			<div class="field">
				<label for="live-title">Title</label>
				<input id="live-title" class="input" bind:value={title} placeholder="e.g. Lecture 5: Sorting" disabled={busy} />
			</div>
			<div class="field">
				<label for="live-course">Course</label>
				<input id="live-course" class="input" bind:value={course} placeholder="e.g. CS 101" disabled={busy} />
			</div>
			<div class="field">
				<label for="live-device">Microphone</label>
				<select id="live-device" class="input" bind:value={deviceId} disabled={busy || devices.length === 0}>
					<option value="">Default microphone</option>
					{#each devices as d, i (d.deviceId || i)}
						<option value={d.deviceId}>{d.label || `Microphone ${i + 1}`}</option>
					{/each}
				</select>
			</div>

			<MicMeter {level} />

			<div class="timer" aria-label="Elapsed time">
				<Icon name="clock" size={17} />
				<span class="timer-value">{formatClock(elapsed)}</span>
			</div>

			{#if status === 'idle' || status === 'error'}
				<button class="btn btn-primary btn-big" onclick={start}>
					<Icon name="mic" size={19} /> Start recording
				</button>
			{:else if status === 'finalizing'}
				<button class="btn btn-secondary btn-big" disabled>
					<span class="spinner" aria-hidden="true"></span> Finalizing…
				</button>
			{:else}
				<button class="btn btn-danger btn-big" onclick={stop}>
					<Icon name="square" size={17} /> Stop & finalize
				</button>
			{/if}
		</div>

		<div class="transcript-pane card">
			<div class="pane-head">
				<h2>Transcript</h2>
				<label class="autoscroll">
					<input type="checkbox" bind:checked={autoScroll} />
					Auto-scroll
				</label>
			</div>
			<div class="live-transcript scroll-thin" bind:this={transcriptEl} role="log" aria-label="Live transcript">
				{#if segments.length === 0}
					<div class="placeholder">
						<Icon name="activity" size={32} />
						<p class="muted">
							{status === 'listening'
								? 'Listening… your words will appear here.'
								: 'Press “Start recording” and start speaking.'}
						</p>
					</div>
				{:else}
					{#each segments as seg (`${seg.start.toFixed(1)}`)}
						<div class="seg">
							<span class="seg-time">{formatClock(seg.start)}</span>
							<span class="seg-text">{seg.text}</span>
						</div>
					{/each}
				{/if}
			</div>
		</div>
	</div>
</div>

<style>
	.live {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.live-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1.25rem;
		flex-wrap: wrap;
	}

	.live-head h1 {
		font-size: 1.9rem;
		font-weight: 800;
		margin-bottom: 0.35rem;
	}

	.status-line {
		display: inline-flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.6rem 1rem;
		border-radius: 999px;
		border: 1px solid rgba(148, 163, 184, 0.2);
		background: rgba(148, 163, 184, 0.07);
		font-size: 0.9rem;
		font-weight: 600;
	}

	.status-error {
		color: var(--danger);
	}

	.notice {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.9rem 1.1rem;
		border-radius: var(--radius-md);
		font-size: 0.92rem;
	}

	.error-notice {
		background: rgba(248, 113, 113, 0.1);
		border: 1px solid rgba(248, 113, 113, 0.3);
		color: #fca5a5;
	}

	.live-grid {
		display: grid;
		grid-template-columns: 340px 1fr;
		gap: 1.25rem;
		align-items: start;
	}

	.controls {
		display: flex;
		flex-direction: column;
		gap: 1.1rem;
		padding: 1.4rem;
		position: sticky;
		top: 96px;
	}

	.timer {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		color: var(--muted-text);
	}

	.timer-value {
		font-size: 1.6rem;
		font-weight: 800;
		font-variant-numeric: tabular-nums;
		color: var(--text);
		letter-spacing: 0.02em;
	}

	.btn-big {
		min-height: 52px;
		font-size: 1.02rem;
	}

	.transcript-pane {
		display: flex;
		flex-direction: column;
		min-height: 420px;
		max-height: calc(100vh - 240px);
	}

	.pane-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1.1rem 1.4rem;
		border-bottom: 1px solid rgba(148, 163, 184, 0.12);
	}

	.pane-head h2 {
		font-size: 1.05rem;
	}

	.autoscroll {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 0.85rem;
		color: var(--muted-text);
		cursor: pointer;
		min-height: 44px;
	}

	.autoscroll input {
		width: 18px;
		height: 18px;
		accent-color: var(--accent);
		cursor: pointer;
	}

	.live-transcript {
		flex: 1;
		overflow-y: auto;
		padding: 1.2rem 1.4rem;
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
	}

	.placeholder {
		margin: auto;
		text-align: center;
		color: var(--muted-text);
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.8rem;
		padding: 2rem;
	}

	.seg {
		display: flex;
		gap: 0.8rem;
		align-items: baseline;
		animation: fade-in 0.25s ease;
	}

	.seg-time {
		flex: none;
		font-size: 0.78rem;
		color: var(--muted-text);
		font-variant-numeric: tabular-nums;
		min-width: 3.4rem;
	}

	.seg-text {
		line-height: 1.6;
	}

	@keyframes fade-in {
		from {
			opacity: 0;
			transform: translateY(4px);
		}
	}

	@media (max-width: 900px) {
		.live-grid {
			grid-template-columns: 1fr;
		}

		.controls {
			position: static;
		}

		.transcript-pane {
			max-height: 60vh;
		}
	}
</style>
