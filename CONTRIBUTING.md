# Contributing to AdBlock Podcast

This guide helps developers understand the codebase and add new features.

## Table of Contents

1. [Development Setup](#development-setup)
2. [Architecture Overview](#architecture-overview)
3. [Code Patterns](#code-patterns)
4. [Adding Features](#adding-features)
5. [Testing](#testing)
6. [Code Quality](#code-quality)

---

## Development Setup

### Prerequisites

```bash
# Required
node --version    # v20+
npm --version     # v10+

# For backend (optional for frontend-only work)
python --version  # 3.10+
ffmpeg -version   # Any recent version
```

### First Time Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# In another terminal, run tests in watch mode
npm run test:watch
```

### IDE Setup

**VS Code Extensions:**
- Svelte for VS Code
- ESLint
- Prettier

**Settings:**
```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "[svelte]": {
    "editor.defaultFormatter": "svelte.svelte-vscode"
  }
}
```

---

## Architecture Overview

### Data Flow

```
User Action → Svelte Component → API Route → Database → Response
     ↑                                                      │
     └──────────────────────────────────────────────────────┘
```

### Key Directories

| Directory | Purpose | When to Modify |
|-----------|---------|----------------|
| `src/routes/` | Pages and API endpoints | Adding new pages or endpoints |
| `src/lib/components/` | Reusable UI components | Building UI |
| `src/lib/stores/` | Global state (Svelte 5 runes) | Managing app state |
| `src/lib/db/` | Database operations | Modifying data schema |
| `src/lib/services/` | Business logic | Complex operations |
| `src/lib/utils/` | Pure utility functions | Helper functions |

### Important Files

| File | Purpose |
|------|---------|
| `src/lib/types.ts` | All TypeScript interfaces |
| `src/lib/utils/config.ts` | App configuration constants |
| `src/lib/services/api.ts` | API response helpers |
| `src/lib/db/index.ts` | Database schema and connection |

---

## Code Patterns

### Svelte 5 Runes

We use Svelte 5 with runes. Key patterns:

```svelte
<script lang="ts">
  // Props (replaces export let)
  let { podcast, onSelect } = $props<{
    podcast: Podcast;
    onSelect: (id: string) => void;
  }>();

  // Reactive state (replaces let x = value)
  let count = $state(0);

  // Derived values (replaces $: x = ...)
  let doubled = $derived(count * 2);

  // Effects (replaces $: { ... })
  $effect(() => {
    console.log('count changed:', count);
  });
</script>
```

### API Routes

All API routes follow this pattern:

```typescript
// src/routes/api/example/+server.ts
import type { RequestHandler } from './$types';
import { success, badRequest, serverError } from '$lib/services/api';

export const GET: RequestHandler = async ({ url }) => {
  try {
    // 1. Validate input
    const query = url.searchParams.get('q');
    if (!query) {
      return badRequest('Query parameter required');
    }

    // 2. Perform operation
    const results = await doSomething(query);

    // 3. Return success
    return success(results);
  } catch (error) {
    console.error('Operation failed:', error);
    return serverError('Operation failed');
  }
};
```

### Database Operations

Database functions go in `src/lib/db/`:

```typescript
// src/lib/db/example.ts
import { db } from './index';

export function getItems(): Item[] {
  const stmt = db.prepare(`
    SELECT id, name, created_at as createdAt
    FROM items
    ORDER BY created_at DESC
  `);
  return stmt.all() as Item[];
}

export function createItem(name: string): Item {
  const stmt = db.prepare(`
    INSERT INTO items (name, created_at) VALUES (?, ?)
  `);
  const now = new Date().toISOString();
  const result = stmt.run(name, now);
  return { id: result.lastInsertRowid, name, createdAt: now };
}
```

### Input Validation

Always validate external input:

```typescript
import { validateString, validateUrl, validateInteger } from '$lib/utils/validation';

// In API route
const title = validateString(body.title, 'title', { required: true });
const feedUrl = validateUrl(body.feedUrl, 'feedUrl', { required: true });
const limit = validateInteger(body.limit, 'limit', { min: 1, max: 100 });
```

### Component Structure

Components follow this structure:

```svelte
<script lang="ts">
  // 1. Imports
  import { formatTime } from '$lib/utils/format';
  import Icon from '$lib/components/common/Icon.svelte';

  // 2. Props
  let { episode, onPlay } = $props<{
    episode: Episode;
    onPlay: () => void;
  }>();

  // 3. State
  let isHovered = $state(false);

  // 4. Derived values
  let formattedDuration = $derived(formatTime(episode.duration));

  // 5. Functions
  function handleClick() {
    onPlay();
  }
</script>

<!-- Template -->
<div class="episode" class:hovered={isHovered}>
  <span>{episode.title}</span>
  <span>{formattedDuration}</span>
  <button onclick={handleClick}>
    <Icon name="play" />
  </button>
</div>

<!-- Scoped styles -->
<style>
  .episode {
    display: flex;
    padding: var(--space-3);
  }
  .episode.hovered {
    background: var(--bg-secondary);
  }
</style>
```

---

## Adding Features

### Adding a New Page

1. Create the route file:

```bash
# Create route directory
mkdir -p src/routes/my-feature
```

2. Create the page component:

```svelte
<!-- src/routes/my-feature/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';

  let data = $state<MyData[]>([]);
  let loading = $state(true);

  onMount(async () => {
    const response = await fetch('/api/my-feature');
    if (response.ok) {
      data = await response.json();
    }
    loading = false;
  });
</script>

<h1>My Feature</h1>

{#if loading}
  <p>Loading...</p>
{:else}
  {#each data as item}
    <div>{item.name}</div>
  {/each}
{/if}
```

### Adding a New API Endpoint

1. Create the route:

```typescript
// src/routes/api/my-feature/+server.ts
import type { RequestHandler } from './$types';
import { success, badRequest, serverError } from '$lib/services/api';
import { validateString } from '$lib/utils/validation';

export const GET: RequestHandler = async ({ url }) => {
  const query = url.searchParams.get('q');
  // ... implementation
  return success(results);
};

export const POST: RequestHandler = async ({ request }) => {
  try {
    const body = await request.json();
    const name = validateString(body.name, 'name', { required: true });
    // ... implementation
    return success(created);
  } catch (error) {
    if (error instanceof ValidationError) {
      return badRequest(error.message);
    }
    return serverError('Failed to create');
  }
};
```

### Adding a New Component

1. Create in appropriate directory:

```svelte
<!-- src/lib/components/common/MyComponent.svelte -->
<script lang="ts">
  let { label, onClick } = $props<{
    label: string;
    onClick?: () => void;
  }>();
</script>

<button class="my-component" onclick={onClick}>
  {label}
</button>

<style>
  .my-component {
    padding: var(--space-2) var(--space-4);
    background: var(--accent);
    color: white;
    border: none;
    border-radius: var(--radius-md);
    cursor: pointer;
  }
</style>
```

2. Use it:

```svelte
<script>
  import MyComponent from '$lib/components/common/MyComponent.svelte';
</script>

<MyComponent label="Click me" onClick={() => console.log('clicked')} />
```

### Adding Database Tables

1. Add to schema in `src/lib/db/index.ts`:

```typescript
db.exec(`
  -- Existing tables...

  CREATE TABLE IF NOT EXISTS my_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
  );

  CREATE INDEX IF NOT EXISTS idx_my_table_name ON my_table(name);
`);
```

2. Create CRUD file:

```typescript
// src/lib/db/myTable.ts
import { db } from './index';

export interface MyItem {
  id: number;
  name: string;
  createdAt: string;
}

export function getAllItems(): MyItem[] {
  return db.prepare('SELECT * FROM my_table').all() as MyItem[];
}

export function createItem(name: string): MyItem {
  const stmt = db.prepare('INSERT INTO my_table (name, created_at) VALUES (?, ?)');
  const now = new Date().toISOString();
  const result = stmt.run(name, now);
  return { id: Number(result.lastInsertRowid), name, createdAt: now };
}
```

3. Add types to `src/lib/types.ts`:

```typescript
export interface MyItem {
  id: number;
  name: string;
  createdAt: string;
}
```

### Adding a Store

```typescript
// src/lib/stores/myStore.svelte.ts

interface MyState {
  items: string[];
  selectedIndex: number;
}

function createMyStore() {
  let state = $state<MyState>({
    items: [],
    selectedIndex: -1
  });

  return {
    // Getters
    get items() { return state.items; },
    get selectedIndex() { return state.selectedIndex; },
    get selectedItem() {
      return state.selectedIndex >= 0 ? state.items[state.selectedIndex] : null;
    },

    // Actions
    addItem(item: string) {
      state.items = [...state.items, item];
    },

    selectIndex(index: number) {
      state.selectedIndex = index;
    },

    clear() {
      state.items = [];
      state.selectedIndex = -1;
    }
  };
}

export const myStore = createMyStore();
```

---

## Testing

### Unit Tests

Tests mirror the source structure:

```
src/lib/utils/format.ts     → tests/lib/utils/format.test.ts
src/lib/services/rss.ts     → tests/lib/services/rss.test.ts
```

Example test:

```typescript
// tests/lib/utils/myUtil.test.ts
import { describe, it, expect } from 'vitest';
import { myFunction } from '$lib/utils/myUtil';

describe('myFunction', () => {
  it('returns expected value for valid input', () => {
    expect(myFunction('input')).toBe('expected');
  });

  it('throws for invalid input', () => {
    expect(() => myFunction('')).toThrow('Invalid input');
  });

  it('handles edge cases', () => {
    expect(myFunction(null)).toBeNull();
  });
});
```

### E2E Tests

Test user flows:

```typescript
// e2e/my-feature.spec.ts
import { test, expect } from '@playwright/test';

test.describe('My Feature', () => {
  test('should display page', async ({ page }) => {
    await page.goto('/my-feature');
    await expect(page.getByRole('heading', { name: /my feature/i })).toBeVisible();
  });

  test('should handle user interaction', async ({ page }) => {
    await page.goto('/my-feature');
    await page.getByRole('button', { name: /submit/i }).click();
    await expect(page.getByText(/success/i)).toBeVisible();
  });
});
```

### Running Tests

```bash
# Unit tests
npm run test              # Run once
npm run test:watch        # Watch mode
npm run test -- myUtil    # Filter by name

# E2E tests
npm run test:e2e          # Run all
npm run test:e2e:ui       # Interactive mode
```

---

## Code Quality

### Before Committing

Run all checks:

```bash
npm run check      # TypeScript
npm run lint       # ESLint
npm run test       # Unit tests
npm run build      # Production build
```

### Code Style

- **TypeScript**: Strict mode, no `any`
- **Formatting**: Prettier (auto-format on save)
- **Naming**: camelCase for variables/functions, PascalCase for components/types
- **Imports**: Use `$lib/` alias for imports from `src/lib/`

### Common Gotchas

1. **Svelte 5 runes are not reactive by default in loops**
   ```svelte
   <!-- Wrong -->
   {#each items as item}
     <button onclick={() => count++}>{count}</button>
   {/each}

   <!-- Right: use function binding -->
   {#each items as item, i}
     <button onclick={() => handleClick(i)}>{counts[i]}</button>
   {/each}
   ```

2. **Database operations are synchronous**
   ```typescript
   // These are sync, not async
   const items = getAllItems(); // Not: await getAllItems()
   ```

3. **Always validate external input**
   ```typescript
   // In API routes, always validate
   const id = validateString(params.id, 'id', { required: true });
   ```

4. **Use CSS variables for theming**
   ```css
   /* Use theme variables */
   color: var(--text-primary);
   background: var(--bg-secondary);
   padding: var(--space-4);
   ```

### Design System

Available CSS variables (from global styles):

```css
/* Colors */
--bg-primary: #0a0a0a;
--bg-secondary: #141414;
--bg-elevated: #1c1c1c;
--text-primary: #f5f5f5;
--text-secondary: #a0a0a0;
--text-muted: #666666;
--accent: #0a84ff;
--success: #30d158;
--warning: #ff9f0a;
--error: #ff453a;

/* Spacing */
--space-1: 0.25rem;
--space-2: 0.5rem;
--space-3: 0.75rem;
--space-4: 1rem;
/* ... up to --space-12 */

/* Border radius */
--radius-sm: 4px;
--radius-md: 8px;
--radius-lg: 12px;
--radius-full: 9999px;

/* Font sizes */
--text-xs: 0.75rem;
--text-sm: 0.875rem;
--text-base: 1rem;
--text-lg: 1.125rem;
--text-xl: 1.25rem;
--text-2xl: 1.5rem;
```

### Icons

Use the Icon component:

```svelte
<script>
  import Icon from '$lib/components/common/Icon.svelte';
</script>

<Icon name="play" size={24} />
<Icon name="check" size={16} />
```

Available icons: `play`, `pause`, `skip-forward`, `skip-back`, `check`, `plus`, `search`, `arrow-left`, `chevron-down`, `chevron-right`, `clock`, `warning`

---

## Questions?

- Check existing code for patterns
- Look at similar features for reference
- Run tests to verify changes work
