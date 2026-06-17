"""
ui/dashboard.py — Live terminal dashboard for JARVIS.

Hooks into the event bus and renders a real-time Rich TUI showing:
  • Current state (idle / listening / thinking / speaking)
  • Wake word confidence score (live bar)
  • Last transcript
  • Last JARVIS response
  • Recent activity log
"""

import threading
import time
from collections import deque
from datetime import datetime

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text

from core.events import Event, bus

# ─────────────────────────────────────────────────────────────────────────────
# State shared between event handlers and renderer
# ─────────────────────────────────────────────────────────────────────────────

_STATE_COLORS = {
    "IDLE":       "cyan",
    "WAKE":       "bold yellow",
    "LISTENING":  "bold green",
    "THINKING":   "bold magenta",
    "SPEAKING":   "bold blue",
}

_STATE_ICONS = {
    "IDLE":       "💤",
    "WAKE":       "👂",
    "LISTENING":  "🎙️ ",
    "THINKING":   "🧠",
    "SPEAKING":   "🔊",
}

class _DashState:
    def __init__(self):
        self.lock = threading.Lock()
        self.state: str = "IDLE"
        self.wake_score: float = 0.0
        self.last_transcript: str = "—"
        self.last_response: str = "—"
        self.log: deque[tuple[str, str, str]] = deque(maxlen=20)  # (time, level, msg)

    def set_state(self, state: str):
        with self.lock:
            self.state = state

    def set_wake_score(self, score: float):
        with self.lock:
            self.wake_score = score

    def add_log(self, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.log.append((ts, level, msg))

    def snapshot(self):
        with self.lock:
            return (
                self.state,
                self.wake_score,
                self.last_transcript,
                self.last_response,
                list(self.log),
            )


_state = _DashState()


# ─────────────────────────────────────────────────────────────────────────────
# Event handlers
# ─────────────────────────────────────────────────────────────────────────────

def _on_wake(_data):
    _state.set_state("LISTENING")
    _state.add_log("WAKE", "Wake word detected — capturing command…")

def _on_transcript(text: str):
    _state.last_transcript = text or "—"
    _state.set_state("THINKING")
    _state.add_log("STT", f"You said: {text}")

def _on_response(text: str):
    _state.last_response = text or "—"
    _state.set_state("SPEAKING")
    _state.add_log("JARVIS", f"{text}")
    # Schedule return to IDLE after a few seconds
    def _reset():
        time.sleep(4)
        _state.set_state("IDLE")
    threading.Thread(target=_reset, daemon=True).start()

def _on_tts_interrupt(_data):
    pass

def _on_context_changed(data):
    if isinstance(data, dict) and "wake_score" in data:
        _state.set_wake_score(data["wake_score"])

def _on_tool_executed(data):
    if isinstance(data, dict):
        tool = data.get("tool", "unknown")
        _state.add_log("TOOL", f"Executed: {tool}")


def register_handlers():
    """Subscribe dashboard to the event bus. Call once before starting threads."""
    bus.subscribe(Event.WAKE_DETECTED,    _on_wake)
    bus.subscribe(Event.TRANSCRIPT_READY, _on_transcript)
    bus.subscribe(Event.AGENT_RESPONSE,   _on_response)
    bus.subscribe(Event.TTS_INTERRUPT,    _on_tts_interrupt)
    bus.subscribe(Event.CONTEXT_CHANGED,  _on_context_changed)
    bus.subscribe(Event.TOOL_EXECUTED,    _on_tool_executed)


# ─────────────────────────────────────────────────────────────────────────────
# Renderer
# ─────────────────────────────────────────────────────────────────────────────

_LEVEL_COLORS = {
    "WAKE":   "bold yellow",
    "STT":    "bold green",
    "JARVIS": "bold cyan",
    "TOOL":   "bold magenta",
    "INFO":   "dim white",
}


def _build_layout(state, wake_score, transcript, response, logs) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header",  size=3),
        Layout(name="main",    ratio=1),
        Layout(name="footer",  size=3),
    )
    layout["main"].split_row(
        Layout(name="left",  ratio=2),
        Layout(name="right", ratio=3),
    )

    # ── Header ──────────────────────────────────────────────────────────────
    color = _STATE_COLORS.get(state, "white")
    icon  = _STATE_ICONS.get(state, "❓")
    header_text = Text(justify="center")
    header_text.append("  J.A.R.V.I.S  ", style="bold white on #1a1a2e")
    header_text.append(f"   {icon} {state}   ", style=f"bold {color} on #16213e")
    layout["header"].update(Panel(header_text, style="bright_black"))

    # ── Left: status cards ───────────────────────────────────────────────────
    # Wake-word score bar
    bar_filled = int(wake_score * 20)
    bar_empty  = 20 - bar_filled
    bar_color  = "bold green" if wake_score > 0.7 else ("yellow" if wake_score > 0.4 else "dim white")
    bar = Text()
    bar.append("▓" * bar_filled, style=bar_color)
    bar.append("░" * bar_empty,  style="dim")
    bar.append(f"  {wake_score:.2f}", style=bar_color)

    status_table = Table.grid(padding=(0, 1))
    status_table.add_column(style="dim cyan", width=14)
    status_table.add_column()
    status_table.add_row("Wake score", bar)
    status_table.add_row("State",      Text(f"{icon} {state}", style=f"bold {color}"))
    status_table.add_row("", "")
    status_table.add_row("You said",   Text(transcript, style="italic white"))
    status_table.add_row("", "")
    status_table.add_row("JARVIS",     Text(response, style="bold cyan"))

    layout["left"].update(Panel(status_table, title="[bold]Status[/bold]", border_style="bright_black"))

    # ── Right: activity log ──────────────────────────────────────────────────
    log_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    log_table.add_column(style="dim", width=8)
    log_table.add_column(width=7)
    log_table.add_column(ratio=1)

    for ts, level, msg in reversed(logs):
        lc = _LEVEL_COLORS.get(level, "dim white")
        log_table.add_row(ts, Text(f"[{level}]", style=lc), msg)

    layout["right"].update(Panel(log_table, title="[bold]Activity Log[/bold]", border_style="bright_black"))

    # ── Footer ───────────────────────────────────────────────────────────────
    footer = Text(justify="center")
    footer.append("Say ", style="dim")
    footer.append('"Hey Mycroft"', style="bold yellow")
    footer.append(" to wake  •  ", style="dim")
    footer.append("Ctrl+C", style="bold red")
    footer.append(" to quit", style="dim")
    layout["footer"].update(Panel(footer, style="bright_black"))

    return layout


class Dashboard:
    """Run the live dashboard. Call `start()` from orchestrator, `stop()` to clean up."""

    def __init__(self, refresh_per_second: int = 10):
        self._refresh = refresh_per_second
        self._live: Live | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def _run(self):
        console = Console()
        with Live(console=console, refresh_per_second=self._refresh, screen=True) as live:
            self._live = live
            while not self._stop.is_set():
                snap = _state.snapshot()
                live.update(_build_layout(*snap))
                time.sleep(1 / self._refresh)

    def start(self):
        register_handlers()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
