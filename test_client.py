import time
from core.events import bus, Event
from llm.client import LLMClient
from core.config import config

def test_conversational():
    print("Initializing LLMClient...")
    client = LLMClient()
    
    print(f"Models configured: fast={client.fast_model}, deep={client.deep_model}")
    print(f"Base URL: {client.base_url}")
    
    responses = []
    def on_tts_enqueue(text: str):
        print(f"TTS Enqueue -> {text}")
        responses.append(text)
        
    bus.subscribe(Event.TTS_ENQUEUE, on_tts_enqueue)
    
    print("\nSending conversational test query...")
    bus.publish(Event.TRANSCRIPT_READY, "Hello, how are you doing today?")
    
    time.sleep(5)  # Wait for background thread to process
    
    assert len(responses) > 0, "No response generated!"
    print("\nTest passed successfully!")

if __name__ == "__main__":
    test_conversational()
