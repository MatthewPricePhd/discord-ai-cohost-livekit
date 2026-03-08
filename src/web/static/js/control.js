/**
 * Control Room — Producer dashboard for managing the podcast session.
 * Connects to LiveKit (audio-only monitoring) and backend API.
 */
const { Room, RoomEvent, Track, ConnectionState } = LivekitClient;

let room = null;
let transcriptCount = 0;
let currentMode = "passive";
let sessionRunning = false;
let sessionStartTime = null;
let durationTimer = null;
let costPollTimer = null;

// ── Connect to LiveKit room (audio-only monitoring) ───────────────

async function connectToRoom() {
    room = new Room({
        adaptiveStream: true,
        dynacast: true,
    });

    room.on(RoomEvent.Connected, onConnected);
    room.on(RoomEvent.Disconnected, onDisconnected);
    room.on(RoomEvent.ParticipantConnected, onParticipantChanged);
    room.on(RoomEvent.ParticipantDisconnected, onParticipantChanged);
    room.on(RoomEvent.TrackSubscribed, onTrackSubscribed);
    room.on(RoomEvent.DataReceived, onDataReceived);
    room.on(RoomEvent.TranscriptionReceived, onTranscriptionReceived);

    try {
        await room.connect(LIVEKIT_URL, TOKEN);
        setStatus("Live", "green");
        updateParticipantList();
    } catch (err) {
        setStatus("Connection failed", "red");
    }
}

// ── Room event handlers ───────────────────────────────────────────

function onConnected() {
    setStatus("Live", "green");
    const nameEl = document.getElementById("room-name-display");
    if (nameEl) nameEl.textContent = ROOM_NAME;
    updateParticipantList();
}

function onDisconnected() {
    setStatus("Disconnected", "red");
}

function onParticipantChanged() {
    updateParticipantList();
}

function onTrackSubscribed(track) {
    // Attach audio tracks for monitoring (no video)
    if (track.kind === Track.Kind.Audio) {
        const el = track.attach();
        el.style.display = "none";
        document.body.appendChild(el);
    }
}

function onDataReceived(payload, participant, kind, topic) {
    const decoder = new TextDecoder();
    try {
        const msg = JSON.parse(decoder.decode(payload));

        if (topic === "transcript" || msg.type === "transcript") {
            appendTranscript(msg.speaker || participant?.name || "Unknown", msg.text, msg.timestamp);
        } else if (topic === "ai-insights" || msg.type === "insight") {
            addInsight(msg);
        } else if (msg.type === "chat") {
            appendTranscript(participant?.name || "Unknown", msg.message);
        } else if (msg.type === "mode-changed") {
            updateModeUI(msg.mode);
        }
    } catch (_) {
        // Ignore malformed data
    }
}

function onTranscriptionReceived(segments, participant) {
    for (const seg of segments) {
        if (seg.final) {
            const name = participant?.name || participant?.identity || "Unknown";
            appendTranscript(name, seg.text);
            // Also send to backend for archival
            storeTranscriptEntry(name, seg.text);
        }
    }
}

// ── Mode switching ────────────────────────────────────────────────

async function setMode(mode) {
    if (!room || room.state !== ConnectionState.Connected) {
        // Fall back to API call if not connected to room
        try {
            const endpoint = mode === "speech-to-speech"
                ? "/api/mode/speech-to-speech"
                : mode === "ask-chatgpt"
                    ? "/api/mode/ask-chatgpt"
                    : "/api/mode/passive";
            const res = await fetch(endpoint, { method: "POST" });
            if (res.ok) updateModeUI(mode);
        } catch (_) {}
        return;
    }

    // Send mode switch via data message to agent
    const encoder = new TextEncoder();
    const data = encoder.encode(JSON.stringify({
        type: "set-mode",
        mode: mode,
    }));
    await room.localParticipant.publishData(data, { reliable: true, topic: "ai-control" });
    updateModeUI(mode);
}

function updateModeUI(mode) {
    currentMode = mode;
    document.getElementById("mode-passive").classList.toggle("active", mode === "passive");
    document.getElementById("mode-speech").classList.toggle("active", mode === "speech-to-speech");
    document.getElementById("mode-chatgpt").classList.toggle("active", mode === "ask-chatgpt");

    const descriptions = {
        "passive": "Transcription only &mdash; ~$0.005/min",
        "speech-to-speech": "AI responds via voice &mdash; ~$0.30/min",
        "ask-chatgpt": "Text-based AI responses &mdash; ~$0.005/1K tokens",
    };
    document.getElementById("mode-description").innerHTML = descriptions[mode] || "";

    // Update cost rate display
    const rates = { "passive": "~$0.005/min", "speech-to-speech": "~$0.30/min", "ask-chatgpt": "~$0.005/1K tokens" };
    document.getElementById("cost-rate").textContent = "Estimated rate: " + (rates[mode] || "");
}

async function forceAIResponse() {
    if (!room || room.state !== ConnectionState.Connected) return;
    const encoder = new TextEncoder();
    const data = encoder.encode(JSON.stringify({
        type: "force-response",
    }));
    await room.localParticipant.publishData(data, { reliable: true, topic: "ai-control" });
}

// ── Voice selection ───────────────────────────────────────────────

async function selectVoice() {
    const voiceId = document.getElementById("voice-select").value;
    try {
        await fetch("/api/voices/select", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ voice_id: voiceId }),
        });
    } catch (_) {}

    // Also send to agent via data message
    if (room && room.state === ConnectionState.Connected) {
        const encoder = new TextEncoder();
        const data = encoder.encode(JSON.stringify({
            type: "set-voice",
            voice: voiceId,
        }));
        await room.localParticipant.publishData(data, { reliable: true, topic: "ai-control" });
    }
}

// ── System prompt ─────────────────────────────────────────────────

async function updateSystemPrompt() {
    const prompt = document.getElementById("system-prompt").value.trim();
    if (!prompt) return;

    if (room && room.state === ConnectionState.Connected) {
        const encoder = new TextEncoder();
        const data = encoder.encode(JSON.stringify({
            type: "set-system-prompt",
            prompt: prompt,
        }));
        await room.localParticipant.publishData(data, { reliable: true, topic: "ai-control" });
    }
}

// ── Provider config ───────────────────────────────────────────────

async function setTTSProvider() {
    const provider = document.getElementById("tts-provider").value;
    try {
        await fetch("/api/providers/tts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ provider }),
        });
    } catch (_) {}
}

async function setSTTProvider() {
    const provider = document.getElementById("stt-provider").value;
    try {
        await fetch("/api/providers/stt", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ provider }),
        });
    } catch (_) {}
}

// ── Room management ───────────────────────────────────────────────

async function createRoom() {
    const title = document.getElementById("room-title").value.trim();
    if (!title) return;

    const btn = document.getElementById("create-room-btn");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';

    try {
        const res = await fetch("/api/rooms/create", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title }),
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById("active-room-name").textContent = data.room.name;
            document.getElementById("active-room-info").classList.remove("hidden");
            // Store room name for invite generation
            window._activeRoomName = data.room.name;
        }
    } catch (err) {
        // Handle error silently
    }

    btn.disabled = false;
    btn.textContent = "Create";
}

// ── Invite link generation ────────────────────────────────────────

async function generateInvite() {
    const roomName = window._activeRoomName || ROOM_NAME;
    if (!roomName) return;

    const name = document.getElementById("invite-name").value.trim() || "Guest";
    const role = document.getElementById("invite-role").value;

    const btn = document.getElementById("gen-invite-btn");
    btn.disabled = true;

    try {
        const res = await fetch("/api/rooms/" + encodeURIComponent(roomName) + "/invite", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, role }),
        });
        const data = await res.json();
        if (data.success) {
            const linkInput = document.getElementById("invite-link-input");
            // For co-producer role, replace /studio/join with /control
            let link = data.invite_link;
            if (role === "co-producer") {
                link = link.replace("/studio/join?token=", "/control?token=");
            }
            linkInput.value = link;
            document.getElementById("invite-link-result").classList.remove("hidden");
        }
    } catch (_) {}

    btn.disabled = false;
}

function copyInviteLink() {
    const input = document.getElementById("invite-link-input");
    navigator.clipboard.writeText(input.value);
    input.parentElement.classList.add("copy-flash");
    setTimeout(() => input.parentElement.classList.remove("copy-flash"), 500);
}

// ── Session tracking ──────────────────────────────────────────────

async function startSession() {
    try {
        const res = await fetch("/api/session/start", { method: "POST" });
        const data = await res.json();
        if (data.success) {
            sessionRunning = true;
            sessionStartTime = data.start_time;
            document.getElementById("session-start-btn").classList.add("hidden");
            document.getElementById("session-stop-btn").classList.remove("hidden");
            startDurationTimer();
            startCostPolling();
        }
    } catch (_) {}
}

async function stopSession() {
    try {
        const res = await fetch("/api/session/stop", { method: "POST" });
        const data = await res.json();
        if (data.success) {
            sessionRunning = false;
            document.getElementById("session-start-btn").classList.remove("hidden");
            document.getElementById("session-stop-btn").classList.add("hidden");
            stopDurationTimer();
            stopCostPolling();

            // Update final cost
            if (data.total_usd !== undefined) {
                document.getElementById("total-cost").textContent = "$" + data.total_usd.toFixed(4);
                document.getElementById("session-cost-badge").textContent = "$" + data.total_usd.toFixed(4);
            }

            // Update breakdown
            if (data.breakdown && data.breakdown.length > 0) {
                updateCostBreakdown(data.breakdown);
            }
        }
    } catch (_) {}
}

function startDurationTimer() {
    const el = document.getElementById("session-duration");
    durationTimer = setInterval(() => {
        if (!sessionStartTime) return;
        const elapsed = Math.floor(Date.now() / 1000) - sessionStartTime;
        const h = Math.floor(elapsed / 3600);
        const m = Math.floor((elapsed % 3600) / 60);
        const s = elapsed % 60;
        el.textContent = String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
    }, 1000);
}

function stopDurationTimer() {
    if (durationTimer) clearInterval(durationTimer);
    durationTimer = null;
}

function startCostPolling() {
    pollCosts();
    costPollTimer = setInterval(pollCosts, 10000);
}

function stopCostPolling() {
    if (costPollTimer) clearInterval(costPollTimer);
    costPollTimer = null;
}

async function pollCosts() {
    try {
        const res = await fetch("/api/session/status");
        const data = await res.json();
        if (data.live_costs) {
            const total = data.live_costs.total_cost || 0;
            document.getElementById("total-cost").textContent = "$" + total.toFixed(4);
            document.getElementById("session-cost-badge").textContent = "$" + total.toFixed(4);
        }
        if (data.running && data.start_time && !sessionStartTime) {
            sessionStartTime = data.start_time;
            sessionRunning = true;
            document.getElementById("session-start-btn").classList.add("hidden");
            document.getElementById("session-stop-btn").classList.remove("hidden");
            startDurationTimer();
        }
    } catch (_) {}
}

function updateCostBreakdown(breakdown) {
    let stt = 0, llm = 0, tts = 0;
    for (const item of breakdown) {
        const service = (item.service || "").toLowerCase();
        if (service.includes("speech-to-text") || service.includes("stt")) {
            stt += item.cost_usd || 0;
        } else if (service.includes("text-to-speech") || service.includes("tts")) {
            tts += item.cost_usd || 0;
        } else {
            llm += item.cost_usd || 0;
        }
    }
    document.getElementById("cost-stt").textContent = "$" + stt.toFixed(4);
    document.getElementById("cost-llm").textContent = "$" + llm.toFixed(4);
    document.getElementById("cost-tts").textContent = "$" + tts.toFixed(4);
}

// ── Participant management ────────────────────────────────────────

function updateParticipantList() {
    if (!room) return;

    const list = document.getElementById("guest-list");
    const participants = [];

    // Add local participant
    participants.push({
        identity: room.localParticipant.identity,
        name: room.localParticipant.name || room.localParticipant.identity,
        isLocal: true,
        metadata: room.localParticipant.metadata,
    });

    // Add remote participants
    room.remoteParticipants.forEach((p) => {
        participants.push({
            identity: p.identity,
            name: p.name || p.identity,
            isLocal: false,
            isAgent: p.identity === "podcast-cohost-agent",
            metadata: p.metadata,
        });
    });

    document.getElementById("participant-count").textContent = participants.length;
    document.getElementById("guest-count").textContent = participants.length;

    if (participants.length === 0) {
        list.innerHTML = '<p class="text-gray-600 text-[11px] italic text-center py-4">No participants yet</p>';
        return;
    }

    list.innerHTML = participants.map((p) => {
        const roleTag = p.isAgent
            ? '<span class="text-[9px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 border border-purple-500/30">AI</span>'
            : p.isLocal
                ? '<span class="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">You</span>'
                : '<span class="text-[9px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400 border border-green-500/30">Guest</span>';

        const actions = !p.isLocal && !p.isAgent
            ? '<div class="flex gap-1">' +
              '<button onclick="muteParticipant(\'' + p.identity + '\')" class="ctrl-btn btn-surface" style="padding:2px 6px;font-size:9px;" title="Mute">' +
              '<svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2c0 .66-.09 1.3-.27 1.9"/></svg>' +
              '</button>' +
              '<button onclick="removeParticipant(\'' + p.identity + '\')" class="ctrl-btn btn-danger" style="padding:2px 6px;font-size:9px;" title="Remove">' +
              '<svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>' +
              '</button>' +
              '</div>'
            : '';

        return '<div class="guest-row">' +
            '<div class="flex items-center gap-2">' +
            '<div class="w-1.5 h-1.5 rounded-full bg-green-500"></div>' +
            '<span class="text-xs text-gray-300 truncate" style="max-width:100px;">' + escapeHtml(p.name) + '</span>' +
            roleTag +
            '</div>' +
            actions +
            '</div>';
    }).join("");
}

async function muteParticipant(identity) {
    // Use LiveKit server API via backend to mute
    try {
        await fetch("/api/rooms/" + encodeURIComponent(ROOM_NAME) + "/participants/" + encodeURIComponent(identity) + "/mute", {
            method: "POST",
        });
    } catch (_) {}
}

async function removeParticipant(identity) {
    try {
        await fetch("/api/rooms/" + encodeURIComponent(ROOM_NAME) + "/participants/" + encodeURIComponent(identity), {
            method: "DELETE",
        });
        updateParticipantList();
    } catch (_) {}
}

// ── Transcript ────────────────────────────────────────────────────

function appendTranscript(speaker, text, timestamp) {
    const box = document.getElementById("transcript-box");
    const placeholder = box.querySelector(".italic");
    if (placeholder) placeholder.remove();

    const timeStr = timestamp
        ? new Date(timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
        : new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

    const entry = document.createElement("div");
    entry.className = "transcript-entry";
    entry.innerHTML =
        '<div class="flex items-baseline gap-2">' +
        '<span class="text-[10px] text-gray-600 font-mono flex-shrink-0">' + timeStr + '</span>' +
        '<span class="text-studio-accent-light font-medium text-xs">' + escapeHtml(speaker) + '</span>' +
        '</div>' +
        '<div class="text-gray-300 text-[13px] leading-relaxed pl-16 mt-0.5">' + escapeHtml(text) + '</div>';
    box.appendChild(entry);
    box.scrollTop = box.scrollHeight;

    transcriptCount++;
    document.getElementById("transcript-count").textContent = transcriptCount + (transcriptCount === 1 ? " entry" : " entries");
}

async function storeTranscriptEntry(speaker, text) {
    try {
        await fetch("/api/transcript/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                speaker: speaker,
                text: text,
                timestamp: Math.floor(Date.now() / 1000),
            }),
        });
    } catch (_) {}
}

async function exportTranscript() {
    // Collect transcript from DOM
    const entries = document.querySelectorAll("#transcript-box .transcript-entry");
    if (entries.length === 0) return;

    let markdown = "# Podcast Transcript\n\n";
    markdown += "**Exported:** " + new Date().toLocaleString() + "\n";
    markdown += "**Entries:** " + entries.length + "\n\n---\n\n";

    entries.forEach((entry) => {
        const time = entry.querySelector(".font-mono")?.textContent || "";
        const speaker = entry.querySelector(".text-studio-accent-light")?.textContent || "";
        const text = entry.querySelector(".text-gray-300")?.textContent || "";
        markdown += "**[" + time + "] " + speaker + ":** " + text + "\n\n";
    });

    // Download as file
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "transcript_" + new Date().toISOString().slice(0, 10) + ".md";
    a.click();
    URL.revokeObjectURL(url);
}

// ── Insights ──────────────────────────────────────────────────────

function addInsight(msg) {
    const list = document.getElementById("insights-list");
    const placeholder = list.querySelector(".italic");
    if (placeholder) placeholder.remove();

    const card = document.createElement("div");
    card.className = "insight-card";

    const typeColors = {
        "suggestion": "text-cyan-400",
        "fact-check": "text-amber-400",
        "topic": "text-purple-400",
        "analysis": "text-emerald-400",
    };
    const color = typeColors[msg.insight_type] || "text-gray-400";

    card.innerHTML =
        '<div class="flex items-center gap-2 mb-1">' +
        '<span class="text-[10px] font-semibold uppercase tracking-wider ' + color + '">' + escapeHtml(msg.insight_type || "insight") + '</span>' +
        '<span class="text-[9px] text-gray-600 font-mono">' + new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) + '</span>' +
        '</div>' +
        '<p class="text-[12px] text-gray-300 leading-relaxed">' + escapeHtml(msg.content || msg.text || "") + '</p>';

    list.prepend(card);

    const countEl = document.getElementById("insights-count");
    const count = list.querySelectorAll(".insight-card").length;
    countEl.textContent = count;
}

// ── Suggested Topics (from observer insights) ─────────────────────

function addSuggestedTopic(topic) {
    const container = document.getElementById("suggested-topics");
    const placeholder = container.querySelector(".italic");
    if (placeholder) placeholder.remove();

    const el = document.createElement("div");
    el.className = "flex items-center gap-2 py-1";
    el.innerHTML =
        '<svg class="w-3 h-3 text-cyan-400 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="9,18 15,12 9,6"/></svg>' +
        '<span class="text-[12px] text-gray-300">' + escapeHtml(topic) + '</span>';
    container.appendChild(el);
}

// ── Utility ───────────────────────────────────────────────────────

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function setStatus(text, color) {
    const el = document.getElementById("room-status");
    const colors = {
        green: { bg: "rgba(34,197,94,0.1)", border: "rgba(34,197,94,0.2)", text: "#4ade80", dot: "#22c55e" },
        red: { bg: "rgba(239,68,68,0.1)", border: "rgba(239,68,68,0.2)", text: "#f87171", dot: "#ef4444" },
        yellow: { bg: "rgba(234,179,8,0.1)", border: "rgba(234,179,8,0.2)", text: "#facc15", dot: "#eab308" },
    };
    const c = colors[color] || colors.yellow;
    el.style.background = c.bg;
    el.style.borderColor = c.border;
    el.style.color = c.text;
    el.innerHTML = '<div class="w-1.5 h-1.5 rounded-full" style="background:' + c.dot + (color === "green" ? ';animation:live-pulse 1.5s ease-in-out infinite' : '') + '"></div>' + text;
}

// ── Load initial provider config ──────────────────────────────────

async function loadProviderConfig() {
    try {
        const res = await fetch("/api/providers");
        const data = await res.json();
        if (data.tts_provider) {
            document.getElementById("tts-provider").value = data.tts_provider;
        }
        if (data.stt_provider) {
            document.getElementById("stt-provider").value = data.stt_provider;
        }
    } catch (_) {}
}

async function loadVoices() {
    try {
        const res = await fetch("/api/voices");
        const data = await res.json();
        if (data.voices && data.voices.length > 0) {
            const select = document.getElementById("voice-select");
            select.innerHTML = data.voices.map(
                (v) => '<option value="' + v.id + '">' + escapeHtml(v.name) + '</option>'
            ).join("");
        }
    } catch (_) {}
}

// ── Check for active session on load ──────────────────────────────

async function checkActiveSession() {
    try {
        const res = await fetch("/api/session/status");
        const data = await res.json();
        if (data.running) {
            sessionRunning = true;
            sessionStartTime = data.start_time;
            document.getElementById("session-start-btn").classList.add("hidden");
            document.getElementById("session-stop-btn").classList.remove("hidden");
            startDurationTimer();
            startCostPolling();
        }
    } catch (_) {}
}

// ── Memory Search ─────────────────────────────────────────────────

async function searchMemory() {
    const query = document.getElementById("memory-query").value.trim();
    if (!query) return;

    const container = document.getElementById("memory-results");
    container.innerHTML = '<p class="text-gray-500 text-[11px] text-center py-2"><span class="spinner"></span> Searching...</p>';

    try {
        const res = await fetch("/api/memory/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: query, limit: 10 }),
        });
        const data = await res.json();

        if (!data.results || data.results.length === 0) {
            container.innerHTML = '<p class="text-gray-600 text-[11px] italic text-center py-2">No memories found</p>';
            return;
        }

        container.innerHTML = data.results.map(function(mem) {
            const text = mem.memory || mem.text || "";
            const epId = (mem.metadata || {}).episode_id || "?";
            return '<div class="py-1 border-b border-studio-border/50">' +
                '<span class="text-[9px] text-violet-400 font-mono">ep:' + escapeHtml(epId.slice(0, 8)) + '</span> ' +
                '<span class="text-[11px] text-gray-300">' + escapeHtml(text) + '</span>' +
                '</div>';
        }).join("");
    } catch (_) {
        container.innerHTML = '<p class="text-red-400 text-[11px] text-center py-2">Search failed</p>';
    }
}

// Allow Enter key in memory search
document.getElementById("memory-query")?.addEventListener("keydown", function(e) {
    if (e.key === "Enter") searchMemory();
});

// ── Episode History ───────────────────────────────────────────────

async function loadEpisodes() {
    const container = document.getElementById("episode-list");
    try {
        const res = await fetch("/api/episodes");
        const data = await res.json();

        if (!data.episodes || data.episodes.length === 0) {
            container.innerHTML = '<p class="text-gray-600 text-[11px] italic text-center py-2">No episodes yet</p>';
            return;
        }

        container.innerHTML = data.episodes.map(function(ep) {
            const dateStr = ep.date ? ep.date.split("T")[0] : "";
            return '<div class="flex items-center justify-between py-1 border-b border-studio-border/50">' +
                '<div class="flex-1 min-w-0">' +
                '<div class="text-[11px] text-gray-300 truncate">' + escapeHtml(ep.title) + '</div>' +
                '<div class="text-[9px] text-gray-500 font-mono">' + dateStr + ' &middot; ' + (ep.entry_count || 0) + ' entries</div>' +
                '</div>' +
                '<button onclick="exportEpisode(\'' + ep.id + '\')" class="ctrl-btn btn-surface flex-shrink-0" style="padding:2px 6px;font-size:9px;" title="Export">' +
                '<svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>' +
                '</button>' +
                '</div>';
        }).join("");
    } catch (_) {
        container.innerHTML = '<p class="text-red-400 text-[11px] text-center py-2">Failed to load episodes</p>';
    }
}

async function exportEpisode(episodeId) {
    try {
        const res = await fetch("/api/episodes/" + encodeURIComponent(episodeId) + "/export?fmt=markdown");
        const data = await res.json();
        if (data.success && data.content) {
            const blob = new Blob([data.content], { type: "text/markdown" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "episode_" + episodeId.slice(0, 8) + ".md";
            a.click();
            URL.revokeObjectURL(url);
        }
    } catch (_) {}
}

// ── Initialize ────────────────────────────────────────────────────

(async function init() {
    // Set room name if available
    if (ROOM_NAME) {
        window._activeRoomName = ROOM_NAME;
        document.getElementById("active-room-name").textContent = ROOM_NAME;
        document.getElementById("active-room-info").classList.remove("hidden");
    }

    await connectToRoom();
    loadProviderConfig();
    loadVoices();
    checkActiveSession();
    loadEpisodes();
})();
