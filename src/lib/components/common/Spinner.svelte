<script lang="ts">
  interface Props {
    size?: 'sm' | 'md' | 'lg';
    color?: 'accent' | 'white' | 'warning';
  }

  let { size = 'md', color = 'accent' }: Props = $props();

  const sizes = {
    sm: 14,
    md: 24,
    lg: 32
  };

  const colors = {
    accent: 'var(--accent)',
    white: 'white',
    warning: 'var(--warning)'
  };
</script>

<div
  class="spinner"
  style:width="{sizes[size]}px"
  style:height="{sizes[size]}px"
  style:border-top-color={colors[color]}
  role="status"
  aria-label="Loading"
></div>

<style>
  .spinner {
    border: 2px solid transparent;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
