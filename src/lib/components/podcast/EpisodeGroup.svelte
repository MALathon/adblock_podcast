<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { EpisodeStatus } from '$lib/types';
  import Spinner from '$lib/components/common/Spinner.svelte';

  interface Props {
    title: string;
    count: number;
    status?: EpisodeStatus;
    children: Snippet;
    headerActions?: Snippet;
  }

  let { title, count, status, children, headerActions }: Props = $props();

  const statusConfig: Record<string, { icon: string; colorClass: string }> = {
    ready: { icon: '✓', colorClass: 'episode-group__title--ready' },
    processing: { icon: '', colorClass: 'episode-group__title--processing' },
    queued: { icon: '⏳', colorClass: 'episode-group__title--queued' },
    error: { icon: '✗', colorClass: 'episode-group__title--error' }
  };

  const config = $derived(status ? statusConfig[status] : null);
</script>

<div class="episode-group">
  <div class="episode-group__header">
    <h3 class="episode-group__title {config?.colorClass ?? ''}">
      {#if status === 'processing'}
        <Spinner size="sm" color="warning" />
      {:else if config?.icon}
        <span class="episode-group__icon">{config.icon}</span>
      {/if}
      {title} ({count})
    </h3>
    {#if headerActions}
      {@render headerActions()}
    {/if}
  </div>
  <div class="episode-list">
    {@render children()}
  </div>
</div>

<style>
  .episode-group {
    margin-bottom: var(--space-6);
  }

  .episode-group__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
    padding: var(--space-2) 0;
    border-bottom: 1px solid var(--border);
  }

  .episode-group__title {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    font-weight: var(--font-semibold);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    margin: 0;
  }

  .episode-group__title--ready {
    color: var(--success);
  }

  .episode-group__title--processing {
    color: var(--warning);
  }

  .episode-group__title--queued {
    color: var(--text-muted);
  }

  .episode-group__title--error {
    color: var(--error);
  }

  .episode-group__icon {
    font-size: var(--text-base);
  }

  .episode-list {
    display: flex;
    flex-direction: column;
  }
</style>
