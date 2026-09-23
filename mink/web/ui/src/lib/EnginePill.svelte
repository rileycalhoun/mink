<script lang="ts">
	/**
	 * Engine status pill. When the on-demand cloud engine is configured
	 * (RunPod), the pill becomes a start/stop control: spin the GPU pod up
	 * before class, and it shuts itself down after idling. Without cloud
	 * configuration it is a static health indicator as before.
	 */
	import { getEngineStatus, getHealth, startEngine, stopEngine } from '$lib/api';
	import type { EngineStatus } from '$lib/types';

	let status = $state<EngineStatus | null>(null);
	let staticOk = $state<boolean | null>(null);
	let busy = $state(false);

	async function refresh() {
		try {
			status = await getEngineStatus();
		} catch {
			status = null;
		}
		if (status && !status.configured) {
			try {
				staticOk = (await getHealth()).engine_reachable;
			} catch {
				staticOk = false;
			}
		}
	}

	async function onStart() {
		busy = true;
		try {
			status = await startEngine();
		} catch {
			/* error state surfaces on next poll */
		} finally {
			busy = false;
			await refresh();
		}
	}

	async function onStop() {
		busy = true;
		try {
			status = await stopEngine();
		} finally {
			busy = false;
		}
	}

	$effect(() => {
		refresh();
		const t = setInterval(refresh, 10_000);
		return () => clearInterval(t);
	});

	const dotColor = $derived(
		!status || !status.configured
			? staticOk === true
				? 'var(--accent)'
				: staticOk === false
					? 'var(--warning)'
					: 'var(--border)'
			: status.state === 'ready'
				? 'var(--accent)'
				: status.state === 'provisioning'
					? 'var(--warning)'
					: status.state === 'error'
						? '#f87171'
						: 'var(--border)'
	);

	const label = $derived(
		!status
			? 'Checking…'
			: !status.configured
				? staticOk === null
					? 'Checking…'
					: staticOk
						? 'Engine ready'
						: 'Engine offline'
				: status.state === 'ready'
					? `Engine ready${status.price_per_hr != null ? ` · $${status.price_per_hr.toFixed(2)}/hr` : ''}`
					: status.state === 'provisioning'
						? 'Warming up…'
						: status.state === 'error'
							? 'Engine failed — retry?'
							: 'Start engine'
	);

	const tooltip = $derived(
		!status || !status.configured
			? 'Transcription engine status'
			: status.state === 'ready'
				? `GPU pod ${status.gpu ?? ''} — click × to stop it now (auto-stops after ${Math.round(status.idle_timeout_s / 60)} min idle)`
				: status.state === 'provisioning'
					? 'Provisioning the GPU pod — usually ready in 2–3 minutes'
					: status.state === 'error'
						? (status.error ?? 'Provisioning failed') + ' — click to retry'
						: 'Spin up the cheapest available GPU for transcription'
	);
</script>

<div class="engine-pill" title={tooltip}>
	<span
		class="pulse-dot"
		class:live={dotColor === 'var(--accent)'}
		class:spin={status?.configured && status.state === 'provisioning'}
		style:background={dotColor}
		aria-hidden="true"
	></span>
	{#if status?.configured && (status.state === 'off' || status.state === 'error')}
		<button class="engine-action" onclick={onStart} disabled={busy}>
			<span class="engine-label">{label}</span>
		</button>
	{:else}
		<span class="engine-label">{label}</span>
	{/if}
	{#if status?.configured && status.state === 'ready'}
		<button
			class="engine-stop"
			onclick={onStop}
			disabled={busy}
			aria-label="Stop the engine pod now"
			title="Stop the engine pod now"
		>
			×
		</button>
	{/if}
</div>

<style>
	.engine-pill {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.4rem 0.8rem;
		border-radius: 999px;
		border: 1px solid rgba(148, 163, 184, 0.18);
		background: rgba(148, 163, 184, 0.07);
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--muted-text);
		white-space: nowrap;
	}

	.engine-action {
		all: unset;
		cursor: pointer;
		font: inherit;
		color: var(--text);
		text-decoration: underline dotted;
		text-underline-offset: 3px;
	}

	.engine-action:disabled {
		cursor: wait;
		opacity: 0.6;
	}

	.engine-stop {
		all: unset;
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.4rem;
		height: 1.4rem;
		border-radius: 999px;
		font-size: 1rem;
		line-height: 1;
		color: var(--muted-text);
		border: 1px solid rgba(148, 163, 184, 0.25);
	}

	.engine-stop:hover {
		color: #f87171;
		border-color: #f87171;
	}

	.spin {
		animation: spin 1.2s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	@media (max-width: 640px) {
		.engine-label {
			display: none;
		}

		/* Keep the label visible when it's the thing you tap. */
		.engine-action .engine-label {
			display: inline;
		}
	}
</style>
