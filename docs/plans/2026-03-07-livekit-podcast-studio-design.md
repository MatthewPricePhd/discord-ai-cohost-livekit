# LiveKit Podcast Studio — Design Document

**Date:** 2026-03-07
**Status:** Approved
**Project:** discord-ai-cohost-livekit

## Summary

Replace Discord voice integration with LiveKit to build a self-contained podcast studio. Two browser views — Studio (on-air, OBS-capturable) and Control Room (producer dashboard) — with an AI co-host that joins as a native LiveKit room participant. Long-term memory via Mem0 enables the AI to reference past episodes. Post-episode content pipeline generates blog posts and show notes from transcripts.

## Why LiveKit

The original Discord-based pipeline required manual SRTP + DAVE E2EE decryption, Opus decoding, and audio resampling. DAVE decryption produced corrupted audio despite reporting success — a fundamental limitation of reverse-engineering Discord's undocumented protocol. LiveKit provides clean WebRTC audio out of the box, plus video, screen sharing, and recording.

## Architecture

### Two-View System

**Studio View** (what guests see, what OBS captures):
- Video grid (auto-scales 1-4+ participants)
- AI co-host tile (avatar/waveform animation when speaking)
- Live scrolling transcript captions
- Minimal controls: upload docs, send message, trigger AI

**Control Room** (producer dashboard):
- Session management: create rooms, generate invite links, admit guests
- AI controls: mode switching (Passive/Speech/ChatGPT), voice selection, provider config
- Live transcript with speaker tags, timestamps, export
- Observer agent insights, suggested topics, fact checks
- Ask ChatGPT panel for text-based queries
- Session cost tracking
- Document management and RAG status
- Mini video preview of the studio

### Three Access Roles

| Role | View | Access |
|------|------|--------|
| Producer | Control Room | Authenticated (login or token) |
| Co-Producer | Control Room | Shareable token-scoped link |
| Guest | Studio Only | Invite link (one-time or reusable) |

### Two Processes, One Codebase

| Process | Role | Framework |
|---------|------|-----------|
| Web Server | UI, REST API, room/token management, transcript archive, content pipeline | FastAPI + Uvicorn |
| Agent Worker | AI participant in LiveKit rooms, STT/LLM/TTS pipeline, memory queries | livekit-agents AgentServer |

Communication between processes:
- LiveKit Room Events (audio tracks, data messages)
- Shared storage (Mem0, ChromaDB, SQLite/Postgres)
- LiveKit Server API (web server creates rooms, agent auto-joins)

### System Diagram

```
FastAPI Web Server              LiveKit Agent Worker
├─ /studio  → Studio UI        ├─ AgentSession
├─ /control → Control Room     │  ├─ STT (OpenAI/Deepgram)
├─ /api/*   → REST API         │  ├─ LLM (GPT Realtime/5.4)
├─ /ws      → WebSocket        │  ├─ TTS (OpenAI/ElevenLabs)
│                               │  └─ VAD (Silero)
├─ Room management              ├─ Observer Agent
├─ Token generation             ├─ Mem0 Client
├─ Transcript archive           └─ RAG retrieval
└─ Content pipeline
        │                              │
        ▼                              ▼
   ┌─────────┐  ┌──────────┐  ┌──────────────┐
   │  Mem0   │  │ ChromaDB │  │ SQLite/PG    │
   │ (memory)│  │ (vectors)│  │ (transcripts)│
   └─────────┘  └──────────┘  └──────────────┘
                      │
                      ▼
              LiveKit Cloud (WebRTC)
               ▲    ▲    ▲
              /     |     \
         Host   Guest   AI Agent
```

## Split-Stack Modes (Cost Optimization)

| Mode | Model | Cost | Use |
|------|-------|------|-----|
| Passive | Deepgram streaming STT | ~$0.005/min | Default — transcription only |
| Speech-to-Speech | OpenAI Realtime (gpt-realtime) | ~$0.30/min | AI speaks in conversation |
| Ask ChatGPT | GPT-5.4 + RAG + Mem0 | ~$0.005/1K tokens | Text-based analysis |

## Memory & Knowledge System

### Mem0 (Long-Term Memory)
- Cross-episode memory ("In episode 12, guest Sarah mentioned...")
- Recurring topics and themes
- Guest preferences and history
- Facts and claims across episodes

### ChromaDB (Document RAG)
- Per-episode uploaded documents
- Global knowledge base (grows over time)
- Sentence-transformers embeddings

### Transcript Archive (SQLite → Postgres)
- Full searchable transcript per episode
- Speaker attribution, timestamps
- Episode metadata (date, guests, topics)
- Export to markdown/JSON

### Content Pipeline (Post-Episode)
- Blog post generation from transcript via LLM
- Show notes: key topics, timestamps, links
- Social clips: notable quotes with timestamps
- Raw transcript export (markdown, JSON)

## Technology Choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| WebRTC | LiveKit Cloud → self-hosted | Approach C: fast dev, migrate later |
| AI voice (active) | openai.realtime.RealtimeModel | Lowest latency speech-to-speech |
| AI voice (passive) | Deepgram streaming STT | Cheap, accurate passive transcription |
| TTS fallback | ElevenLabs / OpenAI TTS | Hot-swappable from Control Room |
| VAD | Silero (livekit plugin) | Proven, built into agents SDK |
| Long-term memory | Mem0 | Cross-session recall |
| Document RAG | ChromaDB + sentence-transformers | Carried over from current codebase |
| Transcript DB | SQLite (dev) → Postgres (prod) | Searchable, exportable |
| Web framework | FastAPI + Uvicorn | Carried over |
| Frontend | Jinja2 + livekit-client JS SDK | SSR templates + WebRTC video |
| Styling | Tailwind CSS | Carried over |

## What We Keep, Replace, and Build

### Keep (carry over)
- `src/web/` — FastAPI app structure, route patterns, Tailwind theme
- `src/context/` — observer agent, summarizer, retrieval, notes
- `src/documents/` — processor, uploader, vector store
- `src/config/` — settings pattern, logging (extend with LiveKit vars)
- `src/api/provider.py` — provider abstraction pattern

### Replace (LiveKit handles this)
- `src/bot/` — entire Discord layer (client, voice_manager, voice_receiver, audio_handler)
- `src/api/websocket_manager.py` — LiveKit manages connections
- `src/api/realtime_handler.py` — replaced by livekit.plugins.openai.realtime
- All SRTP/DAVE/Opus code — gone

### Build New
- `src/agent/` — LiveKit agent worker, split-stack mode switching
- `src/web/templates/studio.html` — Studio view with video
- `src/web/templates/control.html` — Control Room (evolved dashboard)
- `src/rooms/` — Room management, token generation, invite links
- `src/memory/` — Mem0 integration
- `src/archive/` — Transcript storage, content pipeline

## Implementation Phases

### Phase 1: Foundation — LiveKit Room + Basic Audio
- LiveKit agent worker with AgentSession
- Room management (create room, generate tokens)
- Studio view with livekit-client JS SDK (video grid)
- AI agent with OpenAI Realtime (speech-to-speech)
- FastAPI routes for room/token management
- **Milestone:** Join a room in browser, talk, AI responds via voice

### Phase 2: Control Room + Split-Stack Modes
- Control Room view (evolved from current dashboard)
- Split-stack mode switching (Passive/Speech/ChatGPT)
- Passive mode with streaming STT
- Live transcript in both views
- Session cost tracking
- Guest admission (waiting room, mute/remove)
- Invite link generation with role-based tokens
- **Milestone:** Full producer workflow end-to-end

### Phase 3: Memory + Knowledge System
- Mem0 integration for long-term memory
- ChromaDB/RAG carried over for documents
- Transcript archive (SQLite, per-episode)
- AI context injection (Mem0 + RAG + transcript)
- Document upload from Studio and Control Room
- Observer agent ported to agent worker
- **Milestone:** AI references past episodes and uploaded docs

### Phase 4: Content Pipeline + Polish
- Transcript export (markdown, JSON)
- Blog post generation from transcript
- Show notes generation
- AI avatar/waveform animation in Studio
- Screen sharing support
- Recording via LiveKit Egress API
- **Milestone:** End podcast, generate blog post in one click

### Phase 5: Production Hardening
- Self-hosted LiveKit server option (Docker)
- Authentication for Control Room
- Error recovery (agent reconnection, room cleanup)
- Mobile-friendly Studio view
- Rate limiting, input validation, security audit
- **Milestone:** Reliable for live recording sessions

## Agent Team Parallelization

| Team | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|------|---------|---------|---------|---------|---------|
| Backend/Agent | Agent worker, room mgmt, tokens | Mode switching, cost tracking | Mem0, archive DB | Content pipeline LLM | Self-hosted, auth |
| Frontend/UI | Studio view, video grid | Control Room, transcript UI, invite UI | Upload UI, memory UI | Avatar animation, screen share | Mobile, polish |
| Data/Memory | — | — | Mem0 setup, RAG port, transcript schema | Export formats | Security audit |

Phases 1-2: Backend + Frontend in parallel.
Phase 3+: Data/Memory team joins.
