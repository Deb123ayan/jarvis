"""
scripts/mock_publisher.py — Test harness for the JARVIS pipeline.

Bypasses wake word and microphone — publishes fake TRANSCRIPT_READY events
directly to test LLM + TTS + tool dispatch without hardware.

Usage:
    python scripts/mock_publisher.py
    python scripts/mock_publisher.py --phrase "open notepad"
"""

import sys
import time
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from core.events import bus, Event
from tools.registry import registry
from tools.filesystem import FILESYSTEM_TOOLS
from tools.system import SYSTEM_TOOLS
from tools.apps import APP_TOOLS
from tools.clipboard import CLIPBOARD_TOOLS
from tools.shell import SHELL_TOOLS
from llm.client import LLMClient
from tts.queue_manager import TTSWorker

# Test phrases that exercise different paths
DEMO_PHRASES = [
    "Introduce yourself in one short sentence.",      # Conversational
    "What files are in my Downloads folder?",          # file_search / dir_list
    "What is my current volume level?",                # get_volume
    "Set the volume to 50 percent.",                   # set_volume
    "What apps are currently running?",                # app_list
    "Open notepad.",                                   # app_launch
    "What's in my clipboard?",                         # clipboard_read
    "How much battery do I have left?",                # get_battery
    "What are the top processes using CPU right now?", # get_processes
]


def main():
    parser = argparse.ArgumentParser(description="JARVIS mock event publisher")
    parser.add_argument(
        "--phrase", "-p",
        type=str,
        default=None,
        help="Custom phrase to send (defaults to demo sequence)"
    )
    parser.add_argument(
        "--wait", "-w",
        type=int,
        default=20,
        help="Seconds to wait for pipeline to respond (default 20)"
    )
    args = parser.parse_args()

    logger.info("Mock Publisher — registering tools...")
    registry.register_many(FILESYSTEM_TOOLS)
    registry.register_many(SYSTEM_TOOLS)
    registry.register_many(APP_TOOLS)
    registry.register_many(CLIPBOARD_TOOLS)
    registry.register_many(SHELL_TOOLS)

    tts_worker = TTSWorker()
    llm_client = LLMClient(registry=registry)
    tts_worker.start()

    if args.phrase:
        phrases = [args.phrase]
    else:
        phrases = DEMO_PHRASES[:3]  # Run first 3 by default to keep demo short

    for phrase in phrases:
        logger.info(f"Publishing: '{phrase}'")
        bus.publish(Event.TRANSCRIPT_READY, phrase)
        logger.info(f"Waiting {args.wait}s for response...")
        time.sleep(args.wait)
        logger.info("-" * 40)


if __name__ == "__main__":
    main()
