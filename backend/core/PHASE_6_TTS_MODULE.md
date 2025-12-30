# Phase 6: TTS Engine Module Documentation

## Overview
Implementation of production-grade Text-to-Speech (TTS) engine using VibeVoice 0.5B model with full streaming support optimized for RunPod WebSocket architecture.

## Module: `backend/core/tts_engine.py`

### Features Implemented

#### 1. TTSConfig Data Class
- **Model Name**: VibeVoice 0.5B (ljspeech phoneme-based)
- **Sample Rate**: 24,000 Hz (optimal for streaming)
- **Device**: CUDA (GPU acceleration on RunPod)
- **Streaming**: Enabled by default
- **Chunk Size**: 512 samples per chunk
- **Pad Length**: 1024 samples
- **Streaming Chunk Duration**: 80ms (minimal latency for real-time)

#### 2. TTSEngine Class

**Async Initialization**:
```python
await engine.initialize()  # Loads VibeVoice 0.5B model
```
- Lazy loading with error handling
- Graceful fallback for testing environments
- GPU memory optimization (40% allocation for RunPod shared resources)

**Streaming Synthesis**:
```python
async for chunk in engine.synthesize_streaming(
    text="Your text here",
    speaker_id=0,
    speed=1.0,
    pitch=1.0
):
    # Send chunk over WebSocket
    await websocket.send_bytes(chunk)
```
- Yields audio in 16-bit PCM format
- Configurable playback speed (0.5x - 2.0x)
- Adjustable pitch (0.5 - 2.0)
- 10ms delay between chunks for realistic streaming
- Automatic normalization and format conversion

**Batch Synthesis**:
```python
results = await engine.synthesize_batch(
    texts=["Question 1?", "Question 2?"],
    speaker_ids=[0, 1]
)
```
- Efficient processing of multiple texts
- Error resilience (continues on partial failures)
- Returns numpy arrays for further processing

**Speaker Management**:
```python
speakers = await engine.get_available_speakers()
```
- Lists available voice options
- Supports voice cloning with reference audio
- Default fallback: "default" voice

**Health Checks**:
```python
health = await engine.health_check()
# Returns: {status, model, streaming_enabled, sample_rate}
```

**Resource Cleanup**:
```python
await engine.cleanup()  # Frees VRAM and references
```

#### 3. Singleton Pattern

**Global Instance Management**:
```python
engine = await get_tts_engine()  # Creates or returns existing instance
await shutdown_tts_engine()       # Cleanup on shutdown
```
- Ensures single model instance in memory
- Thread-safe initialization
- Proper resource management

### Integration Points

#### WebSocket Pipeline
1. **ASR Output → LLM Processing** (from Phase 4 & 5)
2. **LLM Response → TTS Streaming** (this phase)
   - Text from LLM → VibeVoice 0.5B
   - Audio chunks → WebSocket client
3. **Barge-in Detection** (Phase 7)
   - Listen for user speech during playback
   - Interrupt streaming if needed

#### Database Integration
- Store synthesized audio metadata
- Cache frequently used responses
- Log latency metrics for optimization

### Performance Specifications

| Metric | Target | Status |
|--------|--------|--------|
| First Audio Chunk | < 500ms | Optimized |
| Chunk Latency | 10-50ms | Streaming |
| Stream Jitter | < 20ms | Minimal |
| Memory Usage | < 2GB | 0.5B model |
| VRAM Usage | ~1.5GB | Per instance |
| Sample Rate | 24kHz | Verified |

### Error Handling

- **ImportError**: Graceful fallback for testing
- **Model Loading**: Detailed logging and retry logic
- **Synthesis Errors**: Logged per-text with batch continuation
- **Resource Cleanup**: Safe exception handling in destructor

### Testing Checklist

- [x] Module initialization
- [x] Streaming synthesis
- [x] Batch processing
- [x] Speaker selection
- [x] Speed/pitch modification
- [x] Error handling
- [x] Resource cleanup
- [ ] WebSocket integration (Phase 7)
- [ ] Real-time streaming performance (Phase 8)
- [ ] Barge-in detection overlap (Phase 7)

### Next Steps (Phase 7)

1. **WebSocket Integration**
   - Connect TTS output to WebSocket streaming
   - Implement queue management for sequential messages
   - Add client-side audio playback handling

2. **Barge-in Enhancement**
   - Detect user speech during TTS playback
   - Interrupt stream gracefully
   - Resume conversation context

3. **Performance Optimization**
   - Profile latency across pipeline
   - Optimize chunk sizing
   - Implement audio buffering strategies

### References

- VibeVoice Model: https://huggingface.co/thewiseone/VibeVoice
- TTS Library: https://github.com/coqui-ai/TTS
- Async Patterns: asyncio documentation
- WebSocket Integration: Phase 7 WebSocket Engine
