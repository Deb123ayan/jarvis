import threading
import time
import numpy as np
import pyaudio
from faster_whisper import WhisperModel
from loguru import logger
from core.events import bus, Event
from core.config import config

class VoicePipeline(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.model_size = config.get("models.stt", "small.en")
        self.input_device = config.get("perception.input_device_index", None)
        
        logger.info(f"Loading Whisper model: {self.model_size}")
        try:
            # Try loading with CUDA if available
            self.model = WhisperModel(self.model_size, device="cuda", compute_type="float16")
        except Exception as e:
            logger.warning(f"CUDA loading failed, falling back to CPU: {e}")
            self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.CHUNK = 1024
        
        self.audio = pyaudio.PyAudio()
        
        self.SILENCE_THRESHOLD = 500  # Adjust as needed based on mic noise floor
        self.SILENCE_DURATION = 1.5   # Stop after 1.5s of silence
        
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._ring_buffer = b""
        
        bus.subscribe(Event.WAKE_DETECTED, self._on_wake)

    def _on_wake(self, audio_buffer):
        self._ring_buffer = audio_buffer
        self._wake_event.set()
        
    def stop(self):
        self._stop_event.set()
        self._wake_event.set()

    def run(self):
        logger.info("Starting VoicePipeline thread...")
        while not self._stop_event.is_set():
            self._wake_event.wait()
            if self._stop_event.is_set():
                break
                
            self._wake_event.clear()
            logger.info("VoicePipeline active, capturing command...")
            
            # Play a chime or interrupt TTS
            bus.publish(Event.TTS_INTERRUPT, None)
            
            try:
                stream = self.audio.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    input_device_index=self.input_device,
                    frames_per_buffer=self.CHUNK
                )
                
                frames = [self._ring_buffer]
                silent_chunks = 0
                max_silent_chunks = int(self.RATE / self.CHUNK * self.SILENCE_DURATION)
                
                # Maximum recording time 15 seconds
                max_chunks = int(self.RATE / self.CHUNK * 15)
                chunks_recorded = 0
                
                while chunks_recorded < max_chunks:
                    data = stream.read(self.CHUNK, exception_on_overflow=False)
                    frames.append(data)
                    chunks_recorded += 1
                    
                    rms = int(np.sqrt(np.mean(np.frombuffer(data, dtype=np.int16).astype(np.float32) ** 2)))
                    if rms < self.SILENCE_THRESHOLD:
                        silent_chunks += 1
                    else:
                        silent_chunks = 0
                        
                    if silent_chunks > max_silent_chunks:
                        break
                        
                stream.stop_stream()
                stream.close()
                
                # Signal that STT is done with the microphone
                bus.publish(Event.AUDIO_CAPTURED, None)
                
                logger.info("Command captured, transcribing...")
                audio_data = b"".join(frames)
                
                # Convert to numpy array float32 in range [-1, 1] for faster-whisper
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                
                segments, info = self.model.transcribe(
                    audio_np,
                    language="en",
                    beam_size=1,
                    vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 600, "threshold": 0.5}
                )
                
                transcript = " ".join([segment.text for segment in segments]).strip()
                
                if transcript:
                    logger.success(f"Transcript: {transcript}")
                    bus.publish(Event.TRANSCRIPT_READY, transcript)
                else:
                    logger.warning("Empty transcript or unintelligible audio.")
                
            except Exception as e:
                logger.error(f"Error in VoicePipeline: {e}")
                bus.publish(Event.AUDIO_CAPTURED, None)
