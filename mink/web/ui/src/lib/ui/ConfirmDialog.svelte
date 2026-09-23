<script lang="ts">
	import Modal from './Modal.svelte';

	/**
	 * Destructive-action confirmation. The confirm button is the only path
	 * to the action; Escape, backdrop click, and Cancel all abort.
	 */
	let {
		open = $bindable(false),
		title,
		message,
		confirmLabel = 'Delete',
		busy = false,
		error = null,
		onconfirm
	}: {
		open: boolean;
		title: string;
		message: string;
		confirmLabel?: string;
		busy?: boolean;
		error?: string | null;
		onconfirm: () => void | Promise<void>;
	} = $props();
</script>

<Modal bind:open {title}>
	<p class="message">{message}</p>
	{#if error}
		<p class="error" role="alert">{error}</p>
	{/if}
	<div class="actions">
		<button class="btn btn-secondary" onclick={() => (open = false)} disabled={busy}>
			Cancel
		</button>
		<button class="btn btn-danger" onclick={onconfirm} disabled={busy}>
			{busy ? 'Deleting…' : confirmLabel}
		</button>
	</div>
</Modal>

<style>
	.message {
		color: var(--muted-text);
		line-height: 1.6;
		margin-bottom: 1.5rem;
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
	}

	.error {
		color: #f87171;
		font-size: 0.88rem;
		margin: -0.75rem 0 1rem;
	}
</style>
