<script lang="ts">
	import Icon from '../Icon.svelte';
	import { ApiError, generateSummary } from '../api';
	import { formatClock, parseChapterTime } from '../format';
	import type { Summary } from '../types';
	import { SvelteSet } from 'svelte/reactivity';

	/**
	 * Study summary panel. When no summary exists yet, offers generation
	 * (a slow LLM call) with a progress state.
	 */
	let {
		sessionId,
		summary,
		llmConfigured,
		onseek,
		onsummary
	}: {
		sessionId: string;
		summary: Summary | null;
		llmConfigured: boolean;
		onseek?: (time: number) => void;
		onsummary?: (summary: Summary) => void;
	} = $props();

	let generating = $state(false);
	let error = $state<string | null>(null);
	// SvelteSet (not a plain Set): add()/delete() must stay reactive.
	const checked = new SvelteSet<number>();

	async function handleGenerate() {
		generating = true;
		error = null;
		try {
			onsummary?.(await generateSummary(sessionId));
		} catch (e) {
			error =
				e instanceof ApiError && e.status === 503
					? 'No language model is configured. Set MINK_LLM_PROVIDER (e.g. ollama) on the server and try again.'
					: e instanceof Error
						? e.message
						: 'Summary generation failed.';
		} finally {
			generating = false;
		}
	}

	function toggleItem(i: number) {
		if (checked.has(i)) checked.delete(i);
		else checked.add(i);
	}
</script>

<div class="summary card">
	<div class="summary-head">
		<h2><Icon name="sparkles" size={18} /> Summary</h2>
		{#if summary?.model}
			<span class="badge">{summary.model}</span>
		{/if}
	</div>

	{#if summary}
		<section aria-label="TL;DR">
			<h3>TL;DR</h3>
			<p class="tldr">{summary.tldr}</p>
		</section>

		{#if summary.chapters.length > 0}
			<hr class="divider" />
			<section aria-label="Chapters">
				<h3>Chapters</h3>
				<div class="chapters">
					{#each summary.chapters as chapter, i (chapter.title + i)}
						<button
							class="chapter"
							onclick={() => onseek?.(parseChapterTime(chapter.start))}
							aria-label={`Seek to chapter ${chapter.title}`}
						>
							<div class="chapter-top">
								<span class="chapter-title">{chapter.title}</span>
								<span class="chapter-time muted">
									{formatClock(parseChapterTime(chapter.start))} – {formatClock(
										parseChapterTime(chapter.end)
									)}
								</span>
							</div>
							{#if chapter.bullets.length > 0}
								<ul>
									{#each chapter.bullets as bullet (bullet)}
										<li>{bullet}</li>
									{/each}
								</ul>
							{/if}
						</button>
					{/each}
				</div>
			</section>
		{/if}

		{#if summary.key_points.length > 0}
			<hr class="divider" />
			<section aria-label="Key points">
				<h3>Key points</h3>
				<ul class="points">
					{#each summary.key_points as point (point)}
						<li>{point}</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if summary.action_items.length > 0}
			<hr class="divider" />
			<section aria-label="Action items">
				<h3>Action items</h3>
				<ul class="actions">
					{#each summary.action_items as item, i (item)}
						<li>
							<button
								class="action"
								class:done={checked.has(i)}
								onclick={() => toggleItem(i)}
								aria-pressed={checked.has(i)}
							>
								<span class="checkbox" aria-hidden="true">
									{#if checked.has(i)}<Icon name="check" size={13} />{/if}
								</span>
								<span>{item}</span>
							</button>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if summary.terms.length > 0}
			<hr class="divider" />
			<section aria-label="Glossary">
				<h3>Glossary</h3>
				<dl class="glossary">
					{#each summary.terms as term (term.term)}
						<div class="term">
							<dt>{term.term}</dt>
							<dd class="muted">{term.definition}</dd>
						</div>
					{/each}
				</dl>
			</section>
		{/if}
	{:else}
		<div class="empty">
			{#if generating}
				<div class="spinner" role="status" aria-label="Generating summary"></div>
				<p><strong>Generating summary…</strong></p>
				<p class="muted small">
					The language model is reading the full transcript. This can take a few minutes for
					long lectures — feel free to keep browsing.
				</p>
			{:else}
				<Icon name="bookOpen" size={36} />
				<p><strong>No summary yet</strong></p>
				<p class="muted small">
					Generate a TL;DR, chapters, key points, action items, and a glossary from this
					lecture's transcript.
				</p>
				{#if !llmConfigured}
					<p class="warn"><Icon name="alert" size={15} /> No language model configured on the server.</p>
				{/if}
				<button class="btn btn-primary" onclick={handleGenerate} disabled={generating || !llmConfigured}>
					<Icon name="sparkles" size={17} /> Generate summary
				</button>
				{#if error}
					<p class="error" role="alert"><Icon name="alert" size={15} /> {error}</p>
				{/if}
			{/if}
		</div>
	{/if}
</div>

<style>
	.summary {
		padding: 1.4rem;
		display: flex;
		flex-direction: column;
		gap: 1.2rem;
	}

	.summary-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}

	.summary-head h2 {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 1.05rem;
	}

	section h3 {
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--muted-text);
		margin-bottom: 0.6rem;
	}

	.tldr {
		font-size: 1.02rem;
		line-height: 1.65;
	}

	.chapters {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}

	.chapter {
		text-align: left;
		background: rgba(148, 163, 184, 0.06);
		border: 1px solid rgba(148, 163, 184, 0.14);
		border-radius: var(--radius-md);
		padding: 0.75rem 0.9rem;
		cursor: pointer;
		font-family: var(--font);
		color: var(--text);
		transition:
			border-color 0.18s ease,
			background-color 0.18s ease;
		width: 100%;
	}

	.chapter:hover {
		border-color: rgba(34, 197, 94, 0.4);
		background: rgba(34, 197, 94, 0.06);
	}

	.chapter-top {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.75rem;
		margin-bottom: 0.35rem;
	}

	.chapter-title {
		font-weight: 700;
		font-size: 0.95rem;
	}

	.chapter-time {
		font-size: 0.78rem;
		font-variant-numeric: tabular-nums;
		flex: none;
	}

	.chapter ul,
	.points {
		margin: 0;
		padding-left: 1.1rem;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		font-size: 0.92rem;
		color: #cbd5e1;
	}

	.actions {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.action {
		display: flex;
		gap: 0.65rem;
		align-items: flex-start;
		background: none;
		border: none;
		padding: 0.35rem 0;
		cursor: pointer;
		font-family: var(--font);
		font-size: 0.92rem;
		color: var(--text);
		text-align: left;
		width: 100%;
		min-height: 44px;
	}

	.checkbox {
		flex: none;
		width: 22px;
		height: 22px;
		margin-top: 1px;
		border-radius: 6px;
		border: 1.5px solid var(--border);
		display: inline-flex;
		align-items: center;
		justify-content: center;
		color: #052e16;
		transition:
			background-color 0.18s ease,
			border-color 0.18s ease;
	}

	.action.done .checkbox {
		background: var(--accent);
		border-color: var(--accent);
	}

	.action.done span:last-child {
		text-decoration: line-through;
		color: var(--muted-text);
	}

	.glossary {
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
	}

	.term dt {
		font-weight: 700;
		font-size: 0.92rem;
	}

	.term dd {
		margin: 0.15rem 0 0;
		font-size: 0.9rem;
	}

	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		gap: 0.7rem;
		padding: 1.5rem 0.5rem;
		color: var(--muted-text);
	}

	.small {
		font-size: 0.88rem;
	}

	.warn {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		color: var(--warning);
		font-size: 0.88rem;
	}

	.error {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		color: var(--danger);
		font-size: 0.88rem;
	}
</style>
