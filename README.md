# LiveKit Podcast Studio

An AI-powered podcast studio built on LiveKit. Features a browser-based Studio view (for recording and OBS capture), a Control Room (producer dashboard), and an AI co-host that joins as a native room participant with long-term memory across episodes.

## Features

- **Studio View**: Video grid for host + guests + AI avatar, live transcript, OBS-capturable
- **Control Room**: Producer dashboard with AI controls, mode switching, invite links, session costs
- **AI Co-Host**: OpenAI Realtime speech-to-speech via LiveKit Agents SDK
- **Split-Stack Modes**: Passive (STT only), Speech-to-Speech, Ask ChatGPT
- **Long-Term Memory**: Mem0 for cross-episode recall ("In episode 12, Sarah mentioned...")
- **Transcript Archive**: SQLite-based per-episode storage with full-text search and export
- **Content Pipeline**: Generate blog posts, show notes, and social clips from transcripts
- **Document RAG**: Upload PDFs/DOCX for AI context via ChromaDB
- **Observer Agent**: Background conversation analysis with insights and fact-checks
- **Mobile-Friendly**: Responsive Studio and Control Room layouts
- **Auth & Security**: Optional Control Room password, rate limiting, CORS

## Quick Start

### Prerequisites

- Python 3.11+
- [LiveKit Cloud account](https://cloud.livekit.io) (or self-hosted LiveKit server)
- OpenAI API key with Realtime API access

### 1. Clone and Setup

```bash
git clone https://github.com/MatthewPricePhd/discord-ai-cohost-livekit.git
cd discord-ai-cohost-livekit

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required variables:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
OPENAI_API_KEY=your_openai_api_key
SECRET_KEY=your_random_secret_key
```

Optional:

```env
CONTROL_ROOM_PASSWORD=your_password    # Protect Control Room (no auth if unset)
ELEVENLABS_API_KEY=your_key            # ElevenLabs TTS
WEB_PORT=8000                          # Web server port (default: 8000)
```

### 3. Start the Application

Two processes run from one codebase:

```bash
# Terminal 1: Web server (UI, API, room management)
python -m src.main

# Terminal 2: Agent worker (AI participant in LiveKit rooms)
python run_agent.py dev
```

### 4. Create a Podcast Session

1. Open `http://localhost:8000/studio/create`
2. Enter a room name and click Create
3. Share the Studio invite link with guests
4. Open the Control Room link for producer controls
5. The AI co-host auto-joins when someone enters the room

## Architecture

### Two-Process System

| Process | Role | Command |
|---------|------|---------|
| Web Server | UI, REST API, room/token management, transcript archive | `python -m src.main` |
| Agent Worker | AI participant, STT/LLM/TTS pipeline, memory queries | `python run_agent.py dev` |

### Two-View System

**Studio View** (what guests see, what OBS captures):
- Auto-scaling video grid (1-4+ participants)
- AI co-host avatar with animated waveform
- Live scrolling transcript
- Mic/cam toggles, Ask AI, screen share

**Control Room** (producer dashboard):
- Mode switching (Passive / Speech / ChatGPT)
- Invite link generation with role-based tokens
- Live transcript with speaker tags and export
- Episode history, memory search, content generation
- Session cost tracking

### Three Access Roles

| Role | View | Access |
|------|------|--------|
| Producer | Control Room | Full access (room_admin) |
| Co-Producer | Control Room | Shareable token link |
| Guest | Studio Only | Invite link |

### System Diagram

```
FastAPI Web Server              LiveKit Agent Worker
├─ /studio  → Studio UI        ├─ AgentSession
├─ /control → Control Room     │  ├─ STT (Deepgram)
├─ /api/*   → REST API         │  ├─ LLM (OpenAI Realtime)
│                               │  ├─ TTS (OpenAI/ElevenLabs)
├─ Room management              │  └─ VAD (Silero)
├─ Token generation             ├─ Observer Agent
├─ Transcript archive           ├─ Mem0 Client
└─ Content pipeline             └─ RAG retrieval
        │                              │
        ▼                              ▼
   ┌─────────┐  ┌──────────┐  ┌──────────────┐
   │  Mem0   │  │ ChromaDB │  │ SQLite       │
   │ (memory)│  │ (vectors)│  │ (transcripts)│
   └─────────┘  └──────────┘  └──────────────┘
                      │
                      ▼
              LiveKit Cloud (WebRTC)
               ▲    ▲    ▲
              /     |     \
         Host   Guest   AI Agent
```

## API Endpoints

### Room Management
- `POST /api/rooms/create` — Create room, returns token
- `GET /api/rooms` — List active rooms
- `DELETE /api/rooms/{name}` — Delete a room
- `POST /api/rooms/{name}/invite` — Generate invite link

### Transcript & Episodes
- `POST /api/transcript/add` — Add transcript entry
- `GET /api/transcript` — Get transcript
- `GET /api/episodes` — List episodes
- `GET /api/episodes/{id}` — Get episode details
- `GET /api/episodes/{id}/export` — Export as markdown/JSON

### Content Pipeline
- `POST /api/episodes/{id}/blog-post` — Generate blog post
- `POST /api/episodes/{id}/show-notes` — Generate show notes
- `POST /api/episodes/{id}/social-clips` — Generate social clips

### Memory & AI
- `POST /api/memory/search` — Search long-term memory
- `POST /api/mode` — Switch AI mode
- `GET /api/health` — Health check with LiveKit connectivity

## Docker

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f
```

The `docker-compose.yml` includes both the web server and agent worker.

## Testing

```bash
# Run all tests (54 tests)
python -m pytest tests/ -v

# Run specific test files
python -m pytest tests/test_rooms.py -v
python -m pytest tests/test_archive.py -v
python -m pytest tests/test_memory.py -v
python -m pytest tests/test_content_pipeline.py -v
python -m pytest tests/test_integration_e2e.py -v
```

## Cost Estimation

| Mode | Model | Cost | Use |
|------|-------|------|-----|
| Passive | Deepgram STT | ~$0.005/min | Default — transcription only |
| Speech-to-Speech | OpenAI Realtime | ~$0.30/min | AI speaks in conversation |
| Ask ChatGPT | GPT-5.4 + RAG + Mem0 | ~$0.005/1K tokens | Text-based analysis |

**Estimated cost for 60-minute podcast**: ~$2-4 (with split-stack optimization)

## Troubleshooting

1. **Agent won't join room** — Check `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` in `.env`
2. **No AI audio** — Verify `OPENAI_API_KEY` has Realtime API access
3. **Studio won't connect** — Ensure both web server and agent worker are running
4. **Memory errors** — Mem0 requires ChromaDB; check `./data/mem0_chroma` directory

Enable debug logging:

```env
LOG_LEVEL=DEBUG
ENV=development
```

## License

MIT
