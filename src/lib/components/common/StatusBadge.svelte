<script lang="ts">
  import type { EpisodeStatus } from '$lib/types';

  interface Props {
    status: EpisodeStatus;
  }

  let { status }: Props = $props();

  const statusConfig: Record<EpisodeStatus, { label: string; class: string }> = {
    none: { label: '', class: '' },
    queued: { label: 'Queued', class: 'status-badge--queued' },
    processing: { label: 'Processing', class: 'status-badge--processing' },
    ready: { label: 'Ad-Free', class: 'status-badge--ready' },
    error: { label: 'Error', class: 'status-badge--error' }
  };

  const config = $derived(statusConfig[status]);
</script>

{#if status !== 'none' && config.label}
  <span class="status-badge {config.class}">
    {#if status === 'processing'}
      <span class="status-badge__spinner"></span>
    {/if}
    {config.label}
  </span>
{/if}

<style>
  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--text-xs);
    font-weight: var(--font-medium);
    padding: 2px var(--space-2);
    border-radius: var(--radius-sm);
    text-transform: uppercase;
    letter-spacing: 0.02em;
  }

  .status-badge--queued {
    background: var(--bg-elevated);
    color: var(--text-secondary);
  }

  .status-badge--processing {
    background: rgba(255, 159, 10, 0.15);
    color: var(--warning);
  }

  .status-badge--ready {
    background: rgba(48, 209, 88, 0.15);
    color: var(--success);
  }

  .status-badge--error {
    background: rgba(255, 69, 58, 0.15);
    color: var(--error);
  }

  .status-badge__spinner {
    width: 10px;
    height: 10px;
    border: 1.5px solid transparent;
    border-top-color: currentColor;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
