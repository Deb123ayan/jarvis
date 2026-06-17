# JARVIS — Advanced Personal AI System
## Product Requirements Document · Tech Stack · Execution Flow

> **Philosophy:** Build for yourself first. No compromises for compatibility, no cloud dependencies, no subscription gates. Every decision optimizes for one user on one machine — and that is its strength.

---

## Table of Contents

1. [Vision](#1-vision)
2. [System Overview](#2-system-overview)
3. [Core Requirements](#3-core-requirements)
4. [Tech Stack](#4-tech-stack)
5. [Architecture](#5-architecture)
6. [Module Specifications](#6-module-specifications)
7. [Execution Flow](#7-execution-flow)
8. [Data Models](#8-data-models)
9. [Plugin System](#9-plugin-system)
10. [Security Model](#10-security-model)
11. [Build Phases](#11-build-phases)
12. [Performance Targets](#12-performance-targets)

---

## 1. Vision

JARVIS is a **fully local, ambient intelligence system** that runs permanently on a personal Windows machine. It listens, observes, remembers, reasons, and acts — with or without explicit commands.

It is not a voice assistant wrapper around a cloud API. It is a personal operating layer that integrates deeply with the OS, learns continuously from interaction, and grows more capable over time through a plugin architecture that anyone can extend.

**The north star:** JARVIS should feel like working alongside an intelligent entity that knows you, your work, your preferences, and your context — not a tool you prompt.

---

## 2. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        JARVIS CORE                              │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  PERCEPTION  │    │ INTELLIGENCE │    │     ACTION       │  │
│  │              │    │              │    │                  │  │
│  │ Wake Word    │───▶│ Fast Model   │───▶│ Tool Registry    │  │
│  │ STT          │    │ (Qwen2.5 3B) │    │ Plugin Executor  │  │
│  │ Screen Watch │    │ Deep Model   │    │ OS Integration   │  │
│  │ Audio Class  │    │ (72B/22B)    │    │ Browser Control  │  │
│  │ Process Mon  │    │ ReAct Loop   │    │ Shell Runner     │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│          │                  │                      │            │
│          └──────────────────┼──────────────────────┘            │
│                             │                                   │
│                    ┌────────▼────────┐                          │
│                    │    MEMORY       │                          │
│                    │                 │                          │
│                    │ Working (RAM)   │                          │
│                    │ Episodic(SQLite)│                          │
│                    │ Semantic(Chroma)│                          │
│                    │ Graph (NetworkX)│                          │
│                    └─────────────────┘                          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  AMBIENT LOOP  (background, always running)              │   │
│  │  Context Monitor → Proactive Reasoner → Action Trigger   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Requirements

### 3.1 Non-Negotiable Constraints

| Constraint | Requirement |
|---|---|
| Privacy | Zero network egress for any personal data. All inference local. |
| Availability | Runs as background Windows service, auto-starts on boot |
| Reliability | Single tool failure must never crash the pipeline |
| Latency | First spoken word within 3 seconds of wake word on GPU hardware |
| Persistence | All memory survives restart. State is never lost |
| Extensibility | New capability = drop a `.py` file in `/plugins/`. No other change required |

### 3.2 Functional Requirements

**Perception**
- Detect wake word with < 1% false positive rate using a voice-trained model
- Transcribe speech to text with > 95% accuracy for clear speech
- Classify currently active application and window context
- Optionally capture and interpret screen content via vision model
- Detect audio events (phone ringing, alarm, silence) without transcribing everything

**Intelligence**
- Route requests between fast (3B) and deep (72B) model automatically
- Execute multi-step agentic tasks without hand-holding
- Self-correct when a tool fails — try alternative approaches
- Extract and store memories automatically from every conversation
- Reason over stored knowledge graph to answer complex personal questions

**Action**
- Control every aspect of the OS: files, apps, windows, volume, power
- Automate browser interactions (navigate, click, fill, scrape)
- Send/read email, manage calendar events
- Run arbitrary shell commands (with confirmation gate)
- Schedule tasks for future execution
- Proactively act without a voice command when context warrants it

**Memory**
- Remember facts, preferences, people, and events across all sessions
- Surface relevant memories automatically before the LLM reasons
- Forget on demand
- Build and query a personal knowledge graph

---

## 4. Tech Stack

### 4.1 Complete Stack Reference

| Layer | Component | Technology | Version | Rationale |
|---|---|---|---|---|
| **Wake Word** | Detector | OpenWakeWord | 0.6.0 | Local, CPU-efficient, trainable on your voice |
| **STT** | Transcriber | faster-whisper | 1.0.3 | 4x faster than Whisper, built-in VAD, GPU accelerated |
| **STT Model** | — | whisper `small.en` | — | Better accuracy than `tiny.en`, still fast on GPU |
| **TTS** | Synthesizer | Kokoro ONNX | latest | Natural voice, fully offline, runs fast on CPU |
| **Fast LLM** | Inference | OpenRouter API (Llama 3.3 70B) | latest | Cloud inference for fast response |
| **Deep LLM** | Inference | OpenRouter API (DeepSeek Chat) | latest | Complex reasoning, planning, memory synthesis |
| **Vision** | Screen understanding | OpenRouter API (Vision-capable model) | latest | Multimodal, good instruction following |
| **Memory: Working** | In-session | Python dict + deque | stdlib | Zero latency, no persistence needed |
| **Memory: Episodic** | Events log | SQLite + FTS5 | stdlib | Zero-dependency full-text search, instant startup |
| **Memory: Semantic** | Fact storage | ChromaDB | 0.5.3 | Local vector DB, semantic recall |
| **Embedder** | Vectorization | sentence-transformers `all-MiniLM-L6-v2` | 3.0.1 | 384-dim, fast, runs on CPU |
| **Knowledge Graph** | Personal graph | NetworkX | 3.x | In-memory graph, serialized to JSON, no server needed |
| **Browser** | Automation | Playwright | 1.44.0 | Reliable, supports all modern browsers |
| **OS Integration** | Windows control | pywinauto + psutil + ctypes | latest | Deep Windows API access |
| **Audio Control** | Volume/devices | pycaw | latest | Reliable Windows audio via COM |
| **System Tray** | UI | pystray + Pillow | latest | Lightweight, no GUI framework needed |
| **Scheduler** | Task timing | APScheduler | 3.10.x | Cron + interval + one-shot scheduling, persistent |
| **HTTP API** | Remote access | FastAPI + Uvicorn | latest | Optional, for phone/remote control |
| **Tunnel** | Remote networking | Tailscale | latest | No open ports, no public exposure |
| **Config** | Settings | PyYAML | 6.x | Human-readable, hot-reloadable |
| **Logging** | Observability | Loguru | 0.7.x | Structured logs, rotation, color terminal output |

### 4.2 Model Selection Guide

```
Your GPU VRAM    Fast Model         Deep Model            Vision
─────────────    ──────────         ──────────            ──────
4 GB             qwen2.5:3b         qwen2.5:7b-q4         moondream (2B)
6 GB             qwen2.5:3b         qwen2.5:14b-q4        qwen2-vl:3b
8 GB             qwen2.5:3b         qwen2.5:32b-q4        qwen2-vl:7b
12 GB+           qwen2.5:7b         qwen2.5:72b-q4        qwen2-vl:7b
24 GB+           qwen2.5:7b         qwen2.5:72b-q6        qwen2-vl:7b
```

### 4.3 Full requirements.txt

```
# Audio pipeline
pyaudio==0.2.14
sounddevice==0.4.6
openwakeword==0.6.0
faster-whisper==1.0.3
kokoro-onnx

# LLM / inference
httpx==0.27.0

# Memory
sentence-transformers==3.0.1
chromadb==0.5.3
networkx==3.3

# OS integration
pycaw==20240210
pywinauto==0.6.8
psutil==5.9.8
pywin32==306
pyperclip==1.8.2
pyautogui==0.9.54
send2trash==1.8.3
mss==9.0.1

# Browser & media
playwright==1.44.0
beautifulsoup4==4.12.3
yt-dlp==2024.5.27
Pillow==10.3.0

# Scheduling & UI
APScheduler==3.10.4
pystray==0.19.5

# API server (optional)
fastapi==0.111.0
uvicorn==0.29.0

# Utilities
pyyaml==6.0.1
loguru==0.7.2
aiofiles==23.2.1
```

---

## 5. Architecture

### 5.1 Thread Model

```
┌─────────────────────────────────────────────┐
│              Process: jarvis.py             │
│                                             │
│  Thread 1:  WakeWordListener                │
│             └── always running              │
│             └── fires: wake_event           │
│                                             │
│  Thread 2:  VoicePipeline                   │
│             └── wakes on: wake_event        │
│             └── runs: STT → Agent → TTS     │
│                                             │
│  Thread 3:  TTSWorker                       │
│             └── drains: tts_queue           │
│             └── handles: interruptions      │
│                                             │
│  Thread 4:  AmbientLoop                     │
│             └── always running              │
│             └── interval: 60s               │
│             └── proactive intelligence      │
│                                             │
│  Thread 5:  ContextMonitor                  │
│             └── always running              │
│             └── watches: active window,     │
│                          processes, screen  │
│                                             │
│  Thread 6:  SchedulerWorker                 │
│             └── APScheduler job store       │
│             └── fires scheduled tasks       │
│                                             │
│  Thread 7:  TrayIcon                        │
│             └── pystray event loop          │
│             └── right-click menu, status    │
└─────────────────────────────────────────────┘
```

### 5.2 Event Bus

All inter-thread communication goes through a central event bus — no direct thread coupling:

```python
# core/events.py
from enum import Enum
import queue

class Event(Enum):
    WAKE_DETECTED       = "wake_detected"
    AUDIO_CAPTURED      = "audio_captured"
    TRANSCRIPT_READY    = "transcript_ready"
    AGENT_RESPONSE      = "agent_response"
    TTS_ENQUEUE         = "tts_enqueue"
    TTS_INTERRUPT       = "tts_interrupt"
    CONTEXT_CHANGED     = "context_changed"
    MEMORY_UPDATED      = "memory_updated"
    PLUGIN_LOADED       = "plugin_loaded"
    TOOL_EXECUTED       = "tool_executed"

class EventBus:
    def __init__(self):
        self._subscribers: dict[Event, list[callable]] = {}
    
    def subscribe(self, event: Event, handler: callable):
        self._subscribers.setdefault(event, []).append(handler)
    
    def publish(self, event: Event, data=None):
        for handler in self._subscribers.get(event, []):
            handler(data)

bus = EventBus()  # singleton
```

---

## 6. Module Specifications

### 6.1 Wake Word (`wake_word/listener.py`)

- Model: train custom OpenWakeWord model on 200+ personal voice samples
- Fallback: `hey_mycroft` pre-trained (more reliable than `hey_jarvis` out of box)
- Ring buffer: maintain a 2-second rolling audio buffer at all times
- On detection: pass ring buffer contents immediately to STT — eliminates capture latency
- Cooldown: 2 seconds after detection before re-arming
- False positive gate: require detection score > 0.7 for 3 consecutive frames

### 6.2 STT (`stt/transcriber.py`)

- Model: `small.en` (better accuracy than `tiny.en`, negligible speed difference on GPU)
- VAD: use faster-whisper's built-in VAD filter — remove `webrtcvad` dependency entirely
- Confidence gate: discard transcripts with mean log-probability < -0.6
- Post-processing: strip filler words ("um", "uh", "like") before sending to LLM
- Language detection: optional, enable if switching languages

```python
model = WhisperModel("small.en", device="cuda", compute_type="float16")
segments, info = model.transcribe(
    audio,
    language="en",
    beam_size=1,
    vad_filter=True,
    vad_parameters={"min_silence_duration_ms": 600, "threshold": 0.5}
)
```

### 6.3 LLM Client (`llm/client.py`)

Two-model routing system:

```python
FAST_MODEL = "meta-llama/llama-3.3-70b-instruct"
DEEP_MODEL = "deepseek/deepseek-chat"

DEEP_TRIGGERS = [
    "plan", "analyze", "summarize", "write", "explain", "compare",
    "research", "remember everything", "think about"
]

def route(transcript: str) -> str:
    if any(t in transcript.lower() for t in DEEP_TRIGGERS):
        return DEEP_MODEL
    if len(transcript.split()) > 30:
        return DEEP_MODEL
    return FAST_MODEL
```

**Forced JSON output** for tool calls — uses a strong system prompt to enforce JSON tool calls:

```python
with httpx.stream(
    "POST",
    "https://openrouter.ai/api/v1/chat/completions",
    headers={"Authorization": f"Bearer {current_api_key}"},
    json={
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.1,
    },
    timeout=45.0,
) as response:
```

### 6.4 Agent Loop (`agent/loop.py`)

ReAct pattern — Reason, Act, Observe, repeat:

```python
class AgentLoop:
    MAX_STEPS = 10
    
    async def run(self, goal: str, context: Context) -> AgentResult:
        scratchpad: list[tuple[Action, Observation]] = []
        memory_context = await memory.recall_relevant(goal)
        
        for step in range(self.MAX_STEPS):
            # Reason
            action = await self.llm.reason(
                goal=goal,
                scratchpad=scratchpad,
                memory=memory_context,
                context=context,
                tools=registry.get_schema()
            )
            
            # Terminal conditions
            if action.type == ActionType.DONE:
                await self._extract_memories(goal, scratchpad, action.response)
                return AgentResult(response=action.response, steps=len(scratchpad))
            
            if action.type == ActionType.CLARIFY:
                return AgentResult(response=action.question, needs_clarification=True)
            
            # Act
            observation = await registry.execute(action.tool, action.args)
            scratchpad.append((action, observation))
            
            # Self-correction: if tool failed, tell the model and continue
            if observation.is_error:
                scratchpad[-1] = (action, Observation(
                    content=f"Tool failed: {observation.error}. Try a different approach.",
                    is_error=True
                ))
        
        return AgentResult(response="I couldn't complete that task in time.", partial=True)
    
    async def _extract_memories(self, goal, scratchpad, response):
        # Async, non-blocking — runs after response is spoken
        asyncio.create_task(memory.auto_extract(goal, scratchpad, response))
```

### 6.5 Memory System (`memory/`)

**Three-tier architecture:**

```python
# memory/working.py — in-session context
class WorkingMemory:
    def __init__(self, max_turns=12):
        self.history: deque = deque(maxlen=max_turns)
        self.active_task: str = None
        self.context_snapshot: dict = {}
    
    # Every 12 turns, compress history to a summary
    async def maybe_compress(self, llm):
        if len(self.history) == self.history.maxlen:
            summary = await llm.summarize(list(self.history))
            self.history.clear()
            self.history.appendleft({"role": "system", "content": f"[Prior conversation summary]: {summary}"})
```

```python
# memory/episodic.py — events across sessions (SQLite FTS5)
CREATE VIRTUAL TABLE events USING fts5(
    timestamp,
    event_type,      -- "conversation", "task_completed", "error", "observation"
    summary,
    tags,
    tokenize="porter unicode61"
);

# Query: "what did I ask about last Tuesday?"
SELECT * FROM events 
WHERE events MATCH 'deploy server'
AND timestamp > datetime('now', '-7 days')
ORDER BY rank;
```

```python
# memory/semantic.py — facts and preferences (ChromaDB)
# Lazy load — only initialize on first memory operation
class SemanticMemory:
    _client = None
    
    @property
    def client(self):
        if not self._client:
            self._client = chromadb.PersistentClient(path="memory/chroma")
        return self._client
    
    async def auto_extract(self, conversation: list) -> int:
        """Called after every conversation. Extracts memorable facts silently."""
        extracted = await llm.json(EXTRACT_MEMORIES_PROMPT, conversation)
        stored = 0
        for fact in extracted:
            if fact["confidence"] > 0.8:
                await self.store(fact["text"], metadata=fact)
                stored += 1
        return stored
```

```python
# memory/graph.py — personal knowledge graph (NetworkX)
import networkx as nx
import json

class KnowledgeGraph:
    def __init__(self):
        self.G = nx.DiGraph()
        self._load()
    
    def add_fact(self, subject: str, relation: str, obj: str, **attrs):
        self.G.add_edge(subject.lower(), obj.lower(), 
                       relation=relation, **attrs)
        self._save()
    
    def query(self, subject: str, relation: str = None) -> list:
        neighbors = list(self.G.successors(subject.lower()))
        if relation:
            return [n for n in neighbors 
                    if self.G[subject.lower()][n].get("relation") == relation]
        return neighbors
    
    def find_path(self, source: str, target: str) -> list:
        try:
            return nx.shortest_path(self.G, source.lower(), target.lower())
        except nx.NetworkXNoPath:
            return []
    
    def _save(self):
        data = nx.node_link_data(self.G)
        with open("memory/graph.json", "w") as f:
            json.dump(data, f)
    
    def _load(self):
        try:
            with open("memory/graph.json") as f:
                data = json.load(f)
            self.G = nx.node_link_graph(data)
        except FileNotFoundError:
            pass
```

### 6.6 TTS (`tts/`)

**Kokoro ONNX with streaming + interruption support:**

```python
from kokoro_onnx import Kokoro
import sounddevice as sd
import numpy as np

class TTSEngine:
    def __init__(self):
        self.kokoro = Kokoro("kokoro-v1.0.onnx", "voices.bin")
        self.voice = "af_heart"
        self._stream = None
        self._stop_flag = threading.Event()
    
    def speak(self, text: str):
        # Strip LLM filler before speaking
        text = self._clean(text)
        # Generate audio
        samples, sr = self.kokoro.create(text, voice=self.voice, speed=1.0)
        self._stop_flag.clear()
        self._play(samples, sr)
    
    def interrupt(self):
        """Stop speaking immediately — called when wake word detected during speech."""
        self._stop_flag.set()
        if self._stream:
            self._stream.stop()
    
    def _clean(self, text: str) -> str:
        STRIP = ["Certainly!", "Of course!", "Sure thing!", "Great question!",
                 "Absolutely!", "I'd be happy to", "As an AI"]
        for phrase in STRIP:
            text = text.replace(phrase, "")
        return text.strip()
    
    # Streaming: speak sentence by sentence as LLM generates
    async def speak_stream(self, token_generator):
        buffer = ""
        async for token in token_generator:
            buffer += token
            if buffer.endswith((".", "?", "!", ":", "\n")):
                sentence = buffer.strip()
                if len(sentence) > 4:
                    await tts_queue.put(sentence)
                buffer = ""
        if buffer.strip():
            await tts_queue.put(buffer.strip())
```

### 6.7 Context Monitor (`perception/context.py`)

```python
import win32gui, psutil, mss
from dataclasses import dataclass

@dataclass
class SystemContext:
    active_app: str
    window_title: str
    active_pid: int
    open_windows: list[str]
    cpu_percent: float
    memory_percent: float
    time_of_day: str        # "morning" / "afternoon" / "evening" / "night"
    clipboard_preview: str  # first 100 chars only
    screen_hash: str        # hash of screen — detect when content changes

class ContextMonitor:
    def __init__(self, interval=5.0):
        self.interval = interval
        self._last_context = None
    
    def get_context(self) -> SystemContext:
        hwnd = win32gui.GetForegroundWindow()
        return SystemContext(
            active_app=self._get_app_name(hwnd),
            window_title=win32gui.GetWindowText(hwnd),
            active_pid=self._get_pid(hwnd),
            open_windows=self._get_open_windows(),
            cpu_percent=psutil.cpu_percent(interval=0.1),
            memory_percent=psutil.virtual_memory().percent,
            time_of_day=self._time_bucket(),
            clipboard_preview=self._safe_clipboard(),
            screen_hash=self._screen_hash()
        )
    
    def run(self):
        while True:
            ctx = self.get_context()
            if ctx != self._last_context:
                bus.publish(Event.CONTEXT_CHANGED, ctx)
                self._last_context = ctx
            time.sleep(self.interval)
```

### 6.8 Ambient Loop (`agent/ambient.py`)

```python
class AmbientLoop:
    """Proactive intelligence — acts without being asked."""
    
    INTERVAL = 60  # seconds between checks
    
    async def run(self):
        while True:
            await asyncio.sleep(self.INTERVAL)
            await self.tick()
    
    async def tick(self):
        context = context_monitor.get_context()
        pending = await memory.get_pending_reminders()
        recent_activity = await episodic.last(minutes=30)
        
        prompt = f"""
You are JARVIS running a background check. Current context:
- Active app: {context.active_app}
- Window: {context.window_title}
- Time: {context.time_of_day}
- Pending reminders: {pending}
- Recent activity summary: {recent_activity}

Should JARVIS proactively say or do anything right now?
Respond ONLY with JSON: {{"act": true/false, "action": "speak|tool", "content": "..."}}
Default is act=false. Only act if genuinely useful. Never act just to seem active.
"""
        result = await fast_llm.json(prompt)
        
        if result.get("act"):
            if result["action"] == "speak":
                await tts_queue.put(result["content"])
            elif result["action"] == "tool":
                await agent.run(result["content"], context)
```

---

## 7. Execution Flow

### 7.1 Normal Voice Command Flow

```
[Mic] ──continuous──▶ [WakeWordListener]
                            │
                     score > 0.7 (3 frames)
                            │
                            ▼
                     [Fire wake_event]
                     [Pass ring buffer to STT]
                     [Play chime]
                            │
                            ▼
                    [STT: faster-whisper]
                     VAD trim + transcribe
                            │
                     confidence > 0.6?
                     ├─ NO ──▶ discard, re-arm
                     └─ YES ──▶
                            │
                            ▼
                    [Router: fast or deep model?]
                            │
                    ┌───────┴───────┐
               fast (3B)       deep (72B)
                    └───────┬───────┘
                            │
                            ▼
                  [Build prompt]
                  system prompt
                  + memory recall (top-5 relevant facts)
                  + knowledge graph context
                  + conversation history (compressed)
                  + current context snapshot
                  + tool schema (JSON)
                            │
                            ▼
                  [AgentLoop.run(goal)]
                            │
                    ┌───────▼──────────┐
                    │  REACT ITERATION  │
                    │                  │
                    │ Reason ──────────┤
                    │   ↓              │
                    │ Action type?     │
                    │  DONE ───────────┼──▶ [Final response]
                    │  CLARIFY ────────┼──▶ [Ask user]
                    │  TOOL_CALL ──────┤
                    │   ↓              │
                    │ execute(tool)    │
                    │   ↓              │
                    │ observe result   │
                    │   ↓ (loop)       │
                    │ re-reason        │
                    └──────────────────┘
                            │
                            ▼
                  [Stream response to TTS queue]
                  [Speak sentence by sentence]
                            │
                            ▼ (async, non-blocking)
                  [auto_extract memories]
                  [log to episodic memory]
                  [update knowledge graph if applicable]
                            │
                            ▼
                    [Re-arm wake word]
```

### 7.2 Proactive Action Flow (Ambient Loop)

```
[60s timer fires]
        │
        ▼
[Gather context snapshot]
 active app, window, time, pending reminders, recent activity
        │
        ▼
[fast LLM: should I act?]
        │
    act=false ──▶ [sleep 60s, repeat]
        │
    act=true
        │
        ▼
[action type?]
  speak ──▶ [TTS queue directly]
  tool  ──▶ [AgentLoop.run(content)]
        │
        ▼
[log ambient action to episodic memory]
```

### 7.3 Memory Formation Flow

```
[Conversation ends]
        │
        ▼ (background task, non-blocking)
[auto_extract called with full conversation]
        │
        ▼
[fast LLM with extraction prompt]
Returns JSON array of facts with confidence scores
        │
        ▼
[For each fact where confidence > 0.8]
        │
  ┌─────┴──────┐
  │            │
  ▼            ▼
[Semantic    [Knowledge Graph]
 Memory]      subject/relation/object
 embed        triples extracted
 + store      networkx edge added
```

### 7.4 Plugin Load Flow

```
[Startup OR file dropped in /plugins/]
        │
        ▼
[PluginLoader scans /plugins/*.py]
        │
        ▼
[For each file:]
 importlib.import_module()
 find class inheriting JarvisPlugin
        │
        ▼
[Validate plugin interface]
 name, description, tools present?
        │
  invalid ──▶ [log warning, skip]
        │
  valid
        │
        ▼
[Register plugin.tools into registry]
[Schedule plugin.background_tasks]
[Call plugin.on_load()]
[Publish PLUGIN_LOADED event]
        │
        ▼
[Tool schema regenerated for LLM prompt]
```

### 7.5 Dangerous Tool Confirmation Flow

```
[Agent calls tool in RISK_LEVEL.HIGH or CRITICAL]
        │
        ▼
[Check risk level]
        │
  LOW/MEDIUM ──▶ [Execute immediately]
        │
  HIGH ──────▶ [TTS: "Should I {action}? Say yes to confirm."]
               [Wait 10s for voice confirmation]
               confirmed ──▶ [Execute]
               timeout/no  ──▶ [Cancel, log]
        │
  CRITICAL ──▶ [TTS: "This requires physical confirmation."]
               [Show system tray notification with Yes/No buttons]
               confirmed ──▶ [Execute]
               dismissed   ──▶ [Cancel, log]
```

---

## 8. Data Models

### 8.1 Core Types

```python
# core/types.py

@dataclass
class Action:
    type: ActionType        # TOOL_CALL | DONE | CLARIFY
    tool: str | None
    args: dict
    response: str | None
    reasoning: str          # model's chain of thought (logged, not spoken)

@dataclass
class Observation:
    content: str
    is_error: bool = False
    error: str | None = None
    duration_ms: int = 0

@dataclass
class AgentResult:
    response: str
    steps: int = 0
    tools_used: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    partial: bool = False

@dataclass
class Context:
    active_app: str
    window_title: str
    time_of_day: str
    recent_commands: list[str]
    relevant_memories: list[str]
    graph_context: dict

@dataclass  
class Memory:
    id: str
    text: str
    category: str           # preference | person | fact | task | event
    confidence: float
    created_at: datetime
    last_accessed: datetime
    access_count: int
```

### 8.2 SQLite Schema (Episodic Memory)

```sql
CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,
    started_at  DATETIME,
    ended_at    DATETIME,
    summary     TEXT
);

CREATE VIRTUAL TABLE events USING fts5(
    id,
    session_id,
    timestamp,
    event_type,
    summary,
    tags,
    tokenize="porter unicode61"
);

CREATE TABLE scheduled_tasks (
    id          TEXT PRIMARY KEY,
    description TEXT,
    tool        TEXT,
    args        TEXT,           -- JSON
    schedule    TEXT,           -- cron expression or ISO datetime
    created_at  DATETIME,
    last_run    DATETIME,
    enabled     BOOLEAN DEFAULT 1
);

CREATE TABLE graph_snapshots (
    id          INTEGER PRIMARY KEY,
    snapshot    TEXT,           -- JSON serialized networkx graph
    created_at  DATETIME
);
```

---

## 9. Plugin System

### 9.1 Plugin Interface

```python
# core/plugin_base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class Tool:
    name: str
    description: str        # LLM reads this — write it for an LLM, not a human
    args_schema: dict       # JSON Schema for arguments
    handler: callable
    risk_level: str = "low" # low | medium | high | critical

class JarvisPlugin(ABC):
    name: str                           # unique identifier
    description: str                    # what this plugin does
    version: str = "1.0.0"
    author: str = "local"
    
    @property
    @abstractmethod
    def tools(self) -> list[Tool]:
        """Tools this plugin exposes to the LLM."""
        ...
    
    def background_tasks(self) -> list[callable]:
        """Async coroutines to run continuously in background."""
        return []
    
    def on_load(self):
        """Called when plugin is loaded."""
        pass
    
    def on_unload(self):
        """Called before plugin is removed."""
        pass
    
    def on_context_change(self, context: Context):
        """Called when active app or window changes. Optional."""
        pass
```

### 9.2 Example Plugin Structure

```python
# plugins/spotify.py
class SpotifyPlugin(JarvisPlugin):
    name = "spotify"
    description = "Controls Spotify playback on this machine"
    
    @property
    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="spotify_play",
                description="Play a song, artist, or playlist on Spotify. Use when user wants to listen to music.",
                args_schema={"query": {"type": "string", "description": "song name, artist, or playlist"}},
                handler=self._play,
                risk_level="low"
            ),
            Tool(
                name="spotify_pause",
                description="Pause Spotify playback",
                args_schema={},
                handler=self._pause,
                risk_level="low"
            )
        ]
    
    def _play(self, query: str) -> str:
        # implementation
        ...
```

---

## 10. Security Model

### 10.1 Risk Classification

```python
RISK_LEVELS = {
    "low": [
        "file_read", "file_search", "get_volume", "get_brightness",
        "memory_recall", "clipboard_read", "process_list", "app_list",
        "calendar_read", "note_read", "todo_list", "weather_get"
    ],
    "medium": [
        "file_create", "app_launch", "app_close", "set_volume",
        "clipboard_write", "note_add", "todo_add", "memory_store",
        "browser_navigate", "browser_search"
    ],
    "high": [
        "file_delete", "file_move", "shell_run", "send_email",
        "calendar_create", "power_action", "process_kill",
        "browser_click", "browser_fill", "wifi_control"
    ],
    "critical": [
        "bulk_delete", "bulk_rename", "format_drive",
        "registry_edit", "service_control"
    ]
}
```

### 10.2 Confirmation Gates

| Risk Level | Gate | Timeout |
|---|---|---|
| low | None — execute immediately | — |
| medium | None — execute immediately | — |
| high | Voice confirmation ("say yes to confirm") | 10 seconds |
| critical | Physical confirmation (tray notification) | 30 seconds |

### 10.3 API Security (if enabled)

- All keys stored in environment variables, never in config files
- Constant-time comparison for all key checks (prevents timing attacks)
- Per-key tool scope (mobile key gets read-only subset)
- Rate limiting: 20 requests/minute per key
- Dangerous tools (`shell_run`, `file_delete`) excluded from all remote scopes
- Tailscale only — no public internet exposure

---

## 11. Build Phases

### Phase 1 — Core Pipeline (Week 1)
**Goal:** Wake word → voice → LLM → spoken response. Working end-to-end.

- [ ] Wake word detection with ring buffer pre-capture
- [ ] STT with faster-whisper (small.en, GPU, built-in VAD)
- [ ] Fast model integration (Qwen2.5:3b, forced JSON, streaming)
- [ ] Kokoro TTS with sentence streaming
- [ ] Interruption handling (stop speaking when wake word fires)
- [ ] Basic orchestrator with thread model
- [ ] Config system (PyYAML + hot reload)
- [ ] Loguru structured logging

**Exit criteria:** Say wake word, ask a question, hear a natural response. Second wake word works while TTS is speaking.

---

### Phase 2 — Tool Registry & Core Tools (Week 1-2)
**Goal:** JARVIS executes real actions.

- [ ] Tool registry with risk classification
- [ ] Confirmation gates (voice for high, tray for critical)
- [ ] Filesystem tools (create, read, move, delete, search, organize)
- [ ] System tools (volume, brightness, power, wifi, processes, windows)
- [ ] App control (launch, close, focus)
- [ ] Clipboard tools
- [ ] Shell runner (with confirmation gate)

**Exit criteria:** "Open VS Code", "Set volume to 40", "Delete test.txt" all work correctly.

---

### Phase 3 — Intelligence Layer (Week 2)
**Goal:** ReAct agent loop + two-model routing + proper memory.

- [ ] AgentLoop with self-correction
- [ ] Two-model router (fast/deep decision logic)
- [ ] Working memory with compression
- [ ] Episodic memory (SQLite FTS5)
- [ ] Semantic memory (ChromaDB, lazy load)
- [ ] Knowledge graph (NetworkX)
- [ ] Auto memory extraction (runs async after every conversation)
- [ ] Memory recall injection into LLM prompt

**Exit criteria:** Ask a multi-step question. JARVIS plans and executes multiple tool calls. Tell it your name, close and reopen, ask "what's my name?" — it knows.

---

### Phase 4 — Perception Layer (Week 3)
**Goal:** JARVIS knows what you're doing without being told.

- [ ] Context monitor (active app, window, processes)
- [ ] Context injected into every agent prompt
- [ ] Screen capture on demand (mss)
- [ ] Vision model integration (Qwen2-VL via Ollama)
- [ ] "What am I looking at?" works
- [ ] App-specific context plugins (VS Code → show current file, Chrome → show URL)

**Exit criteria:** Switch to VS Code. Ask "what file am I editing?" JARVIS answers correctly without you mentioning VS Code.

---

### Phase 5 — Ambient Intelligence (Week 3-4)
**Goal:** JARVIS acts without being asked.

- [ ] Ambient loop (60s interval background reasoning)
- [ ] Proactive reminders from episodic memory
- [ ] CPU/memory anomaly detection and notification
- [ ] Calendar-aware morning briefing
- [ ] Tab/window clutter detection
- [ ] Focus session detection (auto-silence non-critical notifications)

**Exit criteria:** Have a meeting in 10 minutes. JARVIS reminds you without being asked. CPU spikes — JARVIS tells you which process is responsible.

---

### Phase 6 — Web, Media & Communication (Week 4)
**Goal:** JARVIS controls the internet.

- [ ] Browser automation (navigate, click, fill forms, scrape)
- [ ] Web search and summarization
- [ ] Email (read, compose, send via SMTP)
- [ ] Calendar management
- [ ] Media control (yt-dlp for download, system media keys)
- [ ] Notes and todos (SQLite backed)

**Exit criteria:** "Search for the latest news on AI and read me the top 3 headlines." Works start to finish.

---

### Phase 7 — Plugin System (Week 5)
**Goal:** New capabilities require zero changes to core.

- [ ] JarvisPlugin base class
- [ ] PluginLoader with hot-reload
- [ ] Tool schema auto-regenerated on plugin load/unload
- [ ] 3 reference plugins: Spotify, system stats, custom shortcuts
- [ ] Plugin error isolation (plugin crash cannot crash JARVIS)

**Exit criteria:** Write a new plugin, drop it in `/plugins/`, say the wake word — new tool available immediately without restarting.

---

### Phase 8 — System Tray & Polish (Week 5-6)
**Goal:** JARVIS lives in the background elegantly.

- [ ] System tray icon with status indicator
- [ ] Right-click menu: mute/unmute, pause ambient loop, open logs, reload plugins
- [ ] Windows startup entry (Task Scheduler or registry)
- [ ] Crash recovery (watchdog restarts the process)
- [ ] Performance profiling — ensure < 3% idle CPU
- [ ] Wake word custom training on your voice

**Exit criteria:** Machine boots. JARVIS is running within 30 seconds. Tray icon visible. All functionality works.

---

### Phase 9 — Remote Access (Optional, Week 6+)
**Goal:** JARVIS accessible from phone on same Tailscale network.

- [ ] FastAPI server (read-only tools only by default)
- [ ] API key auth with scope limitation
- [ ] Rate limiter
- [ ] Tailscale setup
- [ ] Dangerous tools excluded from remote scope

**Exit criteria:** From phone on Tailscale, send a voice note — JARVIS transcribes and responds.

---

## 12. Performance Targets

| Metric | Target | How to Measure |
|---|---|---|
| Wake word latency | < 100ms from detection to chime | Log timestamp delta |
| STT latency | < 400ms for 5-second audio (GPU) | Log transcribe() duration |
| Fast model first token | < 500ms | Log streaming start timestamp |
| Deep model first token | < 2500ms | Log streaming start timestamp |
| TTS first audio | < 200ms per sentence (Kokoro) | Log from enqueue to audio start |
| End-to-end (simple command) | < 3 seconds | Wake word to first spoken word |
| End-to-end (complex task) | < 8 seconds | Wake word to first spoken word |
| Idle CPU usage | < 3% | Task Manager / psutil |
| Idle VRAM usage | < 2GB (fast model loaded) | nvidia-smi |
| Memory recall latency | < 100ms | Log ChromaDB query duration |
| Plugin load time | < 500ms per plugin | Log on_load() duration |

---

## Appendix: Folder Structure

```
jarvis/
├── core/
│   ├── events.py           # Event bus
│   ├── types.py            # Shared dataclasses
│   ├── config.py           # Config loader with hot-reload
│   └── plugin_base.py      # JarvisPlugin ABC
├── wake_word/
│   ├── listener.py
│   └── models/             # .tflite model files
├── stt/
│   └── transcriber.py
├── tts/
│   ├── engine.py           # Kokoro wrapper
│   └── queue_manager.py
├── llm/
│   ├── client.py           # Ollama HTTP client, streaming, routing
│   └── prompt_builder.py
├── agent/
│   ├── loop.py             # ReAct agent loop
│   └── ambient.py          # Ambient background loop
├── perception/
│   ├── context.py          # Active window, process monitor
│   └── screen.py           # mss + vision model
├── memory/
│   ├── working.py
│   ├── episodic.py         # SQLite FTS5
│   ├── semantic.py         # ChromaDB
│   ├── graph.py            # NetworkX knowledge graph
│   └── embedder.py
├── tools/
│   ├── registry.py
│   ├── filesystem.py
│   ├── system.py
│   ├── apps.py
│   ├── shell.py
│   ├── clipboard.py
│   ├── browser.py
│   ├── media.py
│   ├── notes.py
│   ├── web.py
│   ├── email_tool.py
│   └── calendar_tool.py
├── plugins/                # Drop plugins here — auto-loaded
│   └── example_plugin.py
├── api/
│   ├── server.py
│   ├── auth.py
│   └── rate_limiter.py
├── ui/
│   └── tray.py
├── memory/                 # Runtime data (gitignored)
│   ├── jarvis.db           # SQLite
│   ├── chroma/             # ChromaDB
│   └── graph.json          # NetworkX
├── logs/                   # Loguru output (gitignored)
├── orchestrator.py         # Entry point
├── config.yaml
└── requirements.txt
```

---

*Built for one user. Optimized for no one else.*
