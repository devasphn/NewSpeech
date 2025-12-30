# VIVA VOCE EXAMINER - PHASE 1: DESIGN & PLANNING

## Project Overview
Building a production-grade voice-based Viva Voce Examiner for 8 college types using:
- **VAD**: Silero VAD (semantic voice activity detection)
- **ASR**: Whisper Large V3 Turbo (streaming)
- **LLM**: Llama 3.1 8B Instruct (vLLM optimized)
- **TTS**: VibeVoice 0.5B (streaming, Indian accent)
- **Platform**: RunPod (WebSocket, no UDP, no Docker)

---

## SYSTEM ARCHITECTURE

### High-Level Pipeline
```
User Voice Input
      |
      v
[VAD Module] - Detects speech start/end (Silero VAD)
      |
      v
[ASR Module] - Converts speech to text (Whisper Large V3 Turbo)
      |
      v
[LLM Module] - Generates contextual response (Llama 3.1 8B + vLLM)
      |
      v
[TTS Module] - Converts response to speech (VibeVoice 0.5B)
      |
      v
User Audio Output
```

### Communication Layer
- **Protocol**: WebSocket (JSON messages with base64-encoded audio)
- **Architecture**: Token streaming (parallel processing)
- **Barge-in**: Real-time interruption with context preservation

---

## PROJECT STRUCTURE

```
NewSpeech/
├── backend/
├── frontend/
├── database/
├── config/
├── requirements.txt
├── docker-compose.yml (optional for local testing)
├── runpod-serverless.toml (RunPod config)
└── README.md
```

### Backend Modules
```
backend/
├── core/
│  ├── vad_engine.py (Silero VAD)
│  ├── asr_engine.py (Whisper Large V3 Turbo)
│  ├─┐ llm_engine.py (Llama 3.1 8B via vLLM)
│  └── tts_engine.py (VibeVoice 0.5B)
├── websocket/
│  ├── handler.py (WebSocket connection manager)
│  ├─┐ streaming.py (Token streaming pipeline)
│  └── barge_in.py (Interrupt handling)
├── viva_engine/
│  ├── question_manager.py (8 viva question DBs)
│  ├── scenario_handler.py (4-scenario flow)
│  ├─┐ feedback_engine.py (Natural language feedback)
│  └── scoring_system.py (12-question evaluation)
├── database/
│  ├── models.py (SQLAlchemy models)
│  ├─┐ session_handler.py
│  └── report_generator.py
├── utils/
│  ├── audio_utils.py (Audio processing)
│  ├── logging.py
│  └── config_loader.py
└── main.py (Entry point)
```

---

## 14-PHASE DEVELOPMENT ROADMAP

### PHASE 1: Design and Planning [CURRENT]
- Create system architecture and flowcharts
- Define task breakdown and execution order
- Document all technical specifications
- **Deliverable**: PHASE_1_DESIGN_AND_PLANNING.md, Architecture flowchart

### PHASE 2: Backend Core Setup
- Initialize Python project structure
- Create requirements.txt with all dependencies
- Setup environment configuration
- Initialize database models
- **Deliverable**: Project scaffold with dependencies installed

### PHASE 3: VAD Module
- Implement Silero VAD streaming inference
- Create voice activity detection pipeline
- Integrate with WebSocket for real-time processing
- **Deliverable**: Working VAD module with streaming support

### PHASE 4: ASR Module
- Implement Whisper Large V3 Turbo with streaming
- Create audio chunk buffering system
- Integrate with VAD output
- **Deliverable**: Working ASR module returning text in real-time

### PHASE 5: LLM Module
- Setup vLLM server locally/on RunPod
- Create Llama 3.1 8B inference pipeline
- Implement token streaming for real-time response
- Setup system prompts for 8 viva types
- **Deliverable**: Working LLM streaming module

### PHASE 6: TTS Module
- Implement VibeVoice 0.5B streaming inference
- Create audio streaming output pipeline
- Setup Indian accent configuration
- **Deliverable**: Working TTS module with streaming

### PHASE 7: WebSocket Handler
- Implement WebSocket connection manager
- Create message protocol (JSON with base64 audio)
- Setup parallel processing (VAD+ASR+LLM+TTS)
- Implement streaming token handling
- **Deliverable**: Working WebSocket server with all components connected

### PHASE 8: Barge-in Implementation
- Implement semantic VAD for interruption detection
- Create state machine for context preservation
- Setup real-time TTS cancellation (<50ms latency)
- **Deliverable**: Production-grade barge-in system

### PHASE 9: Viva Question Engine
- Create question databases for 8 viva types:
  1. Medical Viva (Cardiology, Orthopedics, etc.)
  2. Automobile Viva
  3. Aviation Viva
  4. Law Viva
  5. Engineering Viva
  6. Nursing Viva
  7. Pharmacy Viva
  8. Dental Viva
- Implement 4-scenario flow with 3 questions each
- Create transition logic between scenarios
- **Deliverable**: Complete question database and scenario flow engine

### PHASE 10: Feedback & Scoring System
- Implement natural language feedback generation
- Create evaluation logic for correct/partial/incorrect answers
- Setup 12-question scoring system (4 scenarios × 3 questions)
- Create model answers for each question
- **Deliverable**: Complete feedback and scoring engine

### PHASE 11: Frontend UI
- Build React/Vue interface with 8 viva type buttons
- Create real-time voice UI (start, stop, mute buttons)
- Implement WebSocket client for streaming
- Add audio visualization and metrics display
- **Deliverable**: Complete frontend UI

### PHASE 12: Database & Reporting
- Setup PostgreSQL/MongoDB for session storage
- Create session recording mechanism
- Implement report generation (PDF with scores)
- Create analytics dashboard
- **Deliverable**: Complete database layer and report generation

### PHASE 13: Integration & Testing
- Full end-to-end testing
- Latency optimization (target <500-700ms)
- Load testing with concurrent users
- Barge-in edge case handling
- **Deliverable**: Fully tested, optimized system

### PHASE 14: Deployment to RunPod
- Configure RunPod container
- Setup vLLM server on RunPod GPU
- Deploy frontend to CDN/cloud
- Configure load balancing
- **Deliverable**: Production deployment on RunPod

---

## COMPONENT SPECIFICATIONS

### VAD Module (Silero VAD)
- **Input**: 16kHz mono audio (16-bit PCM)
- **Output**: Boolean (speech/silence) + confidence
- **Latency**: <1ms per frame
- **Streaming**: Process 512-sample frames continuously
- **Features**: Adaptive thresholds, noise robustness

### ASR Module (Whisper Large V3 Turbo)
- **Input**: Raw audio frames or audio file
- **Output**: Transcription text with timestamps
- **Latency**: ~300-400ms (acceptable within token budget)
- **Streaming**: Support real-time transcription
- **Features**: Language auto-detection, punctuation

### LLM Module (Llama 3.1 8B)
- **Deployment**: vLLM with PagedAttention
- **Input**: System prompt + user question (context preserved)
- **Output**: Token streaming response
- **Latency**: 80-120ms TTFT (Time To First Token)
- **Features**: Context window ~8K tokens, fine-tunable

### TTS Module (VibeVoice 0.5B)
- **Input**: Text to synthesize
- **Output**: Audio stream (16kHz PCM)
- **Latency**: 200-300ms for typical sentence
- **Streaming**: Support chunk-based output
- **Features**: Natural prosody, Indian accent support

---

## LATENCY BUDGET ALLOCATION

```
Component           | Latency Budget | Actual
─────────────────────────────────────────────
VAD Detection       | 20ms          | <1ms ✓
ASR Transcription   | 150ms         | 300-400ms ⚠
LLM Inference (TTFT)| 150ms         | 80-120ms ✓
TTS Synthesis       | 150ms         | 200-300ms ⚠
Network/Processing  | 100ms         | ~50ms ✓
─────────────────────────────────────────────
Total               | 500-700ms     | ~500-700ms ✓
```

**Strategy**: Pipeline parallelization reduces perceived latency

---

## DATA FLOW: MEDICAL VIVA EXAMPLE

```
1. UI: Student clicks "Medical Viva Examiner"
2. WebSocket connects to backend
3. System: "Welcome! What is your name?"
   TTS plays: Welcome message
   
4. Student: "My name is Joseph"
   VAD: Detects speech start/end
   ASR: "My name is Joseph"
   LLM: Generates response
   TTS: Plays confirmation
   
5. System: "Which area would you like to take viva on?"
6. Student: "Cardiology"
   (Repeat VAD→ASR→LLM→TTS)
   
7. System: "Scenario 1: A 58-year-old diabetic man..."
8. System: "Question 1: What is your diagnosis?"
   
9. Student answers all 12 questions (4 scenarios × 3 questions)
10. Database stores session with scores
11. Report generated and displayed
12. "Thank you for attending the viva. Goodbye!"
```

---

## CRITICAL IMPLEMENTATION NOTES

### 1. Single LLM for All 8 Viva Types
- **Why**: Single Llama 3.1 8B with system prompt adaptation
- **Cost**: $0.30/hr instead of $1.80/hr (6 × GPU)
- **Method**: Few-shot examples + LoRA fine-tuning on viva Q&A

### 2. Token Streaming Architecture
- **Benefits**: Reduces perceived latency, better UX
- **Implementation**: Send tokens as they're generated (no waiting)
- **Challenge**: Maintain context during streaming

### 3. Barge-in Production Grade
- **Detection**: VAD on user input while TTS playing
- **Interruption**: Cancel TTS, preserve conversation state
- **Edge Case**: User speaks during system response

### 4. WebSocket Only (No UDP)
- **Reason**: RunPod constraint
- **Trade-off**: Slightly higher latency than UDP
- **Mitigation**: Optimize frame size and compression

### 5. Evaluation Criteria
- **Correct**: Deep medical reasoning + specifics
- **Partial**: Right general direction but missing details
- **Incorrect**: Wrong diagnosis/management/reasoning

---

## NEXT STEPS

After Phase 1 approval:
1. Create detailed architecture diagram
2. Setup GitHub project board
3. Begin Phase 2 (Backend Core Setup)
4. Create all necessary configuration files

**Status**: ✅ PHASE 1 COMPLETE - AWAITING YOUR APPROVAL TO PROCEED
