<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import Icon from '$lib/Icon.svelte';
	import ConfirmDialog from '$lib/ui/ConfirmDialog.svelte';
	import Modal from '$lib/ui/Modal.svelte';
	import SessionCard from '$lib/ui/SessionCard.svelte';
	import { ApiError, deleteSession, listSessions, searchSessions, uploadAudio } from '$lib/api';
	import type { SearchHit, SessionListItem } from '$lib/types';

	let query = $state('');
	let all = $state.raw<SessionListItem[]>([]);
	let hits = $state.raw<SearchHit[] | null>(null);
	let loading = $state(true);
	let searching = $state(false);
	let error = $state<string | null>(null);

	// Upload modal state
	let showUpload = $state(false);
	let file = $state<File | null>(null);
	let upTitle = $state('');
	let upCourse = $state('');
	let dragging = $state(false);
	let uploading = $state(false);
	let transcribing = $state(false);
	let progress = $state(0);
	let uploadError = $state<string | null>(null);

	// Delete confirmation state
	let pendingDelete = $state<SessionListItem | null>(null);
	let deleteOpen = $state(false);
	let deleting = $state(false);
	let deleteError = $state<string | null>(null);

	$effect(() => {
		if (!deleteOpen) pendingDelete = null;
	});

	function askDelete(session: SessionListItem) {
		deleteError = null;
		pendingDelete = session;
		deleteOpen = true;
	}

	async function confirmDeleteSession() {
		if (!pendingDelete) return;
		deleting = true;
		deleteError = null;
		try {
			await deleteSession(pendingDelete.id);
			all = all.filter((s) => s.id !== pendingDelete!.id);
			deleteOpen = false;
		} catch (e) {
			deleteError = e instanceof Error ? e.message : 'Delete failed.';
		} finally {
			deleting = false;
		}
	}

	$effect(() => {
		listSessions()
			.then((s) => (all = s))
			.catch((e) => (error = e instanceof Error ? e.message : 'Failed to load sessions.'))
			.finally(() => (loading = false));
	});

	// Debounced search: empty query shows everything, otherwise hits /api/search.
	$effect(() => {
		const q = query.trim();
		if (!q) {
			hits = null;
			searching = false;
			return;
		}
		searching = true;
		const t = setTimeout(() => {
			searchSessions(q)
				.then((h) => (hits = h))
				.catch((e) => (error = e instanceof Error ? e.message : 'Search failed.'))
				.finally(() => (searching = false));
		}, 300);
		return () => clearTimeout(t);
	});

	const searchingMode = $derived(hits !== null);

	function badgeInfo(id: string): SessionListItem | undefined {
		return all.find((s) => s.id === id);
	}

	function pickFile(files: FileList | null) {
		if (files && files.length > 0) file = files[0];
	}

	async function handleUpload() {
		if (!file || uploading) return;
		uploading = true;
		transcribing = false;
		uploadError = null;
		progress = 0;
		try {
			const { id } = await uploadAudio(
				file,
				{ title: upTitle.trim(), course: upCourse.trim() },
				(f) => (progress = f),
				() => (transcribing = true)
			);
			showUpload = false;
			resetUpload();
			await goto(resolve(`/s/${id}`));
		} catch (e) {
			uploadError =
				e instanceof ApiError
					? e.message
					: e instanceof Error
						? e.message
						: 'Upload failed.';
		} finally {
			uploading = false;
			transcribing = false;
		}
	}

	function resetUpload() {
		file = null;
		upTitle = '';
		upCourse = '';
		progress = 0;
		transcribing = false;
		uploadError = null;
		dragging = false;
	}
</script>

<div class="library">
	<div class="hero">
		<div>
			<h1>Lecture library</h1>
			<p class="muted">
				{all.length === 0
					? 'Record your first lecture to get started.'
					: `${all.length} session${all.length === 1 ? '' : 's'} · fully local transcription`}
			</p>
		</div>
		<div class="actions">
			<a class="btn btn-primary" href={resolve('/live')}><Icon name="mic" size={18} /> Live record</a>
			<button class="btn btn-secondary" onclick={() => (showUpload = true)}>
				<Icon name="upload" size={18} /> Upload audio
			</button>
		</div>
	</div>

	<div class="search-row">
		<div class="search-box">
			<Icon name="search" size={18} />
			<input
				class="search-input"
				type="search"
				placeholder="Search titles, courses, transcripts…"
				bind:value={query}
				aria-label="Search sessions"
			/>
			{#if query}
				<button class="clear-btn" onclick={() => (query = '')} aria-label="Clear search">
					<Icon name="x" size={16} />
				</button>
			{/if}
		</div>
		{#if searching}<span class="spinner" role="status" aria-label="Searching"></span>{/if}
	</div>

	{#if error}
		<div class="notice error-notice" role="alert">
			<Icon name="alert" size={17} /> {error}
		</div>
	{/if}

	{#if loading}
		<div class="grid">
			{#each [1, 2, 3, 4, 5, 6] as i (i)}
				<div class="card skeleton" aria-hidden="true"></div>
			{/each}
		</div>
	{:else if searchingMode}
		{#if hits && hits.length > 0}
			<p class="muted result-count">
				{hits.length} result{hits.length === 1 ? '' : 's'} for “{query.trim()}”
			</p>
			<div class="hits">
				{#each hits as hit (hit.id)}
					{@const info = badgeInfo(hit.id)}
					<a class="hit card" href={resolve(`/s/${hit.id}`)}>
						<div class="hit-top">
							{#if hit.course}<span class="chip">{hit.course}</span>{/if}
							<div class="badges">
								{#if info?.has_transcript}<span class="badge badge-accent">Transcript</span>{/if}
								{#if info?.has_summary}<span class="badge badge-accent">Summary</span>{/if}
							</div>
						</div>
						<h3>{hit.title || 'Untitled lecture'}</h3>
						<ul class="matches">
							{#each hit.matches.slice(0, 3) as match (match)}
								<li>…{match.trim()}</li>
							{/each}
						</ul>
					</a>
				{/each}
			</div>
		{:else if !searching}
			<div class="empty card">
				<Icon name="search" size={36} />
				<p><strong>No matches</strong></p>
				<p class="muted">Nothing in your library matches “{query.trim()}”.</p>
			</div>
		{/if}
	{:else if all.length > 0}
		<div class="grid">
			{#each all as session (session.id)}
				<SessionCard {session} ondelete={() => askDelete(session)} />
			{/each}
		</div>
	{:else}
		<div class="empty card">
			<Icon name="mic" size={40} />
			<p><strong>No lectures yet</strong></p>
			<p class="muted">
				Hit <strong>Live record</strong> to transcribe a lecture in real time, or
				<strong>Upload audio</strong> to transcribe a recording.
			</p>
			<div class="actions">
				<a class="btn btn-primary" href={resolve('/live')}><Icon name="mic" size={18} /> Live record</a>
				<button class="btn btn-secondary" onclick={() => (showUpload = true)}>
					<Icon name="upload" size={18} /> Upload audio
				</button>
			</div>
		</div>
	{/if}
</div>

<Modal bind:open={showUpload} title="Upload audio" onclose={resetUpload}>
	<div class="upload-form">
		<label
			class="dropzone"
			class:dragging
			ondragover={(e) => {
				e.preventDefault();
				dragging = true;
			}}
			ondragleave={() => (dragging = false)}
			ondrop={(e) => {
				e.preventDefault();
				dragging = false;
				pickFile(e.dataTransfer?.files ?? null);
			}}
		>
			<input
				type="file"
				accept="audio/*,.wav,.mp3,.m4a,.ogg,.flac"
				hidden
				onchange={(e) => pickFile((e.target as HTMLInputElement).files)}
			/>
			<Icon name="upload" size={28} />
			{#if file}
				<strong>{file.name}</strong>
				<span class="muted">{(file.size / 1048576).toFixed(1)} MB · click to change</span>
			{:else}
				<strong>Drop an audio file here</strong>
				<span class="muted">or click to browse · WAV, MP3, M4A, …</span>
			{/if}
		</label>

		<div class="field">
			<label for="up-title">Title</label>
			<input id="up-title" class="input" bind:value={upTitle} placeholder="e.g. Lecture 4: Recursion" />
		</div>
		<div class="field">
			<label for="up-course">Course</label>
			<input id="up-course" class="input" bind:value={upCourse} placeholder="e.g. CS 101" />
		</div>

		{#if uploading}
			{#if transcribing}
				<div class="transcribing" role="status" aria-label="Transcribing">
					<span class="spinner" aria-hidden="true"></span>
					<p class="muted small">Transcribing audio… this can take a few minutes for a long lecture.</p>
				</div>
			{:else}
				<div class="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)} aria-label="Upload progress">
					<div class="progress-fill" style:width={`${progress * 100}%`}></div>
				</div>
				<p class="muted small">Uploading… transcription starts automatically.</p>
			{/if}
		{/if}

		{#if uploadError}
			<p class="error-text" role="alert"><Icon name="alert" size={15} /> {uploadError}</p>
		{/if}

		<div class="upload-actions">
			<button class="btn btn-ghost" onclick={() => (showUpload = false)} disabled={uploading}>
				Cancel
			</button>
			<button class="btn btn-primary" onclick={handleUpload} disabled={!file || uploading}>
				{#if uploading}<span class="spinner" aria-hidden="true"></span>{/if}
				Transcribe
			</button>
		</div>
	</div>
</Modal>

<ConfirmDialog
	bind:open={deleteOpen}
	title="Delete this session?"
	message={pendingDelete
		? `This permanently deletes "${pendingDelete.title || 'Untitled lecture'}" — its transcript, summary, and audio recording. This can't be undone.`
		: ''}
	confirmLabel="Delete session"
	busy={deleting}
	error={deleteError}
	onconfirm={confirmDeleteSession}
/>

<style>
	.library {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.hero {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1.25rem;
		flex-wrap: wrap;
	}

	.hero h1 {
		font-size: 1.9rem;
		font-weight: 800;
		margin-bottom: 0.35rem;
	}

	.actions {
		display: flex;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.search-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.search-box {
		position: relative;
		flex: 1;
		max-width: 560px;
		display: flex;
		align-items: center;
		color: var(--muted-text);
	}

	.search-box :global(svg) {
		position: absolute;
		left: 0.9rem;
		pointer-events: none;
	}

	.search-input {
		width: 100%;
		min-height: 48px;
		padding: 0.7rem 2.8rem 0.7rem 2.9rem;
		border-radius: var(--radius-lg);
		border: 1px solid rgba(148, 163, 184, 0.22);
		background: color-mix(in srgb, var(--card) 82%, transparent);
		color: var(--text);
		font-family: var(--font);
		font-size: 0.95rem;
		transition: border-color 0.18s ease;
	}

	.search-input:focus {
		outline: none;
		border-color: var(--accent);
		box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
	}

	.clear-btn {
		position: absolute;
		right: 0.6rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 36px;
		height: 36px;
		border-radius: 8px;
		border: none;
		background: transparent;
		color: var(--muted-text);
		cursor: pointer;
	}

	.clear-btn:hover {
		color: var(--text);
		background: rgba(148, 163, 184, 0.12);
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		gap: 1.1rem;
	}

	.skeleton {
		height: 150px;
		animation: shimmer 1.4s ease-in-out infinite;
	}

	@keyframes shimmer {
		0%,
		100% {
			opacity: 0.5;
		}
		50% {
			opacity: 0.85;
		}
	}

	.result-count {
		font-size: 0.9rem;
	}

	.hits {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}

	.hit {
		display: block;
		padding: 1.2rem 1.35rem;
		text-decoration: none;
		color: inherit;
		transition: border-color 0.18s ease;
	}

	.hit:hover {
		border-color: rgba(34, 197, 94, 0.4);
	}

	.hit-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 0.5rem;
	}

	.hit-top .badges {
		display: flex;
		gap: 0.4rem;
	}

	.hit h3 {
		font-size: 1.05rem;
		margin-bottom: 0.6rem;
	}

	.matches {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.matches li {
		font-size: 0.9rem;
		color: var(--muted-text);
		border-left: 2px solid var(--accent);
		padding-left: 0.7rem;
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

	.upload-form {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.dropzone {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		padding: 2.2rem 1.5rem;
		border: 1.5px dashed rgba(148, 163, 184, 0.35);
		border-radius: var(--radius-md);
		cursor: pointer;
		text-align: center;
		color: var(--muted-text);
		transition:
			border-color 0.18s ease,
			background-color 0.18s ease;
	}

	.dropzone:hover,
	.dropzone.dragging {
		border-color: var(--accent);
		background: rgba(34, 197, 94, 0.06);
		color: var(--text);
	}

	.dropzone strong {
		color: var(--text);
	}

	.progress {
		height: 8px;
		border-radius: 999px;
		background: var(--muted);
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: var(--accent);
		border-radius: 999px;
		transition: width 0.2s ease;
	}

	.transcribing {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 0;
	}

	.transcribing p {
		margin: 0;
	}

	.small {
		font-size: 0.85rem;
	}

	.error-text {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--danger);
		font-size: 0.9rem;
	}

	.upload-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
	}
</style>
