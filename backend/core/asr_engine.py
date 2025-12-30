"""
Automtic Speech Recognition (ASR) Engine
Model: Whisper-large-v3-turbo with response streaming
Framework: OpenAI Whisper
Purpose: Real-time speech-to-text conversion for Viva Voce Examiner
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any
import numpy as np
import torch
try:
    from transformers import WhisperProcessor, WhisperForConditionalGeneration
except ImportError:
    raise ImportError("Install transformers: pip install transformers torch")

logger = logging.getLogger(__name__)


@dataclass
class ASRConfig:
    """Configuration for Whisper ASR Engine"""
    model_name: str = "openai/whisper-large-v3-turbo"
    sample_rate: int = 16000
    language: str = "en"
    task: str = "transcribe"
    device: Optional[str] = None
    dtype: torch.dtype = torch.float32
    chunk_length_s: float = 30.0
    stride_length_s: float = 5.0
    max_new_tokens: int = 128
    num_beams: int = 1
    temperature: float = 0.0


@dataclass
class ASRResult:
    """Output from ASR engine"""
    text: str
    language: str
    confidence: float
    duration_ms: float
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    is_complete: bool = True


class WhisperASREngine:
    """Production-grade Whisper ASR engine for real-time transcription"""

    def __init__(self, config: Optional[ASRConfig] = None):
        """Initialize ASR engine with Whisper model"""
        self.config = config or ASRConfig()
        self._setup_device()
        self._load_model()
        logger.info(f"Whisper ASR Engine initialized on {self.device}")

    def _setup_device(self):
        """Setup GPU/CPU device"""
        if self.config.device:
            self.device = self.config.device
        else:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")

    def _load_model(self):
        """Load Whisper model and processor"""
        try:
            logger.info(f"Loading {self.config.model_name}...")
            self.processor = WhisperProcessor.from_pretrained(self.config.model_name)
            self.model = WhisperForConditionalGeneration.from_pretrained(
                self.config.model_name,
                torch_dtype=self.config.dtype,
                low_cpu_mem_usage=True,
                use_safetensors=True
            ).to(self.device)
            self.model.eval()
            logger.info(f"Model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise

    def process_chunk(self, audio_chunk: np.ndarray) -> ASRResult:
        """Process audio chunk and return transcription
        
        Args:
            audio_chunk: Audio data (16kHz mono PCM, float32 [-1.0, 1.0])
            
        Returns:
            ASRResult with transcribed text and confidence
        """
        try:
            start_time = np.datetime64('now')
            
            # Prepare audio for model
            inputs = self.processor(
                audio_chunk,
                sampling_rate=self.config.sample_rate,
                return_tensors="pt"
            ).to(self.device)
            
            # Generate transcription
            with torch.no_grad():
                predicted_ids = self.model.generate(
                    inputs["input_features"],
                    max_new_tokens=self.config.max_new_tokens,
                    num_beams=self.config.num_beams,
                    temperature=self.config.temperature,
                    language="<|en|>",
                    task="transcribe"
                )
            
            # Decode and return result
            transcription = self.processor.batch_decode(
                predicted_ids,
                skip_special_tokens=True
            )[0].strip()
            
            end_time = np.datetime64('now')
            duration_ms = float((end_time - start_time) / np.timedelta64(1, 'ms'))
            
            confidence = self._compute_confidence(predicted_ids)
            
            return ASRResult(
                text=transcription,
                language=self.config.language,
                confidence=confidence,
                duration_ms=duration_ms,
                is_complete=len(transcription.split()) > 0
            )
        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            return ASRResult(
                text="",
                language=self.config.language,
                confidence=0.0,
                duration_ms=0.0,
                is_complete=False
            )

    def process_audio_batch(self, audio_data: np.ndarray) -> List[ASRResult]:
        """Process audio data in chunks
        
        Args:
            audio_data: Full audio data
            
        Returns:
            List of ASRResult objects for each chunk
        """
        results = []
        chunk_samples = int(self.config.chunk_length_s * self.config.sample_rate)
        stride_samples = int(self.config.stride_length_s * self.config.sample_rate)
        
        for start in range(0, len(audio_data), stride_samples):
            end = min(start + chunk_samples, len(audio_data))
            chunk = audio_data[start:end]
            
            if len(chunk) > 0:
                result = self.process_chunk(chunk)
                results.append(result)
        
        return results

    def stream_transcribe(self, audio_chunks: List[np.ndarray]):
        """Stream transcription from audio chunks (generator)
        
        Yields:
            ASRResult for each processed chunk
        """
        for chunk in audio_chunks:
            yield self.process_chunk(chunk)

    def _compute_confidence(self, predicted_ids) -> float:
        """Compute confidence score (0.0-1.0)"""
        # Simplified confidence computation
        # In production, use log probabilities from model
        if predicted_ids is not None and len(predicted_ids) > 0:
            return min(0.95, 0.85 + (len(predicted_ids[0]) / 100) * 0.1)
        return 0.0

    def __repr__(self) -> str:
        return f"WhisperASREngine(model={self.config.model_name}, device={self.device})"


def create_asr_engine(config: Optional[ASRConfig] = None) -> WhisperASREngine:
    """Factory function for ASR engine initialization
    
    Args:
        config: ASRConfig instance or None for defaults
        
    Returns:
        Initialized WhisperASREngine instance
    """
    return WhisperASREngine(config)


def bytes_to_audio(audio_bytes: bytes, sample_rate: int = 16000) -> np.ndarray:
    """Convert byte stream to numpy audio array
    
    Args:
        audio_bytes: Raw audio bytes
        sample_rate: Sample rate in Hz
        
    Returns:
        Numpy array of audio samples
    """
    try:
        audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        return audio_data
    except Exception as e:
        logger.error(f"Error converting bytes to audio: {e}")
        return np.array([], dtype=np.float32)
