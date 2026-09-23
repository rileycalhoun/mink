<script lang="ts">
	import { resolve } from '$app/paths';
	import Icon from '$lib/Icon.svelte';
	import AudioPlayer from '$lib/ui/AudioPlayer.svelte';
	import ExportMenu from '$lib/ui/ExportMenu.svelte';
	import SummaryPanel from '$lib/ui/SummaryPanel.svelte';
	import TranscriptView from '$lib/ui/TranscriptView.svelte';
	import { audioUrl, getSession } from '$lib/api';
	import { formatDate } from '$lib/format';
	import type { SessionDetail, Summary } from '$lib/types';

	let { data } = $props();

	// The summary is the only piece of page data the user can change in place
	// (generation reports back through onsummary); everything else reads from props.
	let generated = $state<Summary | null>(null);
	let liveSession = $state<SessionDetail | null>(null);
	const summary = $derived(generated ?? (data.session.summary as Summary | null));
	let seekTo = $state<number | null>(null);
	let currentTime = $state(0);

	const session = $derived(liveSession ?? data.session);
	const hasAudio = $derived(!!session.audio_path);
	const llmConfigured = $derived(
		!!data.health && !!data.health.llm.provider && data.health.llm.provider !== 'none'
	);
	// A session can land here before its transcript exists (live session still
	// finalizing, or transcription running server-side). Poll until it arrives.
	const awaitingTranscript = $derived(!session.transcript);

	$effect(() => {
		if (!awaitingTranscript) return;
		const id = data.session.id;
		const t = setInterval(async () => {
			try {
				const fresh = await getSession(id);
				if (fresh.transcript) liveSession = fresh;
			} catch {
				// Keep polling; the next tick retries.
			}
		}, 3000);
		return () => clearInterval(t);
	});

	function seek(t: number) {
		seekTo = t;
	}

	function handleTime(t: number) {
		currentTime = t;
	}
</script>

<div class="detail">
	<a class="back" href={resolve('/')}>

		<Icon name="arrowLeft" size={17} /> Library
	</a>

	<header class="detail-head">
		<div class="title-block">
			{#if session.course}<span class="chip">{session.course}</span>{/if}
			<h1>{session.title || 'Untitled lecture'}</h1>
			<p class="muted">{formatDate(session.created_at)}</p>
		</div>
		<div class="head-actions">
			{#if session.transcript}
				<ExportMenu sessionId={session.id} title={session.title} />
			{/if}
		</div>
	</header>

	{#if hasAudio}
		<AudioPlayer src={audioUrl(session.id)} bind:seekTo ontimeupdate={handleTime} />
	{/if}

	{#if session.transcript}
		<div class="content-grid">
			<section class="transcript-col card" aria-label="Transcript">
				<h2 class="col-title"><Icon name="fileText" size={18} /> Transcript</h2>
				<TranscriptView
					segments={session.transcript.segments}
					{currentTime}
					onseek={hasAudio ? seek : undefined}
				/>
			</section>
			<aside class="summary-col">
				<SummaryPanel
					sessionId={session.id}
					{summary}
					onsummary={(s) => (generated = s)}
					{llmConfigured}
					onseek={hasAudio ? seek : undefined}
				/>
			</aside>
		</div>
	{:else}
		<div class="empty card">
			<span class="spinner spinner-lg" role="status" aria-label="Transcription in progress"></span>
			<p><strong>Transcribing…</strong></p>
			<p class="muted">Your transcript is on its way. This page will update automatically.</p>
		</div>
	{/if}
</div>

<style>
	.detail {
		display: flex;
		flex-direction: column;
		gap: 1.4rem;
	}

	.back {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		text-decoration: none;
		color: var(--muted-text);
		font-weight: 600;
		font-size: 0.92rem;
		min-height: 44px;
		align-self: flex-start;
		padding: 0.4rem 0.6rem;
		margin-left: -0.6rem;
		border-radius: var(--radius-md);
		transition:
			color 0.18s ease,
			background-color 0.18s ease;
	}

	.back:hover {
		color: var(--text);
		background: rgba(148, 163, 184, 0.1);
	}

	.detail-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1.25rem;
		flex-wrap: wrap;
	}

	.title-block {
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
		align-items: flex-start;
	}

	.title-block h1 {
		font-size: 1.8rem;
		font-weight: 800;
	}

	.head-actions {
		display: flex;
		gap: 0.75rem;
		align-items: center;
	}

	.content-grid {
		display: grid;
		grid-template-columns: 7fr 5fr;
		gap: 1.25rem;
		align-items: start;
	}

	.transcript-col {
		padding: 1.4rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
		min-width: 0;
	}

	.col-title {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 1.05rem;
	}

	.summary-col {
		min-width: 0;
	}

	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		gap: 0.7rem;
		padding: 4rem 2rem;
		color: var(--muted-text);
	}

	@media (max-width: 960px) {
		.content-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
