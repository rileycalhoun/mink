<script lang="ts">
	import '../app.css';
	import { resolve } from '$app/paths';
	import type { Snippet } from 'svelte';
	import Icon from '$lib/Icon.svelte';
	import { getHealth } from '$lib/api';

	let { children }: { children: Snippet } = $props();

	let engineOk = $state<boolean | null>(null);

	$effect(() => {
		getHealth()
			.then((h) => (engineOk = h.engine_reachable))
			.catch(() => (engineOk = false));
	});
</script>

<header class="nav glass">
	<div class="nav-inner">
		<a class="brand" href={resolve('/')} aria-label="Mink home">
			<span class="brand-icon"><Icon name="cap" size={22} /></span>
			<span class="brand-name">Mink</span>
		</a>
		<nav class="links" aria-label="Primary">
			<a class="nav-link" href={resolve('/')}>Library</a>
			<a class="nav-link nav-link-live" href={resolve('/live')}>
				<span class="pulse-dot live" aria-hidden="true"></span> Live record
			</a>
		</nav>
		<div
			class="engine-pill"
			title={engineOk === null
				? 'Checking transcription engine…'
				: engineOk
					? 'Transcription engine is ready'
					: 'Transcription engine is offline'}
		>
			<span
				class="pulse-dot"
				class:live={engineOk === true}
				style:background={engineOk === true
					? 'var(--accent)'
					: engineOk === false
						? 'var(--warning)'
						: 'var(--border)'}
				aria-hidden="true"
			></span>
			<span class="engine-label">
				{engineOk === null ? 'Checking…' : engineOk ? 'Engine ready' : 'Engine offline'}
			</span>
		</div>
	</div>
</header>

<main class="main">
	{@render children()}
</main>

<footer class="footer muted">
	<p>
		Mink · open-source lecture transcription ·
		<a href="https://github.com/rileycalhoun/mink" target="_blank" rel="noreferrer">GitHub</a>
	</p>
</footer>

<style>
	.nav {
		position: sticky;
		top: 0;
		z-index: 40;
		border-left: none;
		border-right: none;
		border-top: none;
	}

	.nav-inner {
		max-width: 1200px;
		margin: 0 auto;
		padding: 0.8rem 1.25rem;
		display: flex;
		align-items: center;
		gap: 1.5rem;
	}

	.brand {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		text-decoration: none;
		font-weight: 800;
		font-size: 1.25rem;
		letter-spacing: -0.02em;
	}

	.brand-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 38px;
		height: 38px;
		border-radius: 10px;
		background: var(--accent-dim);
		border: 1px solid rgba(34, 197, 94, 0.35);
		color: var(--accent);
	}

	.links {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		margin-right: auto;
	}

	.nav-link {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.55rem 0.9rem;
		min-height: 44px;
		border-radius: var(--radius-md);
		text-decoration: none;
		font-weight: 600;
		font-size: 0.93rem;
		color: var(--muted-text);
		transition:
			color 0.18s ease,
			background-color 0.18s ease;
	}

	.nav-link:hover {
		color: var(--text);
		background: rgba(148, 163, 184, 0.1);
	}

	.nav-link-live {
		color: #86efac;
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

	.main {
		max-width: 1200px;
		margin: 0 auto;
		padding: 2rem 1.25rem 4rem;
		min-height: calc(100vh - 180px);
	}

	.footer {
		text-align: center;
		padding: 1.5rem;
		font-size: 0.85rem;
	}

	.footer a {
		color: var(--muted-text);
	}

	@media (max-width: 640px) {
		.engine-label {
			display: none;
		}

		.nav-inner {
			gap: 0.9rem;
		}
	}
</style>
