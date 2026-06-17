"""
tools/reminders.py — Proactive, time-based reminders for JARVIS.

Unlike set_timer (countdown), these reminders fire at a real clock time
(e.g. "remind me at 3 PM to call mom") and speak via TTS with no user
interaction required.

Uses APScheduler's BackgroundScheduler so it runs in its own thread and
survives the main loop without polling.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict

from loguru import logger

from tools.registry import Tool
from core.events import bus, Event

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.date import DateTrigger
    _HAS_APS = True
except ImportError:
    _HAS_APS = False
    logger.warning("APScheduler not installed — reminders disabled. Run: pip install APScheduler")


# ---------------------------------------------------------------------------
# Scheduler singleton
# ---------------------------------------------------------------------------

_scheduler: "BackgroundScheduler | None" = None
_active_reminders: Dict[str, dict] = {}


def _get_scheduler() -> "BackgroundScheduler":
    global _scheduler
    if _scheduler is None:
        if not _HAS_APS:
            raise RuntimeError("APScheduler is not installed.")
        # Resolve local timezone — try dateutil first, then fall back to UTC
        try:
            from dateutil import tz as _tz
            local_tz = _tz.tzlocal()
        except Exception:
            import datetime as _dt
            local_tz = _dt.timezone.utc
        _scheduler = BackgroundScheduler(timezone=local_tz)
        _scheduler.start()
        logger.info("APScheduler BackgroundScheduler started for reminders.")
    return _scheduler


# ---------------------------------------------------------------------------
# Internal callback — fires when the reminder time arrives
# ---------------------------------------------------------------------------

def _fire_reminder(reminder_id: str, message: str):
    """Called by APScheduler at the scheduled time — fires regardless of user activity."""
    import sys
    spoken = f"Hey! Reminder: {message}"
    logger.info(f"Firing reminder [{reminder_id}]: {message}")

    # \a = terminal bell, \r clears the current input line visually
    # Write to stderr so it bypasses Python's stdout buffering / input() block
    alert = (
        f"\a\r\n"
        f"{'='*55}\n"
        f"  ⏰  JARVIS REMINDER: {message}\n"
        f"{'='*55}\n"
        f"You: "
    )
    sys.stderr.write(alert)
    sys.stderr.flush()

    # Speak it — TTS worker thread picks this up immediately
    bus.publish(Event.TTS_ENQUEUE, spoken)
    # Repeat once after 4 seconds so it's unmissable
    import threading, time
    def _repeat():
        time.sleep(4)
        bus.publish(Event.TTS_ENQUEUE, f"Reminder: {message}")
    threading.Thread(target=_repeat, daemon=True).start()

    _active_reminders.pop(reminder_id, None)



# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def remind_me(message: str, at: str = "", in_minutes: int = 0, in_seconds: int = 0) -> str:
    """
    Schedule a proactive spoken reminder.

    Provide ONE of:
      - at         : clock time string like "3:30 PM", "15:30", "9am", "2026-06-18 09:00"
      - in_minutes : number of minutes from now
      - in_seconds : number of seconds from now (for quick tests)

    The reminder fires automatically — no user input needed.
    """
    if not _HAS_APS:
        return "Error: APScheduler is not installed. Run: pip install APScheduler"

    now = datetime.now()
    run_at: datetime | None = None

    # --- parse when ---
    if at:
        run_at = _parse_clock_time(at, now)
        if run_at is None:
            return (
                f"Error: Could not understand the time '{at}'. "
                "Try formats like '3:30 PM', '15:30', '9am', or '2026-06-18 09:00'."
            )
    elif in_minutes > 0:
        run_at = now + timedelta(minutes=in_minutes)
    elif in_seconds > 0:
        run_at = now + timedelta(seconds=in_seconds)
    else:
        return "Error: Please specify when — use 'at', 'in_minutes', or 'in_seconds'."

    if run_at <= now:
        # If today's time already passed, schedule for tomorrow
        run_at += timedelta(days=1)

    reminder_id = str(uuid.uuid4())[:8]
    sch = _get_scheduler()
    sch.add_job(
        _fire_reminder,
        trigger=DateTrigger(run_date=run_at),
        args=[reminder_id, message],
        id=reminder_id,
        misfire_grace_time=60,
    )
    _active_reminders[reminder_id] = {
        "message": message,
        "fire_at": run_at.isoformat(),
        "id": reminder_id,
    }
    friendly = run_at.strftime("%I:%M %p on %A, %b %d")
    logger.info(f"Reminder set [{reminder_id}] at {run_at} — '{message}'")
    return f"Got it! I'll remind you at {friendly}: \"{message}\" (ID: {reminder_id})"


def list_reminders() -> str:
    """Return all pending reminders."""
    if not _active_reminders:
        return "You have no pending reminders."
    lines = ["Pending reminders:"]
    for rid, data in _active_reminders.items():
        dt = datetime.fromisoformat(data["fire_at"])
        friendly = dt.strftime("%I:%M %p on %A, %b %d")
        lines.append(f"  [{rid}] \"{data['message']}\" — fires at {friendly}")
    return "\n".join(lines)


def cancel_reminder(name_or_id: str) -> str:
    """Cancel a pending reminder by its ID or a keyword in the message."""
    if not _HAS_APS:
        return "Error: APScheduler is not installed."

    matched = []
    for rid, data in list(_active_reminders.items()):
        if rid == name_or_id or name_or_id.lower() in data["message"].lower():
            matched.append((rid, data["message"]))

    if not matched:
        return f"No reminder found matching '{name_or_id}'."

    sch = _get_scheduler()
    for rid, msg in matched:
        try:
            sch.remove_job(rid)
        except Exception:
            pass
        _active_reminders.pop(rid, None)

    canceled_msgs = ", ".join(f'"{m}"' for _, m in matched)
    return f"Canceled reminder(s): {canceled_msgs}."


# ---------------------------------------------------------------------------
# Time string parser
# ---------------------------------------------------------------------------

def _parse_clock_time(s: str, now: datetime) -> datetime | None:
    """
    Parse a human-readable time string into a datetime for today.
    Accepts: "3pm", "3:30 PM", "15:30", "2026-06-18 09:00", etc.
    Returns None on failure.
    """
    s = s.strip()
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %I:%M %p",
        "%H:%M",
        "%I:%M %p",
        "%I:%M%p",
        "%I %p",
        "%I%p",
    ]
    # Normalise: "3pm" → "3 pm", "9AM" → "9 am"
    import re
    s_norm = re.sub(r"(\d)(am|pm)", r"\1 \2", s, flags=re.IGNORECASE)

    for fmt in formats:
        try:
            parsed = datetime.strptime(s_norm, fmt)
            # If no date component, use today's date
            if parsed.year == 1900:
                parsed = parsed.replace(year=now.year, month=now.month, day=now.day)
            return parsed
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

REMINDER_TOOLS = [
    Tool(
        name="remind_me",
        description=(
            "Schedule a proactive spoken reminder that fires automatically at a specific time, "
            "even without any user input — making JARVIS sentient about reminders. "
            "Use when the user says things like 'remind me at 3 PM to take my medicine', "
            "'remind me in 20 minutes to check the oven', or 'remind me tomorrow at 9 AM to call mom'. "
            "Provide 'at' (clock time string) OR 'in_minutes' (minutes from now)."
        ),
        args_schema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "What to remind the user about (e.g. 'take medicine', 'call mom')."
                },
                "at": {
                    "type": "string",
                    "description": "Clock time to fire the reminder, e.g. '3:30 PM', '15:30', '9am', '2026-06-18 14:00'. Use this OR in_minutes.",
                    "default": ""
                },
                "in_minutes": {
                    "type": "integer",
                    "description": "Minutes from now to fire the reminder (e.g. 20). Use this OR at.",
                    "default": 0
                },
                "in_seconds": {
                    "type": "integer",
                    "description": "Seconds from now (useful for quick tests). Use this OR at/in_minutes.",
                    "default": 0
                },
            },
            "required": ["message"],
        },
        handler=remind_me,
        risk_level="low",
    ),
    Tool(
        name="list_reminders",
        description="List all pending scheduled reminders and their fire times.",
        args_schema={"type": "object", "properties": {}, "required": []},
        handler=list_reminders,
        risk_level="low",
    ),
    Tool(
        name="cancel_reminder",
        description="Cancel a pending reminder by its ID or a keyword from its message.",
        args_schema={
            "type": "object",
            "properties": {
                "name_or_id": {
                    "type": "string",
                    "description": "Reminder ID or a keyword matching the reminder message."
                }
            },
            "required": ["name_or_id"],
        },
        handler=cancel_reminder,
        risk_level="low",
    ),
]
