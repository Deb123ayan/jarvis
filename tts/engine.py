from kokoro_onnx import Kokoro
import sounddevice as sd
import threading
from loguru import logger
from core.config import config
from pathlib import Path

class TTSEngine:
    def __init__(self):
        # Resolve models dir relative to root
        base_dir = Path(__file__).parent.parent
        onnx_path = base_dir / config.get("models.kokoro_onnx", "models/kokoro-v1.0.onnx")
        voices_path = base_dir / config.get("models.kokoro_voices", "models/voices.bin")
        self.voice = config.get("models.tts_voice", "af_heart")
        
        logger.info(f"Loading Kokoro ONNX from {onnx_path}")
        try:
            self.kokoro = Kokoro(str(onnx_path), str(voices_path))
            self._available = True
        except Exception as e:
            logger.error(f"Failed to load Kokoro ONNX: {e}")
            self._available = False
            
        self._stop_flag = threading.Event()
        self.output_device = config.get("perception.output_device_index", None)
        
    def speak(self, text: str):
        if not self._available:
            logger.warning("TTS not available, skipping speech.")
            return
            
        text = self._clean(text)
        if not text:
            return
            
        try:
            samples, sr = self.kokoro.create(text, voice=self.voice, speed=1.0)
            self._stop_flag.clear()
            
            # Use sounddevice to play
            sd.play(samples, sr, device=self.output_device)
            
            # Wait for playback to finish or be interrupted
            while sd.get_stream() and sd.get_stream().active:
                if self._stop_flag.is_set():
                    sd.stop()
                    break
                sd.sleep(50)
        except Exception as e:
            logger.error(f"TTS Error: {e}")
            
    def interrupt(self):
        logger.info("Interrupting TTS playback...")
        self._stop_flag.set()
        
    def _clean(self, text: str) -> str:
        # Strip LLM filler before speaking
        STRIP = ["Certainly!", "Of course!", "Sure thing!", "Great question!",
                 "Absolutely!", "I'd be happy to", "As an AI"]
        for phrase in STRIP:
            text = text.replace(phrase, "")
        return text.strip()
