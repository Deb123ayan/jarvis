from enum import Enum

class Event(Enum):
    WAKE_DETECTED       = "wake_detected"
    AUDIO_CAPTURED      = "audio_captured"
    TRANSCRIPT_READY    = "transcript_ready"
    AGENT_RESPONSE      = "agent_response"
    TTS_ENQUEUE         = "tts_enqueue"
    TTS_INTERRUPT       = "tts_interrupt"
    CONTEXT_CHANGED     = "context_changed"
    MEMORY_UPDATED      = "memory_updated"
    PLUGIN_LOADED       = "plugin_loaded"
    TOOL_EXECUTED       = "tool_executed"

class EventBus:
    def __init__(self):
        self._subscribers: dict[Event, list[callable]] = {}
    
    def subscribe(self, event: Event, handler: callable):
        self._subscribers.setdefault(event, []).append(handler)
    
    def publish(self, event: Event, data=None):
        for handler in self._subscribers.get(event, []):
            handler(data)

# Singleton instance to be used across the application
bus = EventBus()
