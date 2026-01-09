# Ad-Free Podcast App

A locally-hosted podcast app that automatically removes ads from downloaded episodes using AI-powered detection.

## Architecture

- **Frontend**: SvelteKit + Svelte 5
- **Backend**: Python (FastAPI)
- **Processing**: Spark DGX via SSH
  - Transcription: faster-whisper
  - Ad Detection: Ollama (llama3.1:70b)
  - Audio Cutting: ffmpeg

## Setup

1. Copy `.env.example` to `.env` and configure
2. Install DGX dependencies (see below)
3. Start the backend: `cd backend && uvicorn main:app`
4. Start the frontend: `npm run dev`

## DGX Setup

```bash
pip install faster-whisper
mkdir -p ~/podcast_processor
```

## How It Works

1. Search podcasts via iTunes API
2. Select episode to download
3. Backend sends audio to DGX for processing:
   - Transcribe with Whisper
   - Detect ads with LLM analysis
   - Cut ad segments with ffmpeg
4. Clean audio served back to frontend
