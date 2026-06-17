"""
tools/shell.py — Shell command execution tool for JARVIS.

Risk level: HIGH — requires voice confirmation before any command runs.
"""

import subprocess
from loguru import logger
from tools.registry import Tool


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def shell_run(command: str, timeout: int = 30) -> str:
    """
    Execute a shell command using PowerShell and return its output.

    Always runs with a timeout. stdout and stderr are merged so the
    agent can observe what happened. Requires prior voice confirmation
    (enforced by the registry's ConfirmationGate).
    """
    logger.info(f"shell_run: executing command: {command}")
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        output = result.stdout.strip()
        error = result.stderr.strip()

        if result.returncode != 0:
            combined = f"Command exited with code {result.returncode}."
            if output:
                combined += f"\nOutput:\n{output}"
            if error:
                combined += f"\nError:\n{error}"
            return combined

        return output if output else f"Command completed with exit code 0 (no output)."

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except FileNotFoundError:
        return "Error: PowerShell not found. Cannot execute shell command."
    except Exception as e:
        return f"Error executing shell command: {e}"


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------

SHELL_TOOLS = [
    Tool(
        name="shell_run",
        description=(
            "Execute a PowerShell command on the local Windows machine and return the output. "
            "Use only for tasks that genuinely require shell access. "
            "Requires user confirmation before execution. "
            "Always prefer safer specific tools (file_read, app_launch, etc.) over this when possible."
        ),
        args_schema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The PowerShell command string to execute."
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum seconds to wait for command completion. Default 30.",
                    "default": 30
                }
            },
            "required": ["command"]
        },
        handler=shell_run,
        risk_level="high",
    ),
]
