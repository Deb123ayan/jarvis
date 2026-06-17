import threading
import time
import collections
import numpy as np
import pyaudio
from openwakeword.model import Model
from loguru import logger
from core.events import bus, Event
from core.config import config

# Publish live confidence score so dashboard can display a bar
# We re-use CONTEXT_CHANGED with a float payload to avoid adding a new Event
WAKE_SCORE_EVENT = "_wake_score"  # informal, not in enum

class WakeWordListener(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.model_name = config.get("perception.wake_word", "hey_mycroft")
        self.input_device = config.get("perception.input_device_index", None)
        
        # Audio parameters matching openwakeword requirements
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.CHUNK = 1280
        
        # Ring buffer for 2 seconds of audio
        self.num_chunks = int((self.RATE * 2) / self.CHUNK)
        self.ring_buffer = collections.deque(maxlen=self.num_chunks)
        
        self.consecutive_frames = 0
        self.cooldown_until = 0
        self._stop_event = threading.Event()
        self._resume_event = threading.Event()
        
        # Load model
        logger.info(f"Loading OpenWakeWord model: {self.model_name}")
        self.oww_model = Model(wakeword_models=[self.model_name], inference_framework="onnx")
        
        bus.subscribe(Event.AUDIO_CAPTURED, self._on_audio_captured)

    def _on_audio_captured(self, _):
        self._resume_event.set()

    def stop(self):
        self._stop_event.set()

    def run(self):
        logger.info("Starting WakeWordListener thread...")
        audio = pyaudio.PyAudio()
        
        while not self._stop_event.is_set():
            try:
                stream = audio.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    input_device_index=self.input_device,
                    frames_per_buffer=self.CHUNK
                )
                logger.info("Microphone stream opened for wake word detection.")
            except Exception as e:
                logger.error(f"Failed to open microphone: {e}")
                time.sleep(1.0)
                continue

            while not self._stop_event.is_set() and not self._resume_event.is_set():
                try:
                    pcm = stream.read(self.CHUNK, exception_on_overflow=False)
                    # Store raw bytes in ring buffer
                    self.ring_buffer.append(pcm)
                    
                    # Convert to numpy array for openwakeword
                    audio_data = np.frombuffer(pcm, dtype=np.int16)
                    
                    # Predict
                    prediction = self.oww_model.predict(audio_data)
                    
                    score = 0.0
                    for k, v in prediction.items():
                        if self.model_name in k:
                            score = v
                            break

                    # Broadcast live score for dashboard
                    bus.publish(Event.CONTEXT_CHANGED, {"wake_score": float(score)})

                    current_time = time.time()
                    if current_time < self.cooldown_until:
                        self.consecutive_frames = 0
                        continue

                    if score > 0.7:
                        self.consecutive_frames += 1
                    else:
                        self.consecutive_frames = 0

                    if self.consecutive_frames >= 3:
                        logger.success(f"Wake word detected! Score: {score:.2f}")
                        audio_buffer = b"".join(self.ring_buffer)
                        bus.publish(Event.WAKE_DETECTED, audio_buffer)

                        self.consecutive_frames = 0
                        self._resume_event.clear()
                        break # Break to close stream and wait
                        
                except Exception as e:
                    logger.error(f"Error in wake word loop: {e}")
                    time.sleep(0.1)

            stream.stop_stream()
            stream.close()

            if not self._stop_event.is_set():
                logger.info("WakeWordListener paused, releasing mic to STT...")
                self._resume_event.wait()
                self._resume_event.clear()
                self.ring_buffer.clear()
                self.cooldown_until = time.time() + 2.0

        audio.terminate()
        logger.info("WakeWordListener stopped.")
