"""Barge-in Detection Engine

Detects user speech during TTS playback to interrupt and resume conversation.
Uses energy-based voice activity detection optimized for real-time latency.
"""

import asyncio
import logging
import numpy as np
from typing import Optional, Callable, Dict
from dataclasses import dataclass
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class BargeinConfig:
    """Barge-in Detection Configuration"""
    # Energy threshold for voice detection (dB)
    energy_threshold: float = -40.0
    # Minimum duration for valid barge-in (ms)
    min_duration: float = 300.0
    # Sensitivity (0.0 - 1.0, higher = more sensitive)
    sensitivity: float = 0.6
    # Sample rate for audio analysis (Hz)
    sample_rate: int = 24000
    # Frame duration for analysis (ms)
    frame_duration: float = 20.0
    # Enable adaptive threshold
    adaptive_threshold: bool = True
    # Noise floor estimation window (seconds)
    noise_floor_window: float = 2.0

class BargeinDetector:
    """Real-time barge-in detection engine"""
    
    def __init__(self, config: Optional[BargeinConfig] = None):
        """Initialize Barge-in Detector
        
        Args:
            config: BargeinConfig object
        """
        self.config = config or BargeinConfig()
        self.logger = logger
        self.is_detecting = False
        self.callbacks: Dict[str, list[Callable]] = {
            'on_speech_detected': [],
            'on_speech_ended': [],
            'on_energy_update': []
        }
        
        # Audio history for analysis
        self.frame_size = int(
            self.config.sample_rate * self.config.frame_duration / 1000
        )
        self.audio_buffer = deque(maxlen=int(
            self.config.sample_rate * self.config.noise_floor_window
        ))
        
        # Detection state
        self.speech_start_time = None
        self.is_speech_detected = False
        self.noise_floor = self.config.energy_threshold
        self.peak_energy = -np.inf
        
    async def process_audio(self, audio_data: bytes) -> None:
        """Process audio chunk for barge-in detection
        
        Args:
            audio_data: Raw PCM audio bytes
        """
        try:
            # Convert bytes to numpy array (16-bit PCM)
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            
            # Normalize to [-1, 1] range
            audio_array = audio_array / 32768.0
            
            # Add to buffer
            self.audio_buffer.extend(audio_array)
            
            # Calculate frame energy (RMS)
            frame_energy_db = self._calculate_energy(audio_array)
            
            # Update noise floor (continuous estimation)
            if self.config.adaptive_threshold:
                self._update_noise_floor(frame_energy_db)
            
            # Get detection threshold
            threshold = self._get_detection_threshold()
            
            # Detect speech
            is_speech = frame_energy_db > threshold
            
            # Handle speech state transitions
            if is_speech and not self.is_speech_detected:
                self.speech_start_time = datetime.now()
                self.is_speech_detected = True
                self.logger.debug(f"Speech detected: {frame_energy_db:.1f}dB > {threshold:.1f}dB")
                
                # Trigger callbacks
                for callback in self.callbacks['on_speech_detected']:
                    try:
                        await callback(frame_energy_db)
                    except Exception as e:
                        self.logger.error(f"Error in speech detection callback: {str(e)}")
            
            elif not is_speech and self.is_speech_detected:
                # Check if duration is valid
                if self.speech_start_time:
                    duration_ms = (
                        datetime.now() - self.speech_start_time
                    ).total_seconds() * 1000
                    
                    if duration_ms >= self.config.min_duration:
                        self.is_speech_detected = False
                        self.logger.debug(f"Speech ended: {duration_ms:.0f}ms")
                        
                        # Trigger callbacks
                        for callback in self.callbacks['on_speech_ended']:
                            try:
                                await callback(duration_ms)
                            except Exception as e:
                                self.logger.error(f"Error in speech end callback: {str(e)}")
                    # else: too short, ignore
            
            # Energy update callback (for monitoring)
            for callback in self.callbacks['on_energy_update']:
                try:
                    await callback(frame_energy_db, threshold)
                except Exception as e:
                    self.logger.error(f"Error in energy update callback: {str(e)}")
        
        except Exception as e:
            self.logger.error(f"Error processing audio in barge-in: {str(e)}")
    
    def _calculate_energy(self, audio_array: np.ndarray) -> float:
        """Calculate energy of audio frame in dB
        
        Args:
            audio_array: Audio samples
            
        Returns:
            Energy in dB
        """
        # Root mean square (RMS)
        rms = np.sqrt(np.mean(np.square(audio_array)))
        
        # Avoid log(0)
        if rms < 1e-10:
            return -np.inf
        
        # Convert to dB (reference = 1.0)
        energy_db = 20.0 * np.log10(rms)
        
        return energy_db
    
    def _update_noise_floor(self, frame_energy_db: float) -> None:
        """Update estimated noise floor
        
        Args:
            frame_energy_db: Current frame energy
        """
        # Exponential moving average
        alpha = 0.05  # Smoothing factor
        
        if not self.is_speech_detected:
            # Only update when no speech is detected
            self.noise_floor = (
                alpha * frame_energy_db + (1 - alpha) * self.noise_floor
            )
    
    def _get_detection_threshold(self) -> float:
        """Calculate adaptive detection threshold
        
        Returns:
            Detection threshold in dB
        """
        if self.config.adaptive_threshold:
            # Threshold is noise_floor + sensitivity offset
            sensitivity_offset = (1.0 - self.config.sensitivity) * 20.0
            threshold = self.noise_floor + sensitivity_offset
        else:
            threshold = self.config.energy_threshold
        
        return max(threshold, -60.0)  # Minimum threshold
    
    def register_callback(self, event: str, callback: Callable) -> None:
        """Register callback for barge-in events
        
        Args:
            event: Event name
            callback: Async callback function
        """
        if event in self.callbacks:
            self.callbacks[event].append(callback)
            self.logger.info(f"Registered callback for {event}")
    
    async def reset(self) -> None:
        """Reset detection state"""
        self.is_speech_detected = False
        self.speech_start_time = None
        self.audio_buffer.clear()
        self.logger.debug("Barge-in detector reset")
    
    async def get_status(self) -> Dict:
        """Get detector status
        
        Returns:
            Status dictionary
        """
        return {
            "is_detecting": self.is_detecting,
            "is_speech_detected": self.is_speech_detected,
            "noise_floor_db": round(self.noise_floor, 1),
            "threshold_db": round(self._get_detection_threshold(), 1),
            "sensitivity": self.config.sensitivity,
            "buffer_size": len(self.audio_buffer),
            "frame_size": self.frame_size
        }

# Singleton instance
_bargein_instance: Optional[BargeinDetector] = None

async def get_bargein_detector(config: Optional[BargeinConfig] = None) -> BargeinDetector:
    """Get or create barge-in detector instance"""
    global _bargein_instance
    if _bargein_instance is None:
        _bargein_instance = BargeinDetector(config)
    return _bargein_instance

async def shutdown_bargein_detector() -> None:
    """Shutdown barge-in detector"""
    global _bargein_instance
    if _bargein_instance:
        await _bargein_instance.reset()
        _bargein_instance = None
