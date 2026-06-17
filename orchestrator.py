"""
orchestrator.py — JARVIS entry point.

Initialises all modules, registers Phase 2 tools, and starts the thread model.
"""

import time
from loguru import logger

from core.config import config
from core.events import bus, Event

# Phase 1 — Core pipeline
from wake_word.listener import WakeWordListener
from stt.transcriber import VoicePipeline
from tts.queue_manager import TTSWorker

# Phase 2 — Tool registry + tools
from tools.registry import registry
from tools.filesystem import FILESYSTEM_TOOLS
from tools.system import SYSTEM_TOOLS
from tools.apps import APP_TOOLS
from tools.clipboard import CLIPBOARD_TOOLS
from tools.shell import SHELL_TOOLS
from tools.timers import TIMER_TOOLS

# LLM (tool-aware)
from llm.client import LLMClient

# Live terminal dashboard
from ui.dashboard import Dashboard


def _register_tools():
    """Register all Phase 2 tools into the singleton registry."""
    logger.info("Registering tools...")
    registry.register_many(FILESYSTEM_TOOLS)
    registry.register_many(SYSTEM_TOOLS)
    registry.register_many(APP_TOOLS)
    registry.register_many(CLIPBOARD_TOOLS)
    registry.register_many(SHELL_TOOLS)
    registry.register_many(TIMER_TOOLS)
    logger.info(f"Registered {len(registry.list_tools())} tools: {registry.list_tools()}")


def main():
    logger.info("=" * 60)
    logger.info("  JARVIS — Starting up")
    logger.info("  Capabilities:")
    logger.info("   - Filesystem: Read, write, and manage files/directories")
    logger.info("   - System: Control volume, brightness, battery, etc.")
    logger.info("   - Apps: Open and close applications")
    logger.info("   - Clipboard: Read from and write to the clipboard")
    logger.info("   - Shell: Execute terminal commands")
    logger.info("=" * 60)
    logger.info(f"Config loaded. Fast model: {config.get('models.fast')} | Deep: {config.get('models.deep')}")

    # --- Phase 2: Register all tools ---
    _register_tools()

    # --- Phase 1: Core pipeline ---
    tts_worker = TTSWorker()
    llm_client = LLMClient(registry=registry)
    voice_pipeline = VoicePipeline()
    wake_word_listener = WakeWordListener()

    # Start live dashboard first so it captures all events
    # dashboard = Dashboard(refresh_per_second=15)
    # dashboard.start()

    # Start threads
    tts_worker.start()
    voice_pipeline.start()
    wake_word_listener.start()

    logger.info("JARVIS is running in VOICE + TEXT mode. (Type 'help' for tools, 'quit' to exit)")
    
    def on_response(text: str):
        # Print with carriage return to clear the current line, print JARVIS message,
        # then redraw the "You: " prompt and flush so it appears immediately
        print(f"\r\n[JARVIS]: {text}\nYou: ", end="", flush=True)
    bus.subscribe(Event.TTS_ENQUEUE, on_response)

    try:
        while True:
            time.sleep(0.5)
            user_input = input("You: ")
            
            if user_input.lower().strip() in ["exit", "quit"]:
                break
            elif user_input.lower().strip() == "help":
                print("\n[Available Tools]:")
                for t in registry.list_tools():
                    print(f"  - {t}")
                print()
            elif user_input.strip():
                llm_client._dispatch(user_input)
                
    except KeyboardInterrupt:
        logger.info("JARVIS shutting down...")
        wake_word_listener.stop()
        voice_pipeline.stop()
        # dashboard.stop()
        logger.info("Goodbye.")


if __name__ == "__main__":
    main()
