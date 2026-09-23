<script lang="ts">
	import '../app.css';
	import { resolve } from '$app/paths';
	import type { Snippet } from 'svelte';
	import Icon from '$lib/Icon.svelte';
	import EnginePill from '$lib/EnginePill.svelte';

	let { children }: { children: Snippet } = $props();
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
		<EnginePill />
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
		.nav-inner {
			gap: 0.9rem;
		}
	}
</style>
