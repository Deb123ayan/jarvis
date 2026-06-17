"""
tools/system.py — Windows system control tools for JARVIS.

Tools: get_volume, set_volume, get_battery, get_processes, kill_process, power_action
Uses pycaw for audio, psutil for process/battery, ctypes for power.
"""

import ctypes
import subprocess
from loguru import logger

import psutil

from tools.registry import Tool

# pycaw is Windows-only — graceful degradation if missing
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    _HAS_PYCAW = True
except Exception:
    _HAS_PYCAW = False
    logger.warning("pycaw not available — volume control tools will be limited.")


# ---------------------------------------------------------------------------
# Volume helpers
# ---------------------------------------------------------------------------

def _get_volume_interface():
    """Return the Windows IAudioEndpointVolume COM interface."""
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def get_volume() -> str:
    """Return the current system master volume as a percentage (0–100)."""
    if not _HAS_PYCAW:
        return "Error: pycaw not available. Cannot read volume."
    try:
        vol = _get_volume_interface()
        level = vol.GetMasterVolumeLevelScalar()
        muted = vol.GetMute()
        pct = int(level * 100)
        mute_str = " (muted)" if muted else ""
        return f"System volume is at {pct}%{mute_str}."
    except Exception as e:
        return f"Error getting volume: {e}"


def set_volume(level: int) -> str:
    """
    Set the system master volume.

    Args:
        level: Integer 0–100 representing the desired volume percentage.
    """
    if not _HAS_PYCAW:
        return "Error: pycaw not available. Cannot set volume."
    if not 0 <= level <= 100:
        return "Error: Volume level must be between 0 and 100."
    try:
        vol = _get_volume_interface()
        vol.SetMasterVolumeLevelScalar(level / 100.0, None)
        return f"Volume set to {level}%."
    except Exception as e:
        return f"Error setting volume: {e}"


def get_battery() -> str:
    """Return the current battery status and charge level."""
    battery = psutil.sensors_battery()
    if battery is None:
        return "No battery detected — this machine is likely a desktop."
    pct = int(battery.percent)
    plugged = "plugged in" if battery.power_plugged else "on battery"
    secs_left = battery.secsleft
    if secs_left == psutil.POWER_TIME_UNLIMITED:
        time_str = ""
    elif secs_left == psutil.POWER_TIME_UNKNOWN:
        time_str = ""
    else:
        h, m = divmod(secs_left // 60, 60)
        time_str = f", approximately {h}h {m}m remaining"
    return f"Battery is at {pct}% and {plugged}{time_str}."


def get_brightness() -> str:
    """Return the current screen brightness percentage (0-100)."""
    try:
        cmd = ["powershell", "-Command", "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        level = int(result.stdout.strip())
        return f"Current screen brightness is {level}%."
    except Exception as e:
        return f"Error getting brightness: {e}. (Note: Desktop monitors often do not support WMI brightness controls)."


def set_brightness(level: int) -> str:
    """
    Set the screen brightness.

    Args:
        level: Integer 0-100 representing the desired brightness percentage.
    """
    if not 0 <= level <= 100:
        return "Error: Brightness level must be between 0 and 100."
    try:
        cmd = ["powershell", "-Command", f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return f"Brightness set to {level}%."
    except Exception as e:
        return f"Error setting brightness: {e}. (Note: Desktop monitors often do not support WMI brightness controls)."



def get_processes(top_n: int = 10) -> str:
    """
    Return the top N processes sorted by CPU usage.

    Args:
        top_n: Number of top processes to return (default 10).
    """
    try:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Sort by CPU then memory
        procs.sort(key=lambda x: (x.get("cpu_percent") or 0), reverse=True)
        top = procs[:top_n]

        lines = [f"Top {top_n} processes by CPU:"]
        for p in top:
            lines.append(
                f"  PID {p['pid']:>6} | CPU {p.get('cpu_percent', 0):>5.1f}% "
                f"| MEM {p.get('memory_percent', 0):>5.1f}% | {p['name']}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing processes: {e}"


def kill_process(name: str) -> str:
    """
    Terminate all processes matching the given name.

    Args:
        name: Process name to kill (e.g. 'notepad.exe'). Case-insensitive.
    """
    killed = []
    errors = []
    name_lower = name.lower().replace(".exe", "")

    for p in psutil.process_iter(["pid", "name"]):
        try:
            pname = (p.info["name"] or "").lower().replace(".exe", "")
            if pname == name_lower:
                p.kill()
                killed.append(p.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            errors.append(str(e))

    if not killed and not errors:
        return f"No process named '{name}' found."
    parts = []
    if killed:
        parts.append(f"Killed {len(killed)} process(es) named '{name}' (PIDs: {killed}).")
    if errors:
        parts.append(f"Could not kill {len(errors)} process(es): {'; '.join(errors)}")
    return " ".join(parts)


def power_action(action: str) -> str:
    """
    Perform a system power action: shutdown, restart, or sleep.

    Args:
        action: One of 'shutdown', 'restart', 'sleep'.
    """
    action = action.lower().strip()
    commands = {
        "shutdown": ["shutdown", "/s", "/t", "10"],
        "restart": ["shutdown", "/r", "/t", "10"],
        "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"],
    }
    if action not in commands:
        return f"Unknown power action '{action}'. Use: shutdown, restart, or sleep."
    try:
        subprocess.run(commands[action], check=True)
        if action in ("shutdown", "restart"):
            return f"System will {action} in 10 seconds. Run 'shutdown /a' to abort."
        return f"System is going to sleep."
    except Exception as e:
        return f"Error executing power action '{action}': {e}"


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

SYSTEM_TOOLS = [
    Tool(
        name="get_volume",
        description="Get the current Windows system master volume level as a percentage (0–100). Use when the user asks about the current volume.",
        args_schema={"type": "object", "properties": {}, "required": []},
        handler=get_volume,
        risk_level="low",
    ),
    Tool(
        name="set_volume",
        description="Set the Windows system master volume to a specific level (0–100). Use when the user says 'set volume to X' or 'turn volume up/down to X percent'.",
        args_schema={
            "type": "object",
            "properties": {
                "level": {
                    "type": "integer",
                    "description": "Volume percentage to set, 0 (silent) to 100 (maximum).",
                    "minimum": 0,
                    "maximum": 100
                }
            },
            "required": ["level"]
        },
        handler=set_volume,
        risk_level="medium",
    ),
    Tool(
        name="get_battery",
        description="Check the current battery charge percentage and whether it is plugged in. Use when the user asks about battery life or power status.",
        args_schema={"type": "object", "properties": {}, "required": []},
        handler=get_battery,
        risk_level="low",
    ),
    Tool(
        name="get_brightness",
        description="Get the current screen brightness level as a percentage (0-100). Use when the user asks about screen brightness.",
        args_schema={"type": "object", "properties": {}, "required": []},
        handler=get_brightness,
        risk_level="low",
    ),
    Tool(
        name="set_brightness",
        description="Set the screen brightness to a specific level (0-100). Use when the user says 'set brightness to X' or 'dim the screen'.",
        args_schema={
            "type": "object",
            "properties": {
                "level": {
                    "type": "integer",
                    "description": "Brightness percentage to set, 0 to 100.",
                    "minimum": 0,
                    "maximum": 100
                }
            },
            "required": ["level"]
        },
        handler=set_brightness,
        risk_level="medium",
    ),
    Tool(
        name="get_processes",
        description="List the top N running processes sorted by CPU usage. Use when the user asks what's running, what's using CPU, or why the computer is slow.",
        args_schema={
            "type": "object",
            "properties": {
                "top_n": {
                    "type": "integer",
                    "description": "Number of top processes to return. Default is 10.",
                    "default": 10
                }
            },
            "required": []
        },
        handler=get_processes,
        risk_level="low",
    ),
    Tool(
        name="kill_process",
        description="Terminate all running processes with the given name. Requires confirmation. Use when the user asks to kill or force-quit a specific app or process.",
        args_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Process name to terminate, e.g. 'notepad.exe' or 'chrome'. Case-insensitive."
                }
            },
            "required": ["name"]
        },
        handler=kill_process,
        risk_level="high",
    ),
    Tool(
        name="power_action",
        description="Perform a Windows power action: shutdown, restart, or sleep. CRITICAL — always confirm with user before executing.",
        args_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "One of: 'shutdown', 'restart', 'sleep'.",
                    "enum": ["shutdown", "restart", "sleep"]
                }
            },
            "required": ["action"]
        },
        handler=power_action,
        risk_level="critical",
    ),
]
