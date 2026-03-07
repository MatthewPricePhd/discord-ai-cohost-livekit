# Discord AI Co-Host — Progress & Next Steps

## Current Status (March 2026)

### What's Working

**Web Dashboard** — Running on `http://localhost:8000`
- 2x2 + 2-column layout optimized for 1920x1080
  - Top-Left: **Control Panel** (voice channel, mode buttons, force response, documents)
  - Top-Right: **Ask ChatGPT** (input + send button + response area)
  - Bottom-Left: **Configuration** (providers/models, session spend tracking)
  - Bottom-Right: **Context Summary** (generate, export)
  - Right columns: **Live Conversation** + **AI Insights** (observer)
- Responsive breakpoints: scrolls on smaller screens, fills viewport on xl+
- Compact nav bar with live status indicators

**Discord Bot** — Online as AI-Cohost#2827
- Connects to guilds, lists voice channels
- Joins voice channels including E2EE channels (can speak, cannot yet capture incoming audio)
- Voice dependencies: PyNaCl, davey (DAVE E2EE), opus codec auto-loaded
- Requires `discord-ext-voice-recv` or Pycord for audio capture (listening)
- Bot invite URL with correct permissions (Connect, Speak, VAD, etc.)

**API Endpoints** — All core routes functional
- `/api/status`, `/api/discord/guilds`, `/api/documents`
- `/api/session/start`, `/api/session/stop`, `/api/session/status`
- `/api/mode/passive`, `/api/mode/speech-to-speech`, `/api/ai/ask-chatgpt`
- `/api/providers`, `/api/voices`, `/api/observer/insights`
- `/api/chatgpt/completion`, `/api/conversation/transcript`
- `/api/logs`, `/api/export/transcript`, `/api/export/context`

**Session Spend Tracking** — Real cost data (no mock data)
- Tracks STT minutes, TTS minutes/characters, tokens in/out, API requests
- Per-provider breakdown (OpenAI, ElevenLabs)
- Uses OpenAI Admin API key for usage queries
- Computed costs from `openai_client.get_session_costs()`

**Automated Testing** — Playwright test suite (33 tests, all passing)
- Dashboard smoke tests: layout, panels, controls, inputs (21 tests)
- API smoke tests: all GET/POST endpoints validated (12 tests)
- Slash commands: `/test`, `/test-ui`, `/test-api`, `/smoke`, `/test-visual`

### Recently Fixed

- **Voice channel join** — Bot now successfully joins voice channels (including DocDocBot Podcast)
  - Fixed JS number precision: Discord snowflake IDs exceed JS `Number.MAX_SAFE_INTEGER`, now serialized as strings
  - Added `fetch_channel()` API fallback when channel not in bot cache
  - Accepts both `VoiceChannel` and `StageChannel` types
  - Installed `PyNaCl` (voice encryption), `davey` (Discord E2EE/DAVE protocol), loaded `opus` codec
  - Fixed error propagation: `HTTPException` no longer swallowed by generic `except` handler
  - API accepts both string and int channel IDs (`Union[str, int]`) for robustness
  - Cache-busted static JS with `?v=2` query param

### Known Issues

- **Voice audio capture**: Bot joins voice but can't listen — discord.py 2.7.1 lacks `.listen()`. Need Pycord or `discord-ext-voice-recv`.
- **TESTING_GUIDE.md**: Outdated — references old 3-column layout and wrong panel positions. Needs rewrite to match current 2x2+2 layout.
- **API key exposure**: Real keys in `.env` (gitignored) but were in `.env.example` in earlier iterations — verify before making repo public.

---

## Testing Plan

### Automated Tests (Playwright)

Run with `npx playwright test` or use slash commands:

| Command | Scope | Tests |
|---------|-------|-------|
| `/test` | Full suite | 33 |
| `/test-ui` | Dashboard layout & controls | 21 |
| `/test-api` | API endpoint validation | 12 |
| `/smoke` | Live browser check via chrome automation | Manual |
| `/test-visual` | 1920x1080 layout verification | Manual |

### Manual Test Cases Still Needed

1. **Mode switching flow** — Click each mode button, verify API calls and UI state changes
2. **Ask ChatGPT end-to-end** — Type question, send, verify response appears, test Clear and To Context
3. **Document upload** — Upload PDF/DOCX/TXT, verify in list, send to context
4. **Session spend lifecycle** — Start → perform actions → Stop → verify real cost breakdown
5. **Voice channel join/leave** — Select channel, join, verify status, leave
6. **Export transcript/context** — Generate content, export, verify file download
7. **Observer insights** — Enable/disable, set frequency, verify polling
8. **Provider switching** — Change TTS/STT provider, verify selection persists
9. **Error handling** — Invalid channel join, network failure, API errors

### Tests to Add to Playwright

- Mode button click → API call → UI state update
- ChatGPT completion flow (mock API or real)
- Session start/stop lifecycle with cost validation
- Provider dropdown change → POST to API
- Observer toggle and frequency change
- Document upload via file input
- Export button state management

---

## OBS Integration Plan

### Overview

Integrate the AI Co-Host dashboard with OBS Studio for seamless podcast recording. Three integration points:

### Phase 1: Browser Source Overlay (`/obs` route)

Create a transparent overlay page at `http://localhost:8000/obs` for use as an OBS Browser Source.

**Features:**
- Live transcript captions (current speaker + AI response)
- AI status indicator (listening, thinking, speaking)
- Talking points / fact-check alerts from observer
- Transparent background for compositing over video

**Implementation:**
- New template: `src/web/templates/obs_overlay.html`
- New route: `GET /obs` with optional query params (`?show=captions,status,alerts`)
- WebSocket or SSE for real-time updates (no polling)
- CSS animations for smooth text transitions
- Configurable font size, position, colors via query params

**OBS Setup:**
1. Add Browser Source → URL: `http://localhost:8000/obs`
2. Set width/height to match canvas (1920x1080)
3. Check "Shutdown source when not visible"

### Phase 2: Browser Dock Panel

Create a compact control panel at `http://localhost:8000/obs/dock` for OBS's custom browser dock feature.

**Features:**
- Minimal controls: mode switch, start/stop session, force response
- Live cost counter
- Voice channel status
- Compact vertical layout (OBS docks are narrow)

**Implementation:**
- New template: `src/web/templates/obs_dock.html`
- New route: `GET /obs/dock`
- Shares same API endpoints as main dashboard
- Responsive design for narrow width (~300px)
- Dark theme matching OBS

**OBS Setup:**
1. View → Docks → Custom Browser Docks
2. Name: "AI Co-Host" → URL: `http://localhost:8000/obs/dock`

### Phase 3: OBS WebSocket Integration

Connect to OBS via obs-websocket (built into OBS 28+) for programmatic control.

**Features:**
- Auto-detect recording state (start/stop session tracking with recording)
- Scene switching triggers (e.g., switch to "AI Speaking" scene)
- Source visibility control (show/hide overlay elements)
- Recording markers when AI responds

**Implementation:**
- New module: `src/integrations/obs_websocket.py`
- Uses `obs-websocket-py` or `simpleobsws` library
- Config: `OBS_WEBSOCKET_URL=ws://localhost:4455`, `OBS_WEBSOCKET_PASSWORD=...`
- Event handlers: `RecordingStarted`, `RecordingStopped`, `SceneChanged`

**Dependencies:**
```
# Add to requirements.txt
obsws-python>=1.0.0
```

### Phase 4: Unified Workflow

End-to-end podcast recording workflow:

1. **Pre-show**: Open OBS, dashboard loads in dock, overlay active in scene
2. **Start recording**: OBS triggers session tracking automatically
3. **During show**: Live captions overlay, AI insights in dock, mode switching from dock
4. **AI responds**: OBS scene switch to "AI Speaking" layout, TTS plays in Discord
5. **Stop recording**: Session costs calculated, transcript exported automatically
6. **Post-show**: Export transcript + context summary for show notes

### OBS Integration — File Structure

```
src/
  web/
    templates/
      obs_overlay.html     # Phase 1: transparent overlay
      obs_dock.html         # Phase 2: compact dock panel
  integrations/
    obs_websocket.py        # Phase 3: OBS WebSocket client
```

### OBS Integration — Priority

| Phase | Effort | Value | Priority |
|-------|--------|-------|----------|
| 1. Browser Source Overlay | Low | High | Do first |
| 2. Browser Dock Panel | Low | Medium | Do second |
| 3. OBS WebSocket | Medium | High | Do third |
| 4. Unified Workflow | Low | High | Do last (ties it together) |

---

## Other Future Work

- **Voice audio capture**: Switch to Pycord or add `discord-ext-voice-recv` for incoming audio
- **Git init + .gitignore**: Set up repository, ensure .env excluded
- **ElevenLabs integration**: Test TTS/STT with ElevenLabs provider
- **Context window management**: Implement sliding window for long sessions
- **Vector storage**: ChromaDB integration for document embeddings
- **Docker**: Update Dockerfile for current dependencies
