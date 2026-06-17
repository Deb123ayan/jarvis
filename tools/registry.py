"""
tools/registry.py — Central tool registry with risk-gated execution.

All tool modules register their Tool instances here at startup.
The registry is passed to the LLM client to inject schema into prompts,
and is called by the agent to dispatch tool calls.
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from loguru import logger
from core.events import bus, Event
from core.types import Observation

# ---------------------------------------------------------------------------
# Risk level definitions (mirrors PRD §10.1)
# ---------------------------------------------------------------------------
RISK_LEVELS = {
    "low": [
        "file_read", "file_search", "dir_list",
        "get_volume", "get_battery",
        "clipboard_read", "app_list",
    ],
    "medium": [
        "file_write", "app_launch", "app_close", "app_focus",
        "set_volume", "clipboard_write",
    ],
    "high": [
        "file_delete", "file_move", "shell_run",
        "kill_process",
    ],
    "critical": [
        "power_action",
    ],
}


# ---------------------------------------------------------------------------
# Tool dataclass (mirrors core/plugin_base.py but lives here for tools pkg)
# ---------------------------------------------------------------------------
@dataclass
class Tool:
    name: str
    description: str          # LLM reads this — write for an LLM, not a human
    args_schema: dict         # JSON Schema for arguments
    handler: Callable
    risk_level: str = "low"   # low | medium | high | critical


# ---------------------------------------------------------------------------
# Confirmation gate
# ---------------------------------------------------------------------------
class ConfirmationGate:
    """
    Blocks high/critical tool execution until the user voice-confirms.

    Subscribes to TRANSCRIPT_READY events. If the next transcript
    contains "yes" (case-insensitive) within the timeout, returns True.
    """

    def __init__(self):
        self._pending = threading.Event()
        self._confirmed = False
        self._active = False
        bus.subscribe(Event.TRANSCRIPT_READY, self._on_transcript)

    def _on_transcript(self, transcript: str):
        if self._active and "yes" in transcript.lower():
            self._confirmed = True
            self._pending.set()

    def ask(self, action_description: str, timeout: int = 10) -> bool:
        """
        Speak the confirmation prompt and wait for user to say 'yes'.
        Returns True if confirmed, False if timed out.
        """
        prompt = f"Should I {action_description}? Say yes to confirm. Waiting {timeout} seconds."
        bus.publish(Event.TTS_ENQUEUE, prompt)

        self._confirmed = False
        self._active = True
        self._pending.clear()

        confirmed = self._pending.wait(timeout=timeout)
        self._active = False

        if not confirmed:
            bus.publish(Event.TTS_ENQUEUE, "Confirmation timed out. Action cancelled.")
            logger.warning(f"ConfirmationGate: timed out for '{action_description}'")
        return self._confirmed


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------
class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._gate = ConfirmationGate()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register(self, tool: Tool):
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered — overwriting.")
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name} (risk={tool.risk_level})")

    def register_many(self, tools: list[Tool]):
        for t in tools:
            self.register(t)

    # ------------------------------------------------------------------
    # Schema for LLM prompt injection
    # ------------------------------------------------------------------
    def get_schema(self) -> list[dict]:
        """Return JSON-serialisable tool schema list for the LLM system prompt."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.args_schema,
                "risk_level": t.risk_level,
            }
            for t in self._tools.values()
        ]

    # ------------------------------------------------------------------
    # Execution with risk gate
    # ------------------------------------------------------------------
    def execute(self, name: str, args: dict) -> Observation:
        if name not in self._tools:
            return Observation(
                content=f"Unknown tool: '{name}'",
                is_error=True,
                error=f"Tool '{name}' is not registered."
            )

        tool = self._tools[name]

        # Risk gate
        if tool.risk_level == "high":
            action_desc = f"{tool.name} with args {args}"
            if not self._gate.ask(action_desc, timeout=10):
                return Observation(
                    content="Action cancelled — no confirmation received.",
                    is_error=False
                )
        elif tool.risk_level == "critical":
            action_desc = f"{tool.name} with args {args}"
            if not self._gate.ask(action_desc, timeout=30):
                return Observation(
                    content="Critical action cancelled — no confirmation received.",
                    is_error=False
                )

        # Execute
        start = time.time()
        try:
            result = tool.handler(**args)
            duration_ms = int((time.time() - start) * 1000)
            logger.success(f"Tool executed: {name} in {duration_ms}ms")
            bus.publish(Event.TOOL_EXECUTED, {"tool": name, "args": args, "result": result})
            return Observation(content=str(result), duration_ms=duration_ms)
        except TypeError as e:
            # Argument mismatch — surface cleanly to the agent
            return Observation(
                content=f"Tool '{name}' called with wrong arguments: {e}",
                is_error=True,
                error=str(e)
            )
        except Exception as e:
            logger.error(f"Tool '{name}' raised an error: {e}")
            return Observation(
                content=f"Tool '{name}' failed: {e}",
                is_error=True,
                error=str(e)
            )

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())


# Singleton instance
registry = ToolRegistry()
