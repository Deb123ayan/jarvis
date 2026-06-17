"""
tools/clipboard.py — Clipboard read/write tools for JARVIS.

Uses pyperclip which works cross-platform but is especially clean on Windows.
"""

from loguru import logger
from tools.registry import Tool

try:
    import pyperclip
    _HAS_PYPERCLIP = True
except ImportError:
    _HAS_PYPERCLIP = False
    logger.warning("pyperclip not installed — clipboard tools will be unavailable.")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def clipboard_read() -> str:
    """Return the current clipboard text content."""
    if not _HAS_PYPERCLIP:
        return "Error: pyperclip is not installed."
    try:
        text = pyperclip.paste()
        if not text:
            return "Clipboard is empty."
        # Truncate for voice output
        preview = text[:500]
        suffix = f"... ({len(text)} characters total)" if len(text) > 500 else ""
        return preview + suffix
    except Exception as e:
        return f"Error reading clipboard: {e}"


def clipboard_write(text: str) -> str:
    """Write text to the clipboard, replacing current contents."""
    if not _HAS_PYPERCLIP:
        return "Error: pyperclip is not installed."
    try:
        pyperclip.copy(text)
        return f"Clipboard updated ({len(text)} characters)."
    except Exception as e:
        return f"Error writing to clipboard: {e}"


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

CLIPBOARD_TOOLS = [
    Tool(
        name="clipboard_read",
        description="Read and return the current text content of the Windows clipboard. Use when the user asks what is in their clipboard or to paste/use copied text.",
        args_schema={
            "type": "object",
            "properties": {},
            "required": []
        },
        handler=clipboard_read,
        risk_level="low",
    ),
    Tool(
        name="clipboard_write",
        description="Write text to the clipboard so the user can paste it. Use when the user asks to copy something to clipboard.",
        args_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to write to the clipboard."}
            },
            "required": ["text"]
        },
        handler=clipboard_write,
        risk_level="medium",
    ),
]
