"""
tools/apps.py — Application control tools for JARVIS.

Tools: app_launch, app_close, app_focus, app_list

Uses os.startfile for launching, psutil for listing/closing,
and pywinauto for window focusing.
"""

import os
import subprocess
import time
from pathlib import Path

import psutil
from loguru import logger

from tools.registry import Tool

# pywinauto is optional — focus tool degrades gracefully without it
try:
    import pywinauto
    from pywinauto import Desktop
    _HAS_PYWINAUTO = True
except Exception:
    _HAS_PYWINAUTO = False
    logger.warning("pywinauto not available — app_focus will be limited.")

# Common app name → executable mapping for convenience
APP_ALIASES: dict[str, str] = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "paint": "mspaint.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "vs code": "code.exe",
    "vscode": "code.exe",
    "code": "code.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "spotify": "Spotify.exe",
    "discord": "Discord.exe",
    "slack": "slack.exe",
    "zoom": "Zoom.exe",
    "obs": "obs64.exe",
    "vlc": "vlc.exe",
    "steam": "steam.exe",
}


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def app_launch(name: str) -> str:
    """
    Launch an application by name or executable path.

    Args:
        name: App name (e.g. 'notepad', 'vs code') or full path to executable.
    """
    target = APP_ALIASES.get(name.lower(), name)

    # If it looks like an absolute path, use startfile directly
    if Path(target).suffix.lower() in (".exe", ".bat", ".cmd", ".lnk"):
        try:
            os.startfile(target)
            return f"Launched: {name}"
        except FileNotFoundError:
            pass

    # Try subprocess — works for apps on PATH
    try:
        subprocess.Popen([target], shell=True)
        return f"Launched: {name}"
    except Exception as e:
        return f"Error launching '{name}': {e}"


def app_close(name: str) -> str:
    """
    Close all running instances of an application by name.

    Args:
        name: Application name (e.g. 'notepad', 'chrome'). Case-insensitive.
    """
    name_lower = name.lower().replace(".exe", "")
    closed = 0
    errors = []

    for p in psutil.process_iter(["pid", "name"]):
        try:
            pname = (p.info["name"] or "").lower().replace(".exe", "")
            if pname == name_lower or name_lower in pname:
                p.terminate()
                closed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            errors.append(str(e))

    if closed == 0 and not errors:
        return f"No running process found matching '{name}'."
    parts = []
    if closed:
        parts.append(f"Closed {closed} instance(s) of '{name}'.")
    if errors:
        parts.append(f"Could not close {len(errors)} instance(s).")
    return " ".join(parts)


def app_focus(name: str) -> str:
    """
    Bring a running application window to the foreground by name.

    Args:
        name: Application or window title (partial match accepted).
    """
    if not _HAS_PYWINAUTO:
        return "Error: pywinauto not available — cannot focus windows."
    try:
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
        name_lower = name.lower()
        matched = [w for w in windows if name_lower in (w.window_text() or "").lower()]
        if not matched:
            return f"No open window matching '{name}' found."
        matched[0].set_focus()
        return f"Focused window: {matched[0].window_text()}"
    except Exception as e:
        return f"Error focusing '{name}': {e}"


def app_list() -> str:
    """Return a list of all currently running application windows (unique app names)."""
    try:
        seen = set()
        names = []
        for p in psutil.process_iter(["pid", "name", "status"]):
            try:
                n = p.info["name"]
                if n and n not in seen and p.info["status"] == psutil.STATUS_RUNNING:
                    seen.add(n)
                    names.append(n)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        names.sort()
        if not names:
            return "No running processes found."
        return f"Running processes ({len(names)}):\n" + "\n".join(f"  {n}" for n in names)
    except Exception as e:
        return f"Error listing apps: {e}"


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

APP_TOOLS = [
    Tool(
        name="app_launch",
        description=(
            "Launch an application by name on Windows. Supports common names like 'notepad', "
            "'vs code', 'chrome', 'spotify', 'calculator', 'explorer', 'terminal', 'discord'. "
            "Also accepts a full path to an executable. Use when the user says 'open X' or 'launch X'."
        ),
        args_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "App name (e.g. 'notepad', 'vs code') or absolute path to executable."
                }
            },
            "required": ["name"]
        },
        handler=app_launch,
        risk_level="medium",
    ),
    Tool(
        name="app_close",
        description="Close/terminate all running instances of an application by name. Use when the user says 'close X' or 'quit X'.",
        args_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Application name to close (e.g. 'notepad', 'chrome'). Case-insensitive."
                }
            },
            "required": ["name"]
        },
        handler=app_close,
        risk_level="medium",
    ),
    Tool(
        name="app_focus",
        description="Bring a running application window to the foreground. Use when the user wants to switch to or focus a specific app.",
        args_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Application name or part of window title to match."
                }
            },
            "required": ["name"]
        },
        handler=app_focus,
        risk_level="medium",
    ),
    Tool(
        name="app_list",
        description="List all currently running applications and processes. Use when the user asks what apps are open or running.",
        args_schema={"type": "object", "properties": {}, "required": []},
        handler=app_list,
        risk_level="low",
    ),
]
