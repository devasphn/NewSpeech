# Phase 7: WebSocket & Barge-in Integration Documentation

## Overview
Phase 7 implements real-time bidirectional communication via WebSocket and intelligent interruption detection for continuous conversation flow. The pipeline now supports full duplex audio streaming with barge-in (user speech interrupts TTS).

## Module 1: WebSocket Engine (`backend/core/websocket_engine.py`)

### Features
- **Production WebSocket Server**: Async implementation using `websockets` library
- **Client Management**: UUID-based connection tracking with automatic cleanup
- **Message Types**: Audio (binary), Text (JSON), Control (JSON), Barge-in (JSON)
- **Callbacks**: Event-driven architecture (on_connect, on_audio, on_text, on_barge_in, on_disconnect)
- **Broadcast**: Multi-client audio streaming with selective exclusion
- **Heartbeat**: Ping/pong for connection health monitoring
- **RunPod Optimized**: 10MB max message, compression disabled, low latency

### Classes

**WebSocketConfig**
```python
host: str = "0.0.0.0"
port: int = 8765
max_connections: int = 100
buffer_size: int = 4096  # 4KB chunks
heartbeat_interval: float = 30.0
connection_timeout: float = 60.0
enable_barge_in: bool = True
audio_format: str = "pcm16"
sample_rate: int = 24000
```

**WebSocketEngine**
- `async start()` - Start server
- `async handle_connection(websocket, path)` - Connection handler
- `async process_message()` - Message routing
- `async send_message(client_id, message)` - Unicast
- `async broadcast_audio(audio_data)` - Multicast
- `register_callback(event, callback)` - Event subscription
- `async get_status()` - Server status
- `async shutdown()` - Graceful shutdown

**ClientConnection**
- Manages per-client state (buffer, bytes sent/received, connection time)
- Automatic cleanup on disconnect

### Integration Points
```
Client Browser (WebSocket Client)
    ↓ (WebSocket: wss://server:8765)
WebSocketEngine
    ↓
Callback: on_audio → VoiceActivityDetection
Callback: on_barge_in → TTS Interrupt
Callback: on_text → LLM Processing
```

## Module 2: Barge-in Detector (`backend/core/bargein_engine.py`)

### Features
- **Energy-Based VAD**: RMS (Root Mean Square) analysis in dB
- **Adaptive Threshold**: Auto-adjusts to noise floor
- **Real-time Processing**: 20ms frames at 24kHz (480 samples)
- **Configurable Sensitivity**: 0.0 (least) to 1.0 (most sensitive)
- **Minimum Duration**: 300ms to avoid false positives
- **Noise Floor Estimation**: 2-second window with exponential moving average

### Classes

**BargeinConfig**
```python
energy_threshold: float = -40.0 dB  # Default threshold
min_duration: float = 300.0 ms      # Min speech length
sensitivity: float = 0.6            # Adaptiveness
sample_rate: int = 24000 Hz
frame_duration: float = 20.0 ms
adaptive_threshold: bool = True
noise_floor_window: float = 2.0 s
```

**BargeinDetector**
- `async process_audio(audio_data)` - Real-time VAD
- `_calculate_energy(audio_array)` - RMS→dB conversion
- `_update_noise_floor(frame_energy)` - Adaptive baseline
- `_get_detection_threshold()` - Sensitivity-weighted threshold
- `register_callback(event, callback)` - Subscribe to events
- `async reset()` - Clear state
- `async get_status()` - Detector metrics

### Callbacks
- `on_speech_detected(energy_db)` - User started speaking
- `on_speech_ended(duration_ms)` - User stopped speaking
- `on_energy_update(energy_db, threshold_db)` - Per-frame monitoring

### Energy Calculation
```
RMS = sqrt(mean(audio_samples²))
Energy[dB] = 20 * log10(RMS)

Threshold = NoiseFloor + (1.0 - Sensitivity) * 20dB
```

## Full Pipeline Integration

```
┌─────────────────────────────────────────────┐
│ Client Browser (WebSocket)                  │
├─────────────────────────────────────────────┤
│ ↓ Audio Stream (24kHz PCM)                  │
│ ↓ Text Input (JSON)                         │
└──────────────────┬──────────────────────────┘
                   ↓
         ┌─────────────────────┐
         │ WebSocket Engine    │
         └──────────┬──────────┘
                    ↓
      ┌─────────────────────────────┐
      │ Message Processing          │
      ├─────────────────────────────┤
      │ • Audio → Barge-in Detector │
      │ • Text → LLM Engine         │
      │ • Control → Session Mgmt    │
      └──────────┬──────────────────┘
                 ↓
    ┌────────────────────────┐
    │ VAD Result: Speech?    │
    └──────────┬─────────────┘
              YES ↓ NO
               ↓   ↓
         Interrupt  Continue
          TTS      TTS
           ↓        ↓
           └────────┴─────────────┐
                                  ↓
                         ┌────────────────┐
                         │ TTS Streaming  │
                         │ (VibeVoice)    │
                         └────────┬───────┘
                                  ↓
                         Audio → WebSocket
                                  ↓
                    Client Playback + Monitoring
```

## Performance Targets

| Metric | Target | Implementation |
|--------|--------|----------------|
| WebSocket Latency | <50ms | No compression, direct send |
| Barge-in Detection | <100ms | 20ms frames, energy analysis |
| Audio Chunk Delay | 10-20ms | Streaming generator |
| Connection Setup | <200ms | Async handshake |
| Full RTT (Client→Server→TTS→Client) | <300ms | Pipelined async |

## Testing Checklist

### WebSocket Engine
- [x] Server starts on port 8765
- [x] Client connections accepted
- [x] Multiple concurrent clients
- [x] Message routing (audio, text, control)
- [x] Callback invocation
- [x] Broadcast functionality
- [x] Graceful shutdown
- [ ] Load testing (100+ clients)
- [ ] Network failure recovery

### Barge-in Detector
- [x] RMS energy calculation
- [x] Adaptive noise floor
- [x] Speech detection
- [x] Minimum duration validation
- [x] Callback invocation
- [x] State reset
- [ ] Real-time latency measurement
- [ ] Accuracy testing with test audio
- [ ] Sensitivity calibration

## Known Limitations

1. **Queue Management**: No queue for sequential Q&A yet (Phase 8)
2. **Session State**: Minimal session tracking (database pending Phase 9)
3. **Error Recovery**: Basic error handling; needs retry logic
4. **Scaling**: Single server instance; horizontal scaling needed
5. **Authentication**: No client authentication (security Phase 10)

## Next Phase (Phase 8): Viva Engine

### Objectives
- Q&A session orchestration
- Question/scenario management  
- Answer evaluation
- Feedback generation
- Score calculation
- Report compilation

### Expected Duration
- Design: 20 min
- Implementation: 60 min
- Testing: 20 min
- **Total: ~100 min**

## Deployment Notes

### RunPod Configuration
```bash
# Start WebSocket server (port 8765)
python -m backend.core.websocket_engine

# Client connection
ws://runpod_ip:8765
```

### Dependencies
```bash
pip install websockets>=11.0
numpy>=1.24.0
```

## Code Quality
✅ Full async/await implementation  
✅ Comprehensive docstrings  
✅ Error handling with logging  
✅ Type hints throughout  
✅ Singleton patterns  
✅ Resource cleanup  

---

**Phase 7 Status**: ✅ Complete  
**Repository Progress**: 7/14 phases (50%)  
**Total Lines Added**: 316 (WS: 316, Barge-in: 238)
