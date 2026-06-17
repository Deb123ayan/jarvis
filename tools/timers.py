"""
tools/timers.py — Timer control tools for JARVIS.

Allows setting, listing, and canceling timers.
Uses standard library threading for background timers.
"""

import threading
import uuid
import time
from typing import Dict
from loguru import logger

from tools.registry import Tool
from core.events import bus, Event

# Global dictionary to track active timers
_active_timers: Dict[str, dict] = {}
_timer_lock = threading.Lock()

def _timer_thread_func(timer_id: str, name: str, duration: int):
    """Thread function that runs the timer and prints the countdown."""
    end_time = time.time() + duration
    
    while True:
        with _timer_lock:
            if timer_id not in _active_timers:
                # Timer was canceled
                return
                
        remaining = int(end_time - time.time())
        if remaining <= 0:
            break
            
        # Print the remaining time in the terminal, clearing the current line
        print(f"\r[TIMER '{name}'] {remaining} seconds remaining... ", end="", flush=True)
        time.sleep(min(1.0, end_time - time.time()))
        
    # Timer finished
    # Clear the countdown line, write a loud visual alert to stderr (bypasses input() block),
    # then speak the message twice so it's impossible to miss.
    import sys
    alert = (
        f"\a\r\n"
        f"{'='*55}\n"
        f"  ⏰  TIMER '{name}' IS UP!\n"
        f"{'='*55}\n"
        f"You: "
    )
    sys.stderr.write(alert)
    sys.stderr.flush()

    with _timer_lock:
        if timer_id in _active_timers:
            del _active_timers[timer_id]
            logger.info(f"Timer '{name}' finished.")
            msg = f"Hey! Your timer '{name}' is up!"
            bus.publish(Event.TTS_ENQUEUE, msg)
            # Repeat once after 4 seconds
            import threading, time as _time
            def _repeat():
                _time.sleep(4)
                bus.publish(Event.TTS_ENQUEUE, f"Timer '{name}' is done!")
            threading.Thread(target=_repeat, daemon=True).start()


def set_timer(seconds: int, name: str = "default") -> str:
    """
    Set a timer to go off after a given number of seconds.

    Args:
        seconds: Duration in seconds for the timer.
        name: A friendly name for the timer (default is "default").
    """
    if seconds <= 0:
        return "Error: Timer duration must be greater than 0 seconds."
        
    timer_id = str(uuid.uuid4())[:8]
    
    t = threading.Thread(target=_timer_thread_func, args=(timer_id, name, seconds))
    t.daemon = True  # Allows program to exit even if timers are running
    
    with _timer_lock:
        _active_timers[timer_id] = {
            "name": name,
            "thread": t,
            "end_time": time.time() + seconds,
            "duration": seconds
        }
    
    t.start()
    return f"Started timer '{name}' for {seconds} seconds. (ID: {timer_id})"

def list_timers() -> str:
    """Return a list of all active timers."""
    with _timer_lock:
        if not _active_timers:
            return "There are no active timers."
            
        lines = ["Active timers:"]
        now = time.time()
        for t_id, data in _active_timers.items():
            remaining = max(0, int(data["end_time"] - now))
            name = data["name"]
            lines.append(f"  - '{name}' (ID: {t_id}): {remaining} seconds remaining.")
            
        return "\n".join(lines)

def cancel_timer(name_or_id: str) -> str:
    """
    Cancel an active timer by its name or ID.

    Args:
        name_or_id: The name or ID of the timer to cancel.
    """
    canceled = []
    with _timer_lock:
        to_remove = []
        for t_id, data in _active_timers.items():
            if data["name"].lower() == name_or_id.lower() or t_id == name_or_id:
                # We don't need to cancel the thread explicitly; it will exit when removed from _active_timers
                to_remove.append(t_id)
                canceled.append(data["name"])
                
        for t_id in to_remove:
            del _active_timers[t_id]
            
    if not canceled:
        return f"No active timer found with name or ID '{name_or_id}'."
        
    return f"Canceled timer(s): {', '.join(canceled)}."

TIMER_TOOLS = [
    Tool(
        name="set_timer",
        description="Set a timer to alert the user after a specified number of seconds. Use when the user asks to 'set a timer for 5 minutes' (convert to seconds).",
        args_schema={
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "integer",
                    "description": "Duration of the timer in seconds."
                },
                "name": {
                    "type": "string",
                    "description": "A descriptive name for the timer (e.g. 'pasta', 'laundry').",
                    "default": "default"
                }
            },
            "required": ["seconds"]
        },
        handler=set_timer,
        risk_level="low",
    ),
    Tool(
        name="list_timers",
        description="List all currently running timers and their remaining durations.",
        args_schema={"type": "object", "properties": {}, "required": []},
        handler=list_timers,
        risk_level="low",
    ),
    Tool(
        name="cancel_timer",
        description="Cancel a specific running timer by name or ID.",
        args_schema={
            "type": "object",
            "properties": {
                "name_or_id": {
                    "type": "string",
                    "description": "The name or ID of the timer to cancel."
                }
            },
            "required": ["name_or_id"]
        },
        handler=cancel_timer,
        risk_level="low",
    ),
]
