<script lang="ts">
	import Icon from '../Icon.svelte';
	import { formatClock } from '../format';

	/**
	 * Custom audio player. The parent seeks via the bindable `seekTo` prop:
	 * set it to a time in seconds and the player jumps there.
	 */
	let {
		src,
		seekTo = $bindable<number | null>(null),
		ontimeupdate
	}: {
		src: string;
		seekTo?: number | null;
		ontimeupdate?: (time: number) => void;
	} = $props();

	let audio: HTMLAudioElement | undefined = $state();
	let playing = $state(false);
	let current = $state(0);
	let duration = $state(0);
	let rate = $state(1);
	let loadError = $state(false);

	const RATES = [1, 1.25, 1.5, 2];

	$effect(() => {
		const t = seekTo;
		if (t !== null && t !== undefined && audio && Number.isFinite(duration) && duration > 0) {
			audio.currentTime = Math.max(0, Math.min(duration, t));
			seekTo = null;
		}
	});

	function toggle() {
		if (!audio) return;
		if (playing) audio.pause();
		else void audio.play().catch(() => {});
	}

	function onSeekInput(e: Event) {
		const input = e.target as HTMLInputElement;
		if (audio && Number.isFinite(duration) && duration > 0) {
			audio.currentTime = (Number(input.value) / 1000) * duration;
		}
	}

	function cycleRate() {
		const i = RATES.indexOf(rate);
		rate = RATES[(i + 1) % RATES.length];
		if (audio) audio.playbackRate = rate;
	}

	const progress = $derived(duration > 0 ? (current / duration) * 1000 : 0);
</script>

<div class="player glass">
	{#if loadError}
		<p class="error"><Icon name="alert" size={16} /> Audio could not be loaded.</p>
	{:else}
		<audio
			bind:this={audio}
			{src}
			preload="metadata"
			ontimeupdate={() => {
				if (audio) {
					current = audio.currentTime;
					ontimeupdate?.(audio.currentTime);
				}
			}}
			onloadedmetadata={() => {
				if (audio) duration = audio.duration;
			}}
			ondurationchange={() => {
				if (audio && Number.isFinite(audio.duration)) duration = audio.duration;
			}}
			onplay={() => (playing = true)}
			onpause={() => (playing = false)}
			onended={() => (playing = false)}
			onerror={() => (loadError = true)}
		></audio>
		<button
			class="play-btn"
			onclick={toggle}
			aria-label={playing ? 'Pause' : 'Play'}
			disabled={loadError}
		>
			<Icon name={playing ? 'pause' : 'play'} size={22} filled={true} />
		</button>
		<span class="time" aria-hidden="true">{formatClock(current)}</span>
		<input
			class="seek"
			type="range"
			min={0}
			max={1000}
			step={1}
			value={Math.round(progress)}
			oninput={onSeekInput}
			aria-label="Seek"
		/>
		<span class="time" aria-hidden="true">{formatClock(duration)}</span>
		<button class="rate-btn" onclick={cycleRate} aria-label={`Playback speed ${rate}x`}>
			{rate}x
		</button>
	{/if}
</div>

<style>
	.player {
		display: flex;
		align-items: center;
		gap: 0.8rem;
		padding: 0.8rem 1rem;
		border-radius: var(--radius-lg);
	}

	.play-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 48px;
		height: 48px;
		flex: none;
		border-radius: 50%;
		border: none;
		background: var(--accent);
		color: #052e16;
		cursor: pointer;
		transition:
			background-color 0.18s ease,
			transform 0.12s ease;
	}

	.play-btn:hover:not(:disabled) {
		background: #4ade80;
	}

	.play-btn:active:not(:disabled) {
		transform: scale(0.96);
	}

	.time {
		font-variant-numeric: tabular-nums;
		font-size: 0.85rem;
		color: var(--muted-text);
		min-width: 3.2rem;
		text-align: center;
		flex: none;
	}

	.seek {
		flex: 1;
		appearance: none;
		-webkit-appearance: none;
		height: 6px;
		border-radius: 999px;
		background: var(--muted);
		cursor: pointer;
		min-width: 80px;
	}

	.seek::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 18px;
		height: 18px;
		border-radius: 50%;
		background: var(--accent);
		border: none;
		box-shadow: 0 2px 8px rgba(34, 197, 94, 0.5);
	}

	.seek::-moz-range-thumb {
		width: 18px;
		height: 18px;
		border-radius: 50%;
		background: var(--accent);
		border: none;
	}

	.seek:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 4px;
	}

	.rate-btn {
		flex: none;
		min-width: 52px;
		min-height: 36px;
		padding: 0.3rem 0.6rem;
		border-radius: var(--radius-sm);
		border: 1px solid rgba(148, 163, 184, 0.22);
		background: transparent;
		color: var(--muted-text);
		font-family: var(--font);
		font-size: 0.82rem;
		font-weight: 700;
		cursor: pointer;
		transition:
			color 0.18s ease,
			border-color 0.18s ease;
	}

	.rate-btn:hover {
		color: var(--text);
		border-color: rgba(148, 163, 184, 0.4);
	}

	.error {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--danger);
		font-size: 0.9rem;
	}
</style>
