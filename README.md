# AdBlock Podcast

A self-hosted podcast app that automatically removes ads from podcast episodes using AI-powered transcription and detection.

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                              User Flow                               │
├─────────────────────────────────────────────────────────────────────┤
│  1. Search & Subscribe    2. Queue Episodes    3. Listen Ad-Free    │
│         │                        │                     │            │
│    iTunes API              Background Worker      Processed Audio   │
│         │                        │                     │            │
│         ▼                        ▼                     ▼            │
│  ┌──────────┐              ┌──────────┐          ┌──────────┐      │
│  │ SvelteKit│──subscribe──▶│  SQLite  │◀─────────│  Player  │      │
│  │ Frontend │              │    DB    │          │    UI    │      │
│  └──────────┘              └────┬─────┘          └──────────┘      │
│                                 │                                   │
│                                 ▼                                   │
│                          ┌───────────┐                              │
│                          │ DGX Spark │  ◀── GPU Processing          │
│                          │  Backend  │      - Whisper transcription │
│                          └───────────┘      - LLM ad detection      │
│                                             - FFmpeg audio cutting  │
└─────────────────────────────────────────────────────────────────────┘
```

## Features

- **Podcast Search**: Search iTunes podcast directory
- **Subscription Management**: Subscribe/unsubscribe to podcasts
- **Ad Removal**: AI-powered ad detection and removal
- **RSS Feed Generation**: Generate ad-free RSS feeds for any podcast app
- **Queue System**: Background processing with priority queue
- **Mobile-Friendly UI**: Apple Podcasts-style interface

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | SvelteKit, Svelte 5, TypeScript |
| Database | SQLite (better-sqlite3) |
| Backend | Python FastAPI (on DGX Spark) |
| AI | OpenAI Whisper, Ollama (qwen3-coder) |
| Audio | FFmpeg |
| Testing | Vitest, Playwright |

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.10+ (for backend)
- FFmpeg (for audio processing)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/adblock-podcast.git
cd adblock-podcast

# Install dependencies
npm install

# Start development server
npm run dev
```

The app will be available at `http://localhost:5173`

### Running the Backend (DGX)

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Project Structure

```
adblock-podcast/
├── src/
│   ├── routes/                    # SvelteKit pages and API routes
│   │   ├── +page.svelte           # Home (Library view)
│   │   ├── +layout.svelte         # App layout with player
│   │   ├── search/                # Podcast search page
│   │   ├── podcast/[id]/          # Podcast detail page
│   │   ├── feed/[podcastId].xml/  # RSS feed generator
│   │   └── api/                   # REST API endpoints
│   │       ├── search/            # iTunes search proxy
│   │       ├── subscriptions/     # Subscription CRUD
│   │       ├── queue/             # Processing queue
│   │       ├── process/           # Processing status
│   │       └── audio/             # Audio streaming
│   │
│   ├── lib/                       # Shared code
│   │   ├── components/            # Svelte components
│   │   │   ├── common/            # Reusable UI (Icon, Spinner)
│   │   │   ├── player/            # Audio player (Mini, Full)
│   │   │   ├── library/           # Library grid and cards
│   │   │   └── podcast/           # Podcast detail components
│   │   │
│   │   ├── stores/                # Svelte stores
│   │   │   ├── player.svelte.ts   # Audio player state
│   │   │   └── library.svelte.ts  # Subscription state
│   │   │
│   │   ├── db/                    # Database layer
│   │   │   ├── index.ts           # SQLite connection
│   │   │   ├── subscriptions.ts   # Subscription CRUD
│   │   │   ├── episodes.ts        # Episode management
│   │   │   └── queue.ts           # Processing queue
│   │   │
│   │   ├── services/              # Business logic
│   │   │   ├── api.ts             # API response helpers
│   │   │   └── rss.ts             # RSS feed parsing
│   │   │
│   │   ├── utils/                 # Utility functions
│   │   │   ├── validation.ts      # Input validation (SSRF prevention)
│   │   │   ├── format.ts          # Time/date formatting
│   │   │   ├── config.ts          # App configuration
│   │   │   └── xml.ts             # XML parsing utilities
│   │   │
│   │   ├── worker/                # Background processing
│   │   │   └── processor.ts       # Queue processor
│   │   │
│   │   └── types.ts               # TypeScript interfaces
│   │
│   └── hooks.server.ts            # Server hooks (starts worker)
│
├── backend/                       # Python FastAPI backend
│   ├── main.py                    # API server
│   └── processed/                 # Processed audio files
│
├── tests/                         # Unit tests (Vitest)
├── e2e/                           # E2E tests (Playwright)
├── data/                          # SQLite database
└── static/                        # Static assets
```

## Available Scripts

```bash
# Development
npm run dev              # Start dev server (http://localhost:5173)
npm run build            # Production build
npm run preview          # Preview production build

# Testing
npm run test             # Run unit tests
npm run test:watch       # Run tests in watch mode
npm run test:e2e         # Run E2E tests (Playwright)

# Code Quality
npm run check            # TypeScript check
npm run lint             # ESLint
npm run lint:fix         # Fix lint issues
npm run format           # Prettier formatting
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/search?q=` | GET | Search iTunes for podcasts |
| `/api/subscriptions` | GET | List all subscriptions |
| `/api/subscriptions` | POST | Subscribe to a podcast |
| `/api/subscriptions/[id]` | GET | Get subscription with episodes |
| `/api/subscriptions/[id]` | DELETE | Unsubscribe |
| `/api/queue` | GET | Get processing queue |
| `/api/queue` | POST | Add episode to queue |
| `/api/audio/[episodeId]` | GET | Stream processed audio |
| `/feed/[podcastId].xml` | GET | Get RSS feed for podcast |

## Database Schema

```sql
-- User subscriptions
subscriptions (
  podcast_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  feed_url TEXT NOT NULL,
  ...
)

-- Episode metadata
episodes (
  episode_id TEXT PRIMARY KEY,
  podcast_id TEXT REFERENCES subscriptions,
  title TEXT NOT NULL,
  audio_url TEXT NOT NULL,
  ...
)

-- Processing status
processed_episodes (
  episode_id TEXT PRIMARY KEY REFERENCES episodes,
  status TEXT DEFAULT 'pending',  -- pending|queued|processing|ready|error
  processed_path TEXT,
  ...
)

-- Processing queue
queue (
  id INTEGER PRIMARY KEY,
  episode_id TEXT UNIQUE REFERENCES episodes,
  priority INTEGER DEFAULT 0,
  ...
)
```

## Configuration

Environment variables (or edit `src/lib/utils/config.ts`):

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_URL` | `http://localhost:8000` | DGX backend URL |

## Network Access

To access from other devices (e.g., phone):

1. The dev server binds to `0.0.0.0:5173` by default
2. Find your machine's IP: `ip addr` or `ifconfig`
3. Access from phone: `http://192.168.x.x:5173`
4. Add RSS feed to podcast app: `http://192.168.x.x:5173/feed/[podcastId].xml`

## Testing

### Unit Tests (Vitest)

```bash
npm run test             # Run once
npm run test:watch       # Watch mode
npm run test:coverage    # With coverage report
```

Test files are in `tests/` following the structure of `src/lib/`.

### E2E Tests (Playwright)

```bash
npm run test:e2e         # Run E2E tests
npm run test:e2e:ui      # Interactive UI mode
```

E2E tests are in `e2e/` and test full user flows.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for development guidelines.

## License

MIT
