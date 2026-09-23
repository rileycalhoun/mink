<script lang="ts">
	import { resolve } from '$app/paths';
	import Icon from '../Icon.svelte';
	import { formatDate } from '../format';
	import type { SessionListItem } from '../types';

	let { session }: { session: SessionListItem } = $props();
</script>

<a class="session-card card" href={resolve(`/s/${session.id}`)}>
	<div class="card-top">
		{#if session.course}
			<span class="chip">{session.course}</span>
		{/if}
		<span class="date muted">{formatDate(session.created_at)}</span>
	</div>
	<h3 class="title">{session.title || 'Untitled lecture'}</h3>
	<div class="badges">
		{#if session.has_transcript}
			<span class="badge badge-accent"><Icon name="fileText" size={13} /> Transcript</span>
		{/if}
		{#if session.has_summary}
			<span class="badge badge-accent"><Icon name="sparkles" size={13} /> Summary</span>
		{/if}
		{#if session.has_audio}
			<span class="badge"><Icon name="headphones" size={13} /> Audio</span>
		{/if}
		{#if !session.has_transcript && !session.has_summary && !session.has_audio}
			<span class="badge">Empty</span>
		{/if}
	</div>
</a>

<style>
	.session-card {
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
		padding: 1.25rem;
		text-decoration: none;
		color: inherit;
		transition:
			transform 0.18s ease,
			border-color 0.18s ease,
			box-shadow 0.18s ease;
	}

	.session-card:hover {
		transform: translateY(-3px);
		border-color: rgba(34, 197, 94, 0.4);
		box-shadow:
			0 12px 32px rgba(2, 6, 23, 0.55),
			0 0 0 1px rgba(34, 197, 94, 0.12);
	}

	.card-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}

	.date {
		font-size: 0.8rem;
	}

	.title {
		font-size: 1.05rem;
		font-weight: 700;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.badges {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
		margin-top: auto;
	}
</style>
