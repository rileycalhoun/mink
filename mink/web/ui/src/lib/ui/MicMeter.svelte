<script lang="ts">
	/** Horizontal mic level meter driven by an AnalyserNode (0..1). */
	let { level = 0, label = 'Microphone level' }: { level?: number; label?: string } = $props();

	const pct = $derived(Math.max(0, Math.min(1, level)) * 100);
</script>

<div class="meter" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}>
	<div class="meter-track">
		<div class="meter-fill" style:width={`${pct}%`}></div>
	</div>
</div>

<style>
	.meter {
		width: 100%;
	}

	.meter-track {
		height: 8px;
		border-radius: 999px;
		background: var(--muted);
		overflow: hidden;
	}

	.meter-fill {
		height: 100%;
		border-radius: 999px;
		background: var(--accent);
		transition: width 0.08s linear;
	}
</style>
