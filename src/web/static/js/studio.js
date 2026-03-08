/**
 * Studio View — LiveKit room connection and media management.
 */
const { Room, RoomEvent, Track, VideoPresets, ConnectionState, ConnectionQuality } = LivekitClient;

let room = null;
let micEnabled = true;
let camEnabled = true;
let screenShareEnabled = false;
let transcriptCount = 0;

// Audio visualizer state
let aiAudioContext = null;
let aiAnalyser = null;
let aiVisualizerRAF = null;

// ── Connect to LiveKit room ──────────────────────────────────────

async function connectToRoom() {
    room = new Room({
        adaptiveStream: true,
        dynacast: true,
        videoCaptureDefaults: { resolution: VideoPresets.h720.resolution },
    });

    // Event listeners
    room.on(RoomEvent.Connected, onConnected);
    room.on(RoomEvent.Disconnected, onDisconnected);
    room.on(RoomEvent.TrackSubscribed, onTrackSubscribed);
    room.on(RoomEvent.TrackUnsubscribed, onTrackUnsubscribed);
    room.on(RoomEvent.ParticipantConnected, onParticipantConnected);
    room.on(RoomEvent.ParticipantDisconnected, onParticipantDisconnected);
    room.on(RoomEvent.DataReceived, onDataReceived);
    room.on(RoomEvent.TranscriptionReceived, onTranscriptionReceived);
    room.on(RoomEvent.ActiveSpeakersChanged, onActiveSpeakersChanged);
    room.on(RoomEvent.ConnectionQualityChanged, onConnectionQualityChanged);

    try {
        await room.connect(LIVEKIT_URL, TOKEN);
        await room.localParticipant.enableCameraAndMicrophone();
        addLocalVideoTile();
        updateGridLayout();
    } catch (err) {
        setStatus("Connection failed", "red");
    }
}

// ── Room event handlers ──────────────────────────────────────────

function onConnected() {
    setStatus("Live", "green");
    // Render any participants already in the room
    room.remoteParticipants.forEach((p) => {
        onParticipantConnected(p);
    });
}

function onDisconnected() {
    setStatus("Disconnected", "red");
}

function onParticipantConnected(participant) {
    // Agent participant gets the AI tile treatment
    if (participant.identity === "podcast-cohost-agent") {
        return; // AI uses the static tile, tracks attached there
    }
    addParticipantTile(participant);
    updateGridLayout();
}

function onParticipantDisconnected(participant) {
    const tile = document.getElementById("tile-" + participant.identity);
    if (tile) {
        tile.classList.add("leaving");
        setTimeout(function() {
            tile.remove();
            updateGridLayout();
        }, 300);
    } else {
        updateGridLayout();
    }
}

function onTrackSubscribed(track, publication, participant) {
    if (participant.identity === "podcast-cohost-agent") {
        // AI co-host: attach audio only (no video), animate avatar
        if (track.kind === Track.Kind.Audio) {
            const el = track.attach();
            document.getElementById("ai-tile").appendChild(el);
            // Set up real audio visualizer using Web Audio API
            setupAIAudioVisualizer(el);
        }
        return;
    }

    const container = document.getElementById("media-" + participant.identity);
    if (!container) return;

    const el = track.attach();
    if (track.kind === Track.Kind.Video) {
        el.style.width = "100%";
        el.style.height = "100%";
        el.style.objectFit = "cover";
    }
    container.appendChild(el);
}

function onTrackUnsubscribed(track, publication, participant) {
    track.detach().forEach((el) => el.remove());
}

function onActiveSpeakersChanged(speakers) {
    const aiTile = document.getElementById("ai-tile-wrapper");
    const isAISpeaking = speakers.some((s) => s.identity === "podcast-cohost-agent");
    if (isAISpeaking) {
        aiTile.classList.add("ai-speaking");
    } else {
        aiTile.classList.remove("ai-speaking");
    }
}

function onDataReceived(payload, participant, kind, topic) {
    const decoder = new TextDecoder();
    try {
        const msg = JSON.parse(decoder.decode(payload));
        if (msg.type === "chat") {
            appendTranscript(participant?.name || "Unknown", msg.message);
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
        }
    }
}

// ── UI helpers ───────────────────────────────────────────────────

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

function updateGridLayout() {
    const grid = document.getElementById("video-grid");
    const count = grid.children.length;
    grid.classList.remove("cols-1", "cols-2", "cols-3");
    if (count <= 1) {
        grid.classList.add("cols-1");
    } else if (count <= 3) {
        grid.classList.add("cols-2");
    } else {
        grid.classList.add("cols-3");
    }
}

function addLocalVideoTile() {
    const grid = document.getElementById("video-grid");
    const tile = document.createElement("div");
    tile.className = "participant-tile";
    tile.id = "tile-local";
    tile.innerHTML =
        '<div id="media-local" class="w-full h-full min-h-[200px] rounded-xl overflow-hidden bg-studio-card"></div>' +
        '<div class="participant-name">' + (room.localParticipant.name || "You") + '</div>';
    grid.appendChild(tile);

    // Attach local video
    room.localParticipant.videoTrackPublications.forEach((pub) => {
        if (pub.track) {
            const el = pub.track.attach();
            el.style.width = "100%";
            el.style.height = "100%";
            el.style.objectFit = "cover";
            el.style.transform = "scaleX(-1)";
            document.getElementById("media-local").appendChild(el);
        }
    });
}

function addParticipantTile(participant) {
    if (document.getElementById("tile-" + participant.identity)) return;

    const grid = document.getElementById("video-grid");
    const tile = document.createElement("div");
    tile.className = "participant-tile";
    tile.id = "tile-" + participant.identity;
    tile.innerHTML =
        '<div id="media-' + participant.identity + '" class="w-full h-full min-h-[200px] rounded-xl overflow-hidden bg-studio-card"></div>' +
        '<div class="participant-name">' + (participant.name || participant.identity) + '</div>';
    grid.appendChild(tile);
}

function appendTranscript(speaker, text) {
    const box = document.getElementById("transcript-box");
    // Remove placeholder
    const placeholder = box.querySelector(".italic");
    if (placeholder) placeholder.remove();

    const entry = document.createElement("div");
    entry.className = "transcript-entry";
    entry.innerHTML = '<span class="text-studio-accent-light font-medium text-xs">' + speaker + '</span><br/><span class="text-gray-300 text-sm leading-relaxed">' + text + '</span>';
    box.appendChild(entry);
    box.scrollTop = box.scrollHeight;

    transcriptCount++;
    const counter = document.getElementById("transcript-count");
    if (counter) {
        counter.textContent = transcriptCount + (transcriptCount === 1 ? " entry" : " entries");
    }
}

// ── Control buttons ──────────────────────────────────────────────

async function toggleMic() {
    if (!room) return;
    micEnabled = !micEnabled;
    await room.localParticipant.setMicrophoneEnabled(micEnabled);
    const btn = document.getElementById("btn-mic");
    const label = btn.querySelector("span");
    if (micEnabled) {
        btn.classList.remove("muted");
        btn.classList.add("active");
        label.textContent = "Mic";
    } else {
        btn.classList.remove("active");
        btn.classList.add("muted");
        label.textContent = "Muted";
    }
}

async function toggleCam() {
    if (!room) return;
    camEnabled = !camEnabled;
    await room.localParticipant.setCameraEnabled(camEnabled);
    const btn = document.getElementById("btn-cam");
    const label = btn.querySelector("span");
    if (camEnabled) {
        btn.classList.remove("muted");
        btn.classList.add("active");
        label.textContent = "Cam";
    } else {
        btn.classList.remove("active");
        btn.classList.add("muted");
        label.textContent = "Cam Off";
    }
}

async function askAI() {
    if (!room) return;
    const encoder = new TextEncoder();
    const data = encoder.encode(JSON.stringify({ type: "ask-ai", message: "Please respond to the conversation." }));
    await room.localParticipant.publishData(data, { reliable: true, topic: "ai-control" });
}

async function sendChat() {
    const input = document.getElementById("chat-input");
    const msg = input.value.trim();
    if (!msg || !room) return;

    const encoder = new TextEncoder();
    const data = encoder.encode(JSON.stringify({ type: "chat", message: msg }));
    await room.localParticipant.publishData(data, { reliable: true, topic: "chat-messages" });

    appendTranscript("You", msg);
    input.value = "";
}

function leaveRoom() {
    if (aiVisualizerRAF) cancelAnimationFrame(aiVisualizerRAF);
    if (room) room.disconnect();
    window.location.href = "/";
}

// ── Screen sharing ──────────────────────────────────────────────

async function toggleScreenShare() {
    if (!room) return;
    screenShareEnabled = !screenShareEnabled;
    const btn = document.getElementById("btn-screen");
    const label = btn.querySelector("span");

    try {
        await room.localParticipant.setScreenShareEnabled(screenShareEnabled);
        if (screenShareEnabled) {
            btn.classList.remove("btn-surface");
            btn.classList.add("active", "btn-surface");
            btn.style.background = "rgba(99,102,241,0.15)";
            btn.style.borderColor = "rgba(99,102,241,0.4)";
            label.textContent = "Stop Share";
        } else {
            btn.style.background = "";
            btn.style.borderColor = "";
            label.textContent = "Screen";
        }
    } catch (err) {
        // User cancelled the screen share picker
        screenShareEnabled = false;
        btn.style.background = "";
        btn.style.borderColor = "";
        label.textContent = "Screen";
    }
}

// ── Audio visualizer for AI co-host (Web Audio API) ─────────────

function setupAIAudioVisualizer(audioElement) {
    try {
        if (!aiAudioContext) {
            aiAudioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
        const source = aiAudioContext.createMediaElementSource(audioElement);
        aiAnalyser = aiAudioContext.createAnalyser();
        aiAnalyser.fftSize = 64;
        aiAnalyser.smoothingTimeConstant = 0.75;
        source.connect(aiAnalyser);
        aiAnalyser.connect(aiAudioContext.destination);
        renderAIVisualizer();
    } catch (err) {
        // Fallback: use CSS animation if Web Audio API fails
    }
}

function renderAIVisualizer() {
    if (!aiAnalyser) return;

    const bars = document.querySelectorAll("#ai-audio-bars .audio-bar");
    const dataArray = new Uint8Array(aiAnalyser.frequencyBinCount);

    function draw() {
        aiVisualizerRAF = requestAnimationFrame(draw);
        aiAnalyser.getByteFrequencyData(dataArray);

        const barCount = bars.length;
        // Map frequency bins to bar heights
        const step = Math.floor(dataArray.length / barCount);
        for (let i = 0; i < barCount; i++) {
            const value = dataArray[i * step] || 0;
            const height = Math.max(3, (value / 255) * 28);
            bars[i].style.height = height + "px";
        }
    }
    draw();
}

// ── Connection quality indicator ────────────────────────────────

function onConnectionQualityChanged(quality, participant) {
    // Add/update quality indicator on participant tile
    const tileId = participant.identity === room.localParticipant.identity
        ? "tile-local"
        : "tile-" + participant.identity;
    const tile = document.getElementById(tileId);
    if (!tile) return;

    let indicator = tile.querySelector(".conn-quality");
    if (!indicator) {
        indicator = document.createElement("div");
        indicator.className = "conn-quality";
        tile.appendChild(indicator);
    }

    // quality: ConnectionQuality.Excellent (3), Good (2), Poor (1), Lost (0)
    const level = quality === ConnectionQuality.Excellent ? 3
        : quality === ConnectionQuality.Good ? 2
        : quality === ConnectionQuality.Poor ? 1
        : 0;

    const heights = [6, 10, 14];
    indicator.innerHTML = heights.map(function(h, i) {
        let cls = "conn-bar";
        if (i < level) {
            cls += level >= 2 ? " active" : level === 1 ? " warn" : " poor";
        }
        return '<div class="' + cls + '" style="height:' + h + 'px;"></div>';
    }).join("");
}

// ── Initialize ───────────────────────────────────────────────────
connectToRoom();
