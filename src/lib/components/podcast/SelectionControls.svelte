<script lang="ts">
  interface Props {
    seasons: string[];
    selectedSeason: string;
    selectedCount: number;
    allSelected: boolean;
    isQueueing: boolean;
    onSeasonChange: (season: string) => void;
    onSelectAll: () => void;
    onDeselectAll: () => void;
    onQueueSelected: () => void;
  }

  let {
    seasons,
    selectedSeason,
    selectedCount,
    allSelected,
    isQueueing,
    onSeasonChange,
    onSelectAll,
    onDeselectAll,
    onQueueSelected
  }: Props = $props();
</script>

<div class="selection-controls">
  {#if seasons.length > 0}
    <select
      class="season-select"
      value={selectedSeason}
      onchange={(e) => onSeasonChange(e.currentTarget.value)}
    >
      <option value="">All Seasons</option>
      {#each seasons as season}
        <option value={season}>Season {season}</option>
      {/each}
    </select>
  {/if}

  <button class="select-btn" onclick={allSelected ? onDeselectAll : onSelectAll}>
    {allSelected ? 'Deselect All' : 'Select All'}
  </button>

  {#if selectedCount > 0}
    <button class="queue-btn" onclick={onQueueSelected} disabled={isQueueing}>
      {isQueueing ? 'Queueing...' : `Queue ${selectedCount} Episode${selectedCount > 1 ? 's' : ''}`}
    </button>
  {/if}
</div>

<style>
  .selection-controls {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .season-select {
    padding: var(--space-1) var(--space-2);
    background: var(--bg-secondary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    font-size: var(--text-xs);
    cursor: pointer;
  }

  .select-btn {
    padding: var(--space-1) var(--space-3);
    background: var(--bg-secondary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    font-size: var(--text-xs);
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .select-btn:hover {
    background: var(--bg-elevated);
  }

  .queue-btn {
    padding: var(--space-1) var(--space-3);
    background: var(--accent);
    color: white;
    border: none;
    border-radius: var(--radius-md);
    font-size: var(--text-xs);
    font-weight: var(--font-medium);
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .queue-btn:hover:not(:disabled) {
    opacity: 0.9;
  }

  .queue-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
