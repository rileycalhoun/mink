<script lang="ts">
	/**
	 * Engine status pill. When the on-demand cloud engine is configured
	 * (RunPod), the pill becomes a start/stop control: spin the GPU pod up
	 * before class, and it shuts itself down after idling. Without cloud
	 * configuration it is a static health indicator as before.
	 */
	import { getEngineStatus, getEngineLogs, getHealth, startEngine, stopEngine } from '$lib/api';
	import type { EngineLog, EngineStatus } from '$lib/types';

	let status = $state<EngineStatus | null>(null);
	let staticOk = $state<boolean | null>(null);
	let busy = $state(false);
	let bootLog = $state<EngineLog | null>(null);
	let showLog = $state(false);

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
		if (showLog && status?.configured && (status.state === 'provisioning' || status.state === 'error')) {
			try {
				bootLog = await getEngineLogs();
			} catch {
				/* keep the last log we had */
			}
		}
	}

	function toggleLog() {
		showLog = !showLog;
		if (showLog) refresh();
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
					? 'Provisioning the GPU pod — usually ready in 2–3 minutes. Toggle the log icon to watch it boot.'
					: status.state === 'error'
						? (status.error ?? 'Provisioning failed') + ' — click to retry'
						: 'Spin up the cheapest available GPU for transcription'
	);

	const showLogToggle = $derived(
		status?.configured === true && (status.state === 'provisioning' || status.state === 'error')
	);

	$effect(() => {
		if (!showLogToggle) showLog = false;
	});
</script>

<div class="engine-wrap">
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
	{#if showLogToggle}
		<button
			class="engine-log-toggle"
			class:open={showLog}
			onclick={toggleLog}
			aria-label={showLog ? 'Hide pod boot log' : 'Show pod boot log'}
			title={showLog ? 'Hide pod boot log' : 'Show pod boot log'}
		>
			<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 4h10M3 8h10M3 12h6"/></svg>
		</button>
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
{#if showLog && showLogToggle}
	<div class="boot-log-panel" role="log" aria-label="Pod boot log">
		<div class="boot-log-head">
			<span>Pod boot log{bootLog?.pod_id ? ` · ${bootLog.pod_id.slice(0, 8)}…` : ''}</span>
			<button class="boot-log-close" onclick={toggleLog} aria-label="Close boot log">×</button>
		</div>
		<pre class="boot-log-body scroll-thin">{bootLog?.log?.trim() || 'Waiting for the pod to emit logs…'}</pre>
	</div>
{/if}
</div>

<style>
	.engine-wrap {
		position: relative;
	}

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

	.engine-log-toggle {
		all: unset;
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.4rem;
		height: 1.4rem;
		border-radius: 999px;
		color: var(--muted-text);
		border: 1px solid rgba(148, 163, 184, 0.25);
	}

	.engine-log-toggle:hover,
	.engine-log-toggle.open {
		color: var(--text);
		border-color: var(--text);
	}

	.boot-log-panel {
		position: absolute;
		top: calc(100% + 0.5rem);
		right: 0;
		width: min(26rem, 80vw);
		max-height: 22rem;
		display: flex;
		flex-direction: column;
		background: var(--card-bg, #0f172a);
		border: 1px solid rgba(148, 163, 184, 0.25);
		border-radius: var(--radius-md);
		box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
		z-index: 50;
		overflow: hidden;
	}

	.boot-log-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 0.75rem;
		font-size: 0.75rem;
		font-weight: 700;
		color: var(--muted-text);
		border-bottom: 1px solid rgba(148, 163, 184, 0.15);
	}

	.boot-log-close {
		all: unset;
		cursor: pointer;
		font-size: 1.1rem;
		line-height: 1;
		color: var(--muted-text);
		padding: 0.1rem 0.3rem;
	}

	.boot-log-close:hover {
		color: var(--text);
	}

	.boot-log-body {
		margin: 0;
		padding: 0.75rem;
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.72rem;
		line-height: 1.5;
		color: var(--text);
		white-space: pre-wrap;
		word-break: break-word;
		overflow-y: auto;
		max-height: 18rem;
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
