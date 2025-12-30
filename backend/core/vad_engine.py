backend/core/vad_engine.py"""
Voice Activity Detection (VAD) Engine
Based on Silero VAD v5.2.1 for streaming real-time detection
"""

import io
import logging
from typing import Optional, Tuple, List
from dataclasses import dataclass
import torch
import numpy as np
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class VADConfig:
    """Configuration for VAD Engine"""
    model_path: Optional[str] = None
    sample_rate: int = 16000
    speech_threshold: float = 0.6  # Confidence threshold for speech
    min_speech_duration_ms: int = 250  # Minimum duration for speech segment
    min_silence_duration_ms: int = 100  # Minimum duration for silence gap
    max_speech_duration_ms: int = 300000  # Maximum duration for speech
    device: str = "cpu"  # "cuda" or "cpu"
    num_workers: int = 1
    
    def to_dict(self) -> dict:
        return {
            'model_path': self.model_path,
            'sample_rate': self.sample_rate,
            'speech_threshold': self.speech_threshold,
            'min_speech_duration_ms': self.min_speech_duration_ms,
            'min_silence_duration_ms': self.min_silence_duration_ms,
            'max_speech_duration_ms': self.max_speech_duration_ms,
            'device': self.device,
            'num_workers': self.num_workers,
        }


@dataclass
class VADResult:
    """Result from VAD inference"""
    has_speech: bool  # True if speech detected
    confidence: float  # Confidence score (0-1)
    start_time_ms: Optional[float] = None  # Start time of speech segment
    end_time_ms: Optional[float] = None  # End time of speech segment
    duration_ms: float = 0.0  # Duration of current audio chunk


class SileroVADEngine:
    """Silero VAD Engine for real-time voice activity detection
    
    Supports streaming audio processing with configurable thresholds.
    Detects speech/silence with <1ms latency per frame.
    """
    
    def __init__(self, config: VADConfig):
        """
        Initialize Silero VAD Engine
        
        Args:
            config: VADConfig object with model and processing settings
        """
        self.config = config
        self.device = torch.device(config.device)
        
        # Load Silero VAD model
        try:
            # Use torch hub to download model
            self.model, self.utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False,
                device=self.device
            )
            self.model.eval()
            logger.info(f"Silero VAD model loaded successfully on {self.device}")
        except Exception as e:
            logger.error(f"Failed to load Silero VAD model: {e}")
            raise
        
        # Extract utilities
        (self.get_speech_ts,
         self.save_audio,
         self.read_audio,
         self.VADIterator,
         self.collect_chunks) = self.utils
        
        # State tracking for streaming
        self.speech_segments: List[Tuple[int, int]] = []
        self.current_segment_start: Optional[int] = None
        self.last_chunk_end: int = 0
        self.frame_idx: int = 0
        self.speech_chunks: List[np.ndarray] = []
        
        logger.info(f"VAD Engine initialized with config: {config.to_dict()}")
    
    def reset(self):
        """Reset streaming state"""
        self.speech_segments = []
        self.current_segment_start = None
        self.last_chunk_end = 0
        self.frame_idx = 0
        self.speech_chunks = []
        logger.debug("VAD state reset")
    
    def process_chunk(self, audio_chunk: np.ndarray) -> VADResult:
        """
        Process a single audio chunk for voice activity
        
        Args:
            audio_chunk: Audio data (numpy array, 16-bit PCM)
            Expected shape: (num_samples,) for mono audio at 16kHz
        
        Returns:
            VADResult with speech detection information
        """
        if audio_chunk is None or len(audio_chunk) == 0:
            return VADResult(has_speech=False, confidence=0.0)
        
        try:
            # Convert to torch tensor
            if isinstance(audio_chunk, np.ndarray):
                audio_tensor = torch.from_numpy(audio_chunk).float()
            else:
                audio_tensor = torch.tensor(audio_chunk, dtype=torch.float32)
            
            # Normalize audio if needed (convert 16-bit PCM to [-1, 1])
            if audio_tensor.max() > 1.0:
                audio_tensor = audio_tensor / 32768.0
            
            # Move to device
            audio_tensor = audio_tensor.to(self.device)
            
            # Run VAD inference
            with torch.no_grad():
                confidence = self.model(audio_tensor, self.config.sample_rate).item()
            
            # Determine if speech is detected
            has_speech = confidence >= self.config.speech_threshold
            
            # Calculate timing information
            chunk_duration_ms = (len(audio_chunk) / self.config.sample_rate) * 1000
            start_time_ms = (self.frame_idx * len(audio_chunk) / self.config.sample_rate) * 1000
            end_time_ms = start_time_ms + chunk_duration_ms
            
            # Track speech segments
            if has_speech:
                if self.current_segment_start is None:
                    self.current_segment_start = int(start_time_ms)
                    logger.debug(f"Speech segment started at {start_time_ms:.0f}ms")
                self.speech_chunks.append(audio_chunk)
            else:
                if self.current_segment_start is not None:
                    # Check if silence is long enough to end segment
                    silence_duration = int(start_time_ms) - self.last_chunk_end
                    if silence_duration >= self.config.min_silence_duration_ms:
                        segment_end = int(start_time_ms)
                        self.speech_segments.append(
                            (self.current_segment_start, segment_end)
                        )
                        logger.debug(
                            f"Speech segment ended: "
                            f"{self.current_segment_start}-{segment_end}ms"
                        )
                        self.current_segment_start = None
                        self.speech_chunks = []
            
            self.last_chunk_end = int(end_time_ms)
            self.frame_idx += 1
            
            return VADResult(
                has_speech=has_speech,
                confidence=confidence,
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                duration_ms=chunk_duration_ms
            )
            
        except Exception as e:
            logger.error(f"Error processing VAD chunk: {e}")
            return VADResult(has_speech=False, confidence=0.0)
    
    def process_audio_batch(self, audio: np.ndarray) -> List[VADResult]:
        """
        Process entire audio batch and return all chunks
        
        Args:
            audio: Full audio array (num_samples,)
        
        Returns:
            List of VADResult for each processed chunk
        """
        chunk_size = int(0.512 * self.config.sample_rate)  # 512ms chunks
        results = []
        
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i + chunk_size]
            if len(chunk) > 0:
                result = self.process_chunk(chunk)
                results.append(result)
        
        return results
    
    def get_speech_segments(self) -> List[Tuple[int, int]]:
        """Get detected speech segments (start_ms, end_ms)"""
        return self.speech_segments
    
    def get_speech_audio(self, audio: np.ndarray) -> np.ndarray:
        """Extract only speech portions from audio"""
        if not self.speech_chunks:
            return np.array([])
        return np.concatenate(self.speech_chunks)
    
    def __repr__(self) -> str:
        return f"SileroVADEngine(device={self.device}, sample_rate={self.config.sample_rate}Hz)"


# Factory function for easy initialization
def create_vad_engine(config: Optional[VADConfig] = None) -> SileroVADEngine:
    """Create and initialize a VAD engine with default or custom config"""
    if config is None:
        config = VADConfig()
    return SileroVADEngine(config)
