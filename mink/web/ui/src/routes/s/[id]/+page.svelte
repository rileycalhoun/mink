<script lang="ts">
	import { resolve } from '$app/paths';
	import { goto } from '$app/navigation';
	import Icon from '$lib/Icon.svelte';
	import AudioPlayer from '$lib/ui/AudioPlayer.svelte';
	import ConfirmDialog from '$lib/ui/ConfirmDialog.svelte';
	import ExportMenu from '$lib/ui/ExportMenu.svelte';
	import Modal from '$lib/ui/Modal.svelte';
	import SummaryPanel from '$lib/ui/SummaryPanel.svelte';
	import TranscriptView from '$lib/ui/TranscriptView.svelte';
	import { audioUrl, createFolder, deleteSession, getSession, listFolders, updateSession } from '$lib/api';
	import { formatDate } from '$lib/format';
	import type { Folder, SessionDetail, Summary } from '$lib/types';

	let { data } = $props();

	// The summary is the only piece of page data the user can change in place
	// (generation reports back through onsummary); everything else reads from props.
	let generated = $state<Summary | null>(null);
	let liveSession = $state<SessionDetail | null>(null);
	let editedSession = $state<SessionDetail | null>(null);
	const summary = $derived(generated ?? (data.session.summary as Summary | null));
	let seekTo = $state<number | null>(null);
	let currentTime = $state(0);
	let confirmDelete = $state(false);
	let deleting = $state(false);
	let deleteError = $state<string | null>(null);

	// Editable metadata (title/course/teacher/folder)
	let folders = $state<Folder[]>([]);
	let editOpen = $state(false);
	let editBusy = $state(false);
	let editError = $state<string | null>(null);
	let editTitle = $state('');
	let editCourse = $state('');
	let editTeacher = $state('');
	let editFolderId = $state('');
	let editNewFolder = $state('');
	let editShowNewFolder = $state(false);

	$effect(() => {
		listFolders()
			.then((f) => (folders = f))
			.catch(() => {});
	});

	function openEdit() {
		const s = session;
		editTitle = s.title;
		editCourse = s.course;
		editTeacher = s.teacher;
		editFolderId = s.folder_id ?? '';
		editNewFolder = '';
		editShowNewFolder = false;
		editError = null;
		editOpen = true;
	}

	async function submitEdit() {
		editBusy = true;
		editError = null;
		try {
			let folderId: string | null = editFolderId || null;
			if (editShowNewFolder && editNewFolder.trim()) {
				const folder = await createFolder(editNewFolder.trim());
				folders = [...folders.filter((f) => f.id !== folder.id), folder].sort((a, b) =>
					a.name.localeCompare(b.name)
				);
				folderId = folder.id;
			}
			editedSession = await updateSession(session.id, {
				title: editTitle.trim(),
				course: editCourse.trim(),
				teacher: editTeacher.trim(),
				folder_id: folderId
			});
			editOpen = false;
		} catch (e) {
			editError = e instanceof Error ? e.message : 'Could not save changes.';
		} finally {
			editBusy = false;
		}
	}

	async function handleDelete() {
		deleting = true;
		deleteError = null;
		try {
			await deleteSession(data.session.id);
			await goto(resolve('/'));
		} catch (e) {
			deleteError = e instanceof Error ? e.message : 'Delete failed.';
		} finally {
			deleting = false;
			if (!deleteError) confirmDelete = false;
		}
	}

	const session = $derived(editedSession ?? liveSession ?? data.session);
	const hasAudio = $derived(!!session.audio_path);
	const folderName = $derived(folders.find((f) => f.id === session.folder_id)?.name ?? null);
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
			<dl class="meta">
				<div>
					<dt>Recorded</dt>
					<dd>{formatDate(session.created_at)}</dd>
				</div>
				{#if session.teacher}
					<div>
						<dt>Teacher</dt>
						<dd>{session.teacher}</dd>
					</div>
				{/if}
				{#if folderName}
					<div>
						<dt>Folder</dt>
						<dd><Icon name="folder" size={13} /> {folderName}</dd>
					</div>
				{/if}
			</dl>
		</div>
		<div class="head-actions">
			{#if session.transcript}
				<ExportMenu sessionId={session.id} title={session.title} />
			{/if}
			<button class="btn btn-ghost" onclick={openEdit} aria-label="Edit session details">
				<Icon name="pencil" size={15} /> Edit
			</button>
			<button
				class="btn btn-ghost btn-danger-ghost"
				onclick={() => {
					deleteError = null;
					confirmDelete = true;
				}}
				aria-label="Delete this session"
			>
				<Icon name="trash" size={15} /> Delete
			</button>
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
					text={session.transcript.text}
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

<ConfirmDialog
	bind:open={confirmDelete}
	title="Delete this session?"
	message={`This permanently deletes "${session.title || 'Untitled lecture'}" — its transcript, summary, and audio recording. This can't be undone.`}
	confirmLabel="Delete session"
	busy={deleting}
	error={deleteError}
	onconfirm={handleDelete}
/>

<Modal bind:open={editOpen} title="Edit session details">
	<div class="edit-form">
		<div class="field">
			<label for="edit-title">Title</label>
			<input id="edit-title" class="input" bind:value={editTitle} disabled={editBusy} />
		</div>
		<div class="field-row">
			<div class="field">
				<label for="edit-course">Course</label>
				<input
					id="edit-course"
					class="input"
					bind:value={editCourse}
					placeholder="e.g. Anthropology C1001"
					disabled={editBusy}
				/>
			</div>
			<div class="field">
				<label for="edit-teacher">Teacher</label>
				<input
					id="edit-teacher"
					class="input"
					bind:value={editTeacher}
					placeholder="e.g. Dr. Alvarez"
					disabled={editBusy}
				/>
			</div>
		</div>
		<div class="field">
			<label for="edit-folder">Folder</label>
			{#if editShowNewFolder}
				<div class="folder-new">
					<input
						id="edit-folder"
						class="input"
						bind:value={editNewFolder}
						placeholder="New folder name"
						disabled={editBusy}
						aria-label="New folder name"
					/>
					<button
						class="btn btn-ghost"
						disabled={editBusy}
						onclick={() => {
							editShowNewFolder = false;
							editNewFolder = '';
						}}
					>
						Cancel
					</button>
				</div>
			{:else}
				<select
					id="edit-folder"
					class="input"
					bind:value={editFolderId}
					disabled={editBusy}
					onchange={(e) => {
						if ((e.target as HTMLSelectElement).value === '__new__') {
							editFolderId = '';
							editShowNewFolder = true;
						}
					}}
				>
					<option value="">No folder</option>
					{#each folders as folder (folder.id)}
						<option value={folder.id}>{folder.name}</option>
					{/each}
					<option value="__new__">+ New folder…</option>
				</select>
			{/if}
		</div>
		{#if editError}
			<p class="error-text" role="alert"><Icon name="alert" size={15} /> {editError}</p>
		{/if}
		<div class="edit-actions">
			<button class="btn btn-ghost" onclick={() => (editOpen = false)} disabled={editBusy}>
				Cancel
			</button>
			<button class="btn btn-primary" onclick={submitEdit} disabled={editBusy}>
				{editBusy ? 'Saving…' : 'Save changes'}
			</button>
		</div>
	</div>
</Modal>

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

	.meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1.75rem;
		margin: 0;
	}

	.meta > div {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
	}

	.meta dt {
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--muted-text);
	}

	.meta dd {
		margin: 0;
		font-size: 0.95rem;
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}

	.edit-form {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.field-row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}

	.folder-new {
		display: flex;
		gap: 0.5rem;
	}

	.folder-new .input {
		flex: 1;
	}

	.edit-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
		margin-top: 0.5rem;
	}

	.error-text {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--danger);
		font-size: 0.9rem;
	}

	.head-actions {
		display: flex;
		gap: 0.75rem;
		align-items: center;
	}

	.btn-danger-ghost {
		color: var(--muted-text);
	}

	.btn-danger-ghost:hover:not(:disabled) {
		color: #f87171;
		border-color: rgba(248, 113, 113, 0.5);
		background: rgba(248, 113, 113, 0.08);
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
