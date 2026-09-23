<script lang="ts">
	import type { Snippet } from 'svelte';
	import Icon from '../Icon.svelte';

	let {
		open = $bindable(false),
		title,
		children,
		onclose
	}: { open: boolean; title: string; children: Snippet; onclose?: () => void } = $props();

	function close() {
		open = false;
		onclose?.();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') close();
	}
</script>

<svelte:window onkeydown={open ? handleKeydown : undefined} />

{#if open}
	<div
		class="backdrop"
		onclick={(e) => {
			if (e.target === e.currentTarget) close();
		}}
		role="presentation"
	>
		<div class="modal card" role="dialog" aria-modal="true" aria-label={title}>
			<div class="modal-head">
				<h2>{title}</h2>
				<button class="icon-btn" onclick={close} aria-label="Close dialog">
					<Icon name="x" size={18} />
				</button>
			</div>
			<div class="modal-body">
				{@render children()}
			</div>
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 50;
		display: flex;
		align-items: flex-start;
		justify-content: center;
		padding: 4rem 1rem 1rem;
		background: rgba(2, 6, 23, 0.7);
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		animation: fade-in 0.18s ease;
	}

	.modal {
		width: min(560px, 100%);
		max-height: calc(100vh - 8rem);
		overflow-y: auto;
		animation: rise 0.22s ease;
	}

	.modal-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 1.25rem 1.5rem;
		border-bottom: 1px solid rgba(148, 163, 184, 0.12);
		position: sticky;
		top: 0;
		background: inherit;
	}

	.modal-head h2 {
		font-size: 1.15rem;
		font-weight: 700;
	}

	.modal-body {
		padding: 1.5rem;
	}

	@keyframes fade-in {
		from {
			opacity: 0;
		}
	}

	@keyframes rise {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
	}
</style>
