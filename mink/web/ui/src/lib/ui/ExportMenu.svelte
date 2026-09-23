<script lang="ts">
	import Icon from '../Icon.svelte';
	import { exportUrl, type ExportFormat } from '../api';

	let { sessionId, title }: { sessionId: string; title: string } = $props();

	let open = $state(false);
	let wrap: HTMLDivElement | undefined = $state();

	const FORMATS: { format: ExportFormat; label: string }[] = [
		{ format: 'md', label: 'Markdown' },
		{ format: 'txt', label: 'Plain text' },
		{ format: 'srt', label: 'SRT captions' },
		{ format: 'vtt', label: 'WebVTT captions' }
	];

	function close() {
		open = false;
	}

	function handleWindowClick(e: MouseEvent) {
		if (open && wrap && !wrap.contains(e.target as Node)) close();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') close();
	}

	function filename(format: ExportFormat): string {
		const base = (title || sessionId).replace(/[^\w\- ]+/g, '').trim() || sessionId;
		return `${base}.${format}`;
	}
</script>

<svelte:window onclick={handleWindowClick} onkeydown={handleKeydown} />

<div class="export-wrap" bind:this={wrap}>
	<button
		class="btn btn-secondary btn-sm"
		onclick={() => (open = !open)}
		aria-haspopup="menu"
		aria-expanded={open}
	>
		<Icon name="download" size={16} /> Export <Icon name="chevronDown" size={15} />
	</button>
	{#if open}
		<div class="menu glass" role="menu" aria-label="Export formats">
			{#each FORMATS as { format, label } (format)}
				<a
					class="menu-item"
					role="menuitem"
					href={exportUrl(sessionId, format)}
					download={filename(format)}
					onclick={close}
				>
					<Icon name="download" size={15} /> {label}
					<span class="ext muted">.{format}</span>
				</a>
			{/each}
		</div>
	{/if}
</div>

<style>
	.export-wrap {
		position: relative;
	}

	.menu {
		position: absolute;
		right: 0;
		top: calc(100% + 8px);
		z-index: 30;
		min-width: 220px;
		border-radius: var(--radius-md);
		padding: 0.4rem;
		display: flex;
		flex-direction: column;
		animation: pop 0.16s ease;
	}

	.menu-item {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.65rem 0.8rem;
		border-radius: var(--radius-sm);
		text-decoration: none;
		color: var(--text);
		font-size: 0.9rem;
		font-weight: 500;
		min-height: 44px;
		transition: background-color 0.15s ease;
	}

	.menu-item:hover {
		background: rgba(148, 163, 184, 0.12);
	}

	.ext {
		margin-left: auto;
		font-size: 0.78rem;
	}

	@keyframes pop {
		from {
			opacity: 0;
			transform: translateY(-4px);
		}
	}
</style>
