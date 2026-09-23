<script lang="ts">
	import { formatClock } from '../format';
	import { prettySpeaker, speakerColor } from '../speakers';
	import type { Segment } from '../types';

	/**
	 * Clickable, timestamped transcript. The active segment (by `currentTime`)
	 * is highlighted; clicking a segment seeks the audio via `onseek`.
	 */
	let {
		segments,
		currentTime = 0,
		onseek
	}: {
		segments: Segment[];
		currentTime?: number;
		onseek?: (time: number) => void;
	} = $props();

	interface Group {
		key: string;
		speaker: string | null;
		start: number;
		segments: Segment[];
	}

	// Group consecutive segments by speaker for a readable, chat-like layout.
	const groups: Group[] = $derived.by(() => {
		const out: Group[] = [];
		for (const seg of segments) {
			const last = out[out.length - 1];
			if (last && last.speaker === seg.speaker && seg.start - last.segments[last.segments.length - 1].end < 8) {
				last.segments.push(seg);
			} else {
				out.push({
					key: `${seg.start.toFixed(2)}-${seg.speaker ?? 'none'}`,
					speaker: seg.speaker,
					start: seg.start,
					segments: [seg]
				});
			}
		}
		return out;
	});

	const activeKey = $derived.by(() => {
		for (const g of groups) {
			const last = g.segments[g.segments.length - 1];
			if (currentTime >= g.start && currentTime <= last.end + 0.6) return g.key;
		}
		return null;
	});
</script>

<div class="transcript scroll-thin" role="log" aria-label="Transcript">
	{#each groups as group (group.key)}
		{@const color = speakerColor(group.speaker)}
		<div class="group" class:active={group.key === activeKey}>
			<button
				class="group-head"
				onclick={() => onseek?.(group.start)}
				aria-label={`Seek to ${formatClock(group.start)}`}
			>
				<span class="speaker-dot" style:background={color} aria-hidden="true"></span>
				<span class="speaker-name" style:color>{prettySpeaker(group.speaker)}</span>
				<span class="stamp muted">{formatClock(group.start)}</span>
			</button>
			<div class="lines">
				{#each group.segments as seg (`${seg.start.toFixed(2)}`)}
					<button class="line" onclick={() => onseek?.(seg.start)}>
						<span class="line-stamp">{formatClock(seg.start)}</span>
						<span class="line-text">{seg.text}</span>
					</button>
				{/each}
			</div>
		</div>
	{/each}
</div>

<style>
	.transcript {
		display: flex;
		flex-direction: column;
		gap: 1.1rem;
		max-height: 70vh;
		overflow-y: auto;
		padding-right: 0.4rem;
	}

	.group {
		border-radius: var(--radius-md);
		padding: 0.55rem 0.7rem;
		border: 1px solid transparent;
		transition:
			background-color 0.25s ease,
			border-color 0.25s ease;
	}

	.group.active {
		background: rgba(34, 197, 94, 0.07);
		border-color: rgba(34, 197, 94, 0.25);
	}

	.group-head {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		background: none;
		border: none;
		padding: 0.2rem 0;
		cursor: pointer;
		font-family: var(--font);
		text-align: left;
		min-height: 32px;
	}

	.speaker-dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		flex: none;
	}

	.speaker-name {
		font-weight: 700;
		font-size: 0.88rem;
	}

	.stamp {
		font-size: 0.78rem;
		font-variant-numeric: tabular-nums;
	}

	.lines {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		margin-top: 0.25rem;
	}

	.line {
		display: flex;
		gap: 0.7rem;
		align-items: baseline;
		background: none;
		border: none;
		padding: 0.28rem 0.2rem;
		border-radius: var(--radius-sm);
		cursor: pointer;
		font-family: var(--font);
		font-size: 0.95rem;
		color: var(--text);
		text-align: left;
		transition: background-color 0.15s ease;
	}

	.line:hover {
		background: rgba(148, 163, 184, 0.08);
	}

	.line-stamp {
		flex: none;
		font-size: 0.75rem;
		color: var(--muted-text);
		font-variant-numeric: tabular-nums;
		min-width: 3.4rem;
	}

	.line-text {
		line-height: 1.6;
	}
</style>
