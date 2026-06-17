import queue
import threading
from loguru import logger
from core.events import bus, Event
from tts.engine import TTSEngine

class TTSWorker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.tts_queue = queue.Queue()
        self.engine = TTSEngine()
        
        bus.subscribe(Event.TTS_ENQUEUE, self._on_enqueue)
        bus.subscribe(Event.TTS_INTERRUPT, self._on_interrupt)
        
    def _on_enqueue(self, text: str):
        self.tts_queue.put(text)
        
    def _on_interrupt(self, _=None):
        self.engine.interrupt()
        # Clear the queue
        while not self.tts_queue.empty():
            try:
                self.tts_queue.get_nowait()
            except queue.Empty:
                break
                
    def run(self):
        logger.info("Starting TTSWorker thread...")
        while True:
            try:
                text = self.tts_queue.get()
                if text:
                    logger.debug(f"Speaking: {text}")
                    self.engine.speak(text)
                self.tts_queue.task_done()
            except Exception as e:
                logger.error(f"Error in TTSWorker loop: {e}")
