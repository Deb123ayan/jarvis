import time
from loguru import logger

from core.events import bus, Event
from core.config import config

# Tools
from tools.registry import registry
from tools.filesystem import FILESYSTEM_TOOLS
from tools.system import SYSTEM_TOOLS
from tools.apps import APP_TOOLS
from tools.clipboard import CLIPBOARD_TOOLS
from tools.shell import SHELL_TOOLS
from tools.timers import TIMER_TOOLS

# LLM
from llm.client import LLMClient

def _register_tools():
    """Register all Phase 2 tools into the singleton registry."""
    registry.register_many(FILESYSTEM_TOOLS)
    registry.register_many(SYSTEM_TOOLS)
    registry.register_many(APP_TOOLS)
    registry.register_many(CLIPBOARD_TOOLS)
    registry.register_many(SHELL_TOOLS)
    registry.register_many(TIMER_TOOLS)

def main():
    logger.info("Initializing Text-Based JARVIS CLI...")
    
    _register_tools()
    llm_client = LLMClient(registry=registry)
    
    # Instead of running the full TTS pipeline, we can just print the responses
    # If you want spoken audio too, we could start TTSWorker() here.
    def on_response(text: str):
        # Print with carriage return to clear the current line, print JARVIS message,
        # then redraw the "You: " prompt and flush so it appears immediately
        print(f"\r\n[JARVIS]: {text}\nYou: ", end="", flush=True)
        
    bus.subscribe(Event.TTS_ENQUEUE, on_response)
    
    print("=" * 60)
    print("JARVIS CLI Ready.")
    print("Capabilities:")
    print("  - Filesystem: Read, write, and manage files/directories")
    print("  - System: Control volume, brightness, battery, etc.")
    print("  - Apps: Open and close applications")
    print("  - Clipboard: Read from and write to the clipboard")
    print("  - Shell: Execute terminal commands")
    print("  - Timers: Set, list, and cancel background timers")
    print("Type your commands below. Type 'exit' or 'quit' to close.")
    print("=" * 60)
    
    try:
        while True:
            # Short sleep to let background LLM threads print their results
            time.sleep(0.5) 
            user_input = input("You: ")
            
            if user_input.lower().strip() in ["exit", "quit"]:
                break
                
            if user_input.strip():
                # Send the text exactly as if the STT pipeline transcribed it
                bus.publish(Event.TRANSCRIPT_READY, user_input)
                
    except KeyboardInterrupt:
        print("\nGoodbye.")

if __name__ == "__main__":
    main()
