# VIVA VOCE EXAMINER - ARCHITECTURE FLOWCHARTS

## 1. OVERALL SYSTEM FLOW

```
┌─────────────────────────────────────────────────────────────┐
│                      USER INTERFACE (Browser)               │
│  [Medical] [Auto] [Aviation] [Law] [Engineering] [etc.]    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         v
                  WebSocket Connection
                  (JSON + base64 audio)
                         │
┌────────────────────────┴────────────────────────────────────┐
│              BACKEND STREAMING PIPELINE                     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   VAD Layer  │  │   ASR Layer  │  │   LLM Layer  │     │
│  │ (Silero VAD) │  │  (Whisper)   │  │ (Llama 3.1)  │     │
│  │  <1ms        │─>│  300-400ms   │─>│ 80-120ms     │─┐   │
│  └──────────────┘  └──────────────┘  └──────────────┘ │   │
│                                                         │   │
│                                    ┌──────────────┐    │   │
│                                    │  TTS Layer   │    │   │
│                                    │(VibeVoice)   │<───┘   │
│                                    │ 200-300ms    │        │
│                                    └──────────────┘        │
│                                           │                │
│                          Database & Session Manager        │
└────────────────────────────────┬─────────────────────────┘
                                 │
                                 v
                          Audio Output to User
```

## 2. VAD + ASR + LLM STREAMING PIPELINE

```
┌─────────────────────────────────────────────────────────────┐
│                   User Voice Input                          │
└────────────────┬────────────────────────────────────────────┘
                 │
                 v
         ┌───────────────────────┐
         │  Silero VAD Module    │
         │  (16kHz, 512 samples) │
         └────────┬──────────────┘
                  │
          ┌───────▼───────┐
          │ Voice Activity?│
          └───┬───────┬───┘
              │       │
             No      Yes
              │       │
              │       v
              │   ┌──────────────────────────┐
              │   │ Buffer Audio Frames      │
              │   │ Collect until VAD end    │
              │   └────────┬─────────────────┘
              │            │
              │            v
              │   ┌──────────────────────────┐
              │   │ Whisper ASR Module       │
              │   │ (Large V3 Turbo)         │
              │   │ Streaming Transcription  │
              │   └────────┬─────────────────┘
              │            │
              │            v
              │   ┌──────────────────────────┐
              │   │ LLM Inference (vLLM)     │
              │   │ Llama 3.1 8B Instruct    │
              │   │ Token Streaming          │
              │   │ Context Preservation     │
              │   └────────┬─────────────────┘
              │            │
              │            v
              │   ┌──────────────────────────┐
              │   │ VibeVoice TTS            │
              │   │ Streaming Audio Output   │
              │   │ Play to User             │
              │   └────────┬─────────────────┘
              │            │
              └────────────┴──────────────────>
```

## 3. BARGE-IN IMPLEMENTATION FLOW

```
                    TTS Playing (System Response)
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
        v                                     v
  ┌──────────────┐                  ┌──────────────┐
  │ User Input   │                  │ TTS Output   │
  │ VAD Detector │                  │ Audio Stream │
  │ (Semantic)   │                  └──────────────┘
  └────────┬─────┘
           │
    ┌──────▼──────┐
    │Speech       │
    │Detected?    │
    └────┬───┬────┘
         │   │
        No  Yes
         │   │
         │   v
         │  ┌──────────────────────┐
         │  │ VAD Confidence High? │
         │  └────┬────┬────────────┘
         │       │    │
         │      No    Yes
         │       │    │
         │       │    v
         │       │  ┌──────────────────┐
         │       │  │ Cancel TTS       │
         │       │  │ (<50ms latency)  │
         │       │  └────┬─────────────┘
         │       │       │
         │       │       v
         │       │  ┌──────────────────┐
         │       │  │ Preserve LLM     │
         │       │  │ Context (State)  │
         │       │  └────┬─────────────┘
         │       │       │
         v       v       v
         ┌───────────────────┐
         │Continue Pipeline  │
         │VAD→ASR→LLM→TTS    │
         └───────────────────┘
```

## 4. VIVA VOCE EXAMINATION FLOW (12 Questions)

```
┌─────────────────────────────────────────────────┐
│ Student Selects Viva Type (e.g., Medical)      │
└────────────────────┬────────────────────────────┘
                     │
                     v
        ┌────────────────────────┐
        │ System Introduction    │
        │ "Welcome! Your name?"  │
        └────────┬───────────────┘
                 │
                 v
        ┌────────────────────────┐
        │ Area Selection         │
        │ "Which area (Cardio)"  │
        └────────┬───────────────┘
                 │
                 v
        ┌────────────────────────────────┐
        │ SCENARIO 1: Case Presentation  │
        │ "A 58-year-old diabetic man..."│
        └────────┬───────────────────────┘
                 │
        ┌────────┴────────┬────────┬────────┐
        │                │        │        │
        v                v        v        v
   Q1. "Diagnosis?"  Q2. "Test?"  Q3. "Management?"
        │                │        │        │
        └────────┬────────┴────────┴────────┘
                 │
          ┌──────▼──────┐
          │ Feedback +  │
          │ Next Q or   │
          │ Scenario    │
          └──────┬──────┘
                 │
                 v
        ┌──────────────────────────────┐
        │ SCENARIO 2: New Case         │
        │ (Q4, Q5, Q6)                 │
        └──────────┬───────────────────┘
                   │
                   v
        ┌──────────────────────────────┐
        │ SCENARIO 3: New Case         │
        │ (Q7, Q8, Q9)                 │
        └──────────┬───────────────────┘
                   │
                   v
        ┌──────────────────────────────┐
        │ SCENARIO 4: New Case         │
        │ (Q10, Q11, Q12)              │
        └──────────┬───────────────────┘
                   │
                   v
        ┌──────────────────────────────┐
        │ Final Score Calculation      │
        │ 12 Questions Evaluated       │
        │ Generate Report              │
        └──────────┬───────────────────┘
                   │
                   v
        ┌──────────────────────────────┐
        │ Display Results & PDF        │
        │ "Thank you. Goodbye!"        │
        └──────────────────────────────┘
```

## 5. FEEDBACK ENGINE LOGIC

```
┌──────────────────────────────────────────┐
│ Student Answer Received (ASR Output)     │
└────────────────────┬─────────────────────┘
                     │
                     v
              ┌──────────────┐
              │ LLM Evaluation
              │ (Zero-shot)  │
              └────┬─────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        v          v          v
   ┌─────────┐ ┌─────────┐ ┌──────────┐
   │ CORRECT │ │ PARTIAL │ │INCORRECT │
   └────┬────┘ └────┬────┘ └────┬─────┘
        │           │           │
        v           v           v
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │"That's   │ │"You're on│ │"Not quite│
   │exactly   │ │the right │ │. The     │
   │right.Key│ │track with│ │correct   │
   │points...│ │[correct].│ │approach."│
   │Model:   │ │However.. │ │Model:    │
   │[answer] │ │Model:    │ │[answer]  │
   └────┬────┘ └────┬────┘ └────┬─────┘
        │           │           │
        └───────┬───┴───┬───────┘
                │       │
                v       v
        ┌──────────────────────┐
        │ Database: Store      │
        │ - Q&A               │
        │ - Answer Type        │
        │ - Score (if given)   │
        └──────┬───────────────┘
               │
               v
        ┌──────────────────────┐
        │ Next Question or     │
        │ Scenario Transition  │
        └──────────────────────┘
```

## 6. SYSTEM PROMPT ADAPTATION (SINGLE LLM FOR ALL 8 VIVASYSTEM PROMPT FOR MEDICAL VIVA):
```
You are an expert medical viva examiner testing cardiology knowledge.

EXAMINATION RULES:
1. Ask ONE specific question at a time
2. Evaluate the answer STRICTLY
3. NEVER repeat questions
4. If wrong: Give model answer immediately, move next
5. After 3 questions: "Moving to scenario 2."

FEEDBACK FORMAT:
- Correct: "That's exactly right. [Brief confirmation]. [Model answer]"
- Partial: "You're on track... However, [missing]. [Model answer]"
- Incorrect: "Not quite. [Model answer]"

EVALUATION CRITERIA:
- Correct: Specific diagnosis + reasoning
- Partial: General direction but missing specifics
- Incorrect: Wrong diagnosis or management

QUESTION STYLE:
- Investigations: ONE specific test name
- Management: ONE specific drug/procedure
- No generic phrasing
```

## 7. DATABASE SCHEMA (SIMPLIFIED)

```
Viva Session:
├─ session_id (UUID)
├─ student_name
├─ viva_type (Medical, Auto, Aviation, etc.)
├─ area_of_specialization
├─ start_time
├─ end_time
├─ total_score
└─ scenarios[
    ├─ scenario_id
    ├─ case_presentation
    └─ questions[
        ├─ q_id
        ├─ question_text
        ├─ student_answer
        ├─ evaluation (correct/partial/incorrect)
        ├─ model_answer
        ├─ feedback_text
        └─ score (if applicable)
    ]
  ]
```

---

**Status**: ✅ Architecture documented with 7 comprehensive flowcharts
**Next**: Phase 1 approval pending for Phase 2 execution
