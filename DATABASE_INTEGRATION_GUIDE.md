# Database Integration Guide for NewSpeech Voice Agent

**Purpose**: Connect the database layer with existing voice pipeline (Phases 2-8)  
**Target**: Maintain <400ms latency throughout integration  
**Status**: Ready for Phase 10 (API Endpoints)

---

## Quick Start

### 1. Environment Setup

```env
# .env file
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/newspeech
# or MySQL
# DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/newspeech

DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_RECYCLE=3600

ENABLE_AUDIT_LOGS=true
ENABLE_RESULT_CACHING=true
```

### 2. Initialize Database

```bash
cd backend/database
python init_db.py
```

### 3. Import in Main App

```python
# backend/main.py
from fastapi import FastAPI
from database import get_db_session, close_db_session

app = FastAPI()

@app.on_event("startup")
async def startup():
    app.state.db_session = await get_db_session()

@app.on_event("shutdown")
async def shutdown():
    await close_db_session()
```

---

## Integration Points

### Phase 7: WebSocket Server ↔ Database

**File**: `backend/core/websocket_engine.py`

```python
from database import SessionRepository, AuditLogRepository
from database.config import get_db_session

class WebSocketEngine:
    async def on_client_connect(self, client_id: str, user_id: int, college_type: str):
        """Create session in database when client connects"""
        db_session = await get_db_session()
        session_repo = SessionRepository(db_session.get_session())
        
        # Create session
        session = await session_repo.create_session(user_id, college_type)
        
        # Store in memory for quick access
        self.client_sessions[client_id] = session
        
        # Log action
        audit_repo = AuditLogRepository(db_session.get_session())
        await audit_repo.log_action(
            user_id=user_id,
            action="session_created",
            resource_type="session",
            resource_id=session.id,
            status="success",
            session_id=session.id,
            ip_address="client_ip"
        )
        
        return session
```

### Phase 8: Viva Engine ↔ Database

**File**: `backend/core/viva_engine.py`

```python
from database import (
    SessionRepository, QuestionRepository, AnswerRepository,
    EvaluationRepository, ResultRepository
)

class VivaEngine:
    async def store_answer(self, session_id: int, question_id: int,
                          answer_text: str, transcribed_text: str,
                          audio_path: str, confidence: float):
        """Store answer in database"""
        db_session = await get_db_session()
        answer_repo = AnswerRepository(db_session.get_session())
        
        answer = await answer_repo.store_answer(
            session_id=session_id,
            question_id=question_id,
            answer_text=answer_text,
            transcribed_text=transcribed_text,
            audio_path=audio_path,
            confidence=confidence
        )
        return answer
    
    async def store_evaluation(self, answer_id: int, session_id: int,
                              score: int, feedback: str,
                              matched_keywords: list, latency_ms: float):
        """Store evaluation in database"""
        db_session = await get_db_session()
        eval_repo = EvaluationRepository(db_session.get_session())
        
        # Determine feedback type
        if score >= 8:
            feedback_type = "correct"
        elif score >= 5:
            feedback_type = "partial"
        else:
            feedback_type = "incorrect"
        
        evaluation = await eval_repo.store_evaluation(
            answer_id=answer_id,
            session_id=session_id,
            score=score,
            feedback=feedback,
            feedback_type=feedback_type,
            matched_keywords=matched_keywords,
            latency_ms=latency_ms
        )
        return evaluation
    
    async def complete_session(self, session_id: int):
        """Complete session and generate results"""
        db_session = await get_db_session()
        
        # Get session
        session_repo = SessionRepository(db_session.get_session())
        session = await session_repo.get_session_by_id(session_id)
        
        # Calculate total score
        eval_repo = EvaluationRepository(db_session.get_session())
        total_score = await eval_repo.calculate_session_score(session_id)
        
        # Complete session
        await session_repo.complete_session(session_id)
        
        # Create result
        result_repo = ResultRepository(db_session.get_session())
        result = await result_repo.create_result(
            session_id=session_id,
            user_id=session.user_id,
            college_type=session.college_type,
            total_score=total_score
        )
        
        return result
```

---

## Data Flow Example

### Complete Viva Session Flow

```
1. USER INITIATES SESSION
   │
   └─→ WebSocket: on_client_connect(user_id, college_type)
       │
       └─→ Database: SessionRepository.create_session()
           └─→ Result: Session(id=123, code='VIVA-ABC123', status='pending')

2. SESSION STARTS
   │
   └─→ SessionRepository.start_session(session_id)
       └─→ Update: status='in_progress', start_time=now

3. QUESTION PRESENTED
   │
   └─→ QuestionRepository.get_question(question_id)
       └─→ Result: Question with expected_keywords

4. STUDENT ANSWERS
   │
   └─→ VAD/ASR Pipeline (Phases 3-4)
       │
       └─→ AnswerRepository.store_answer()
           └─→ Result: Answer(id=456, transcribed_text='...')

5. ANSWER EVALUATED
   │
   └─→ LLM Engine (Phase 5) + Viva Engine (Phase 8)
       │
       └─→ EvaluationRepository.store_evaluation()
           └─→ Result: Evaluation(score=8, feedback='...')

6. REPEAT FOR ALL 12 QUESTIONS
   │
   └─→ Answer + Evaluate cycle x12

7. SESSION COMPLETE
   │
   └─→ VivaEngine.complete_session()
       │
       └─→ EvaluationRepository.calculate_session_score()
       │   └─→ Result: total_score = 95
       │
       └─→ SessionRepository.complete_session()
       │   └─→ Update: status='completed', end_time=now
       │
       └─→ ResultRepository.create_result()
           └─→ Result: Result(score=95, grade='A', pass=true)
```

---

## Latency Considerations

### Phase 7 (WebSocket) Integration

```python
# Connection establishment - should be <50ms total
start = time.time()

# 1. WebSocket connection (5ms)
# 2. Database session creation (5ms)
# 3. Session record insertion (30ms)
# 4. Audit log entry (5ms)

total = (time.time() - start) * 1000  # milliseconds
assert total < 50, f"Connection setup took {total}ms"
```

### Phase 8 (Viva Engine) Integration

```python
# Answer storage - should be <30ms total
start = time.time()

# 1. Database insert (15ms)
# 2. Commit transaction (5ms)
# 3. Refresh object (5ms)
# 4. Return to caller (5ms)

total = (time.time() - start) * 1000
assert total < 30, f"Answer storage took {total}ms"
```

### Overall Pipeline

```
VAD (50ms) + ASR (150ms) + LLM (80ms) + TTS (60ms) + DB (25ms) = ~365ms < 400ms ✅
```

---

## Exception Handling

### Database Connection Failures

```python
from sqlalchemy.exc import SQLAlchemyError

async def store_answer_with_fallback(...):
    """Store answer with fallback handling"""
    try:
        answer = await answer_repo.store_answer(...)
        return answer
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        # Fallback: Store in memory cache
        cache[answer_id] = answer_data
        # Retry on next batch operation
        return answer_data
    except Exception as e:
        logger.critical(f"Unexpected error: {e}")
        raise
```

### Transaction Rollback

```python
async def store_session_data(session_id: int, answers: list):
    """Store multiple answers with transaction safety"""
    db_session = await get_db_session()
    session = db_session.get_session()
    
    try:
        for answer_data in answers:
            answer = await answer_repo.store_answer(**answer_data)
            # If any answer fails, entire transaction rolls back
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Transaction rolled back: {e}")
        raise
```

---

## Monitoring & Observability

### Query Performance Monitoring

```python
from database.config import DatabaseConfig

config = DatabaseConfig()
config.echo = True  # Enable SQL logging in development
config.echo_pool = True  # Log pool events
```

### Audit Logging

```python
async def log_answer_submission(user_id: int, session_id: int, answer_id: int):
    """Log answer submission for audit trail"""
    await audit_repo.log_action(
        user_id=user_id,
        action="answer_submitted",
        resource_type="answer",
        resource_id=answer_id,
        status="success",
        session_id=session_id,
        details={
            "timestamp": datetime.utcnow().isoformat(),
            "answer_length": len(answer_text),
            "confidence": confidence_score
        },
        ip_address="client_ip"
    )
```

### Metrics Collection

```python
from prometheus_client import Histogram, Counter

db_query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['operation']
)

db_errors = Counter(
    'db_errors_total',
    'Total database errors',
    ['operation', 'error_type']
)

# Usage
with db_query_duration.labels('answer_insert').time():
    answer = await answer_repo.store_answer(...)
```

---

## Testing Integration

### Unit Test Example

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from database import Base, SessionRepository, Session as SessionModel

@pytest.fixture
async def test_db():
    """Create in-memory test database"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = AsyncSession(engine)
    yield async_session
    await async_session.close()

@pytest.mark.asyncio
async def test_create_session(test_db):
    """Test session creation"""
    repo = SessionRepository(test_db)
    session = await repo.create_session(user_id=1, college_type="medical")
    
    assert session.id is not None
    assert session.session_code.startswith("VIVA-")
    assert session.status == SessionStatus.PENDING
```

### Integration Test Example

```python
@pytest.mark.asyncio
async def test_complete_viva_flow():
    """Test complete viva session flow"""
    # 1. Create session
    session = await session_repo.create_session(1, "medical")
    
    # 2. Start session
    await session_repo.start_session(session.id)
    
    # 3. Store answers and evaluations
    for i in range(1, 13):
        answer = await answer_repo.store_answer(
            session.id, i, f"Answer {i}", f"Transcribed {i}", f"/audio/{i}.wav", 0.95
        )
        await eval_repo.store_evaluation(
            answer.id, session.id, 8, "Good answer", ["key1", "key2"], 25.0
        )
    
    # 4. Complete session
    result = await result_repo.create_result(
        session.id, 1, "medical", 96
    )
    
    assert result.total_score == 96
    assert result.grade == "A"
    assert result.pass_status == True
```

---

## Performance Tuning

### Connection Pool Optimization

```python
# For high concurrent load
DB_POOL_SIZE=40  # Increase for more concurrent connections
DB_MAX_OVERFLOW=20
DB_POOL_RECYCLE=1800  # Reduce recycle time for freshness
```

### Query Optimization

```python
# Use eager loading to prevent N+1 queries
query = select(Session).options(
    joinedload(Session.user),
    selectinload(Session.answers).joinedload(Answer.evaluation),
    selectinload(Session.result)
).where(Session.id == session_id)
```

### Batch Operations

```python
# Insert multiple answers efficiently
await answer_repo.bulk_insert([
    Answer(session_id=1, question_id=1, answer_text="..."),
    Answer(session_id=1, question_id=2, answer_text="..."),
    # ... more answers
])
```

---

## Migration to Production

### Step 1: Database Migration
```bash
alembic upgrade head
```

### Step 2: Backup Existing Data
```bash
mysqldump -u user -p database > backup_$(date +%Y%m%d).sql
```

### Step 3: Deploy Code
```bash
git pull origin main
pip install -r requirements.txt
```

### Step 4: Run Migrations
```bash
alembic upgrade head
```

### Step 5: Verify
```bash
psql -U user -d newspeech -c "SELECT COUNT(*) FROM sessions;"
```

---

## Next Steps

1. **Phase 10**: Implement REST API endpoints
2. **Phase 11**: Add authentication & authorization
3. **Phase 12**: Implement caching layer (Redis)
4. **Phase 13**: Deploy to RunPod
5. **Phase 14**: Performance optimization & monitoring

---

## Support & Troubleshooting

### Connection Issues
```python
# Test database connection
from database import get_db_session

async def test_connection():
    db = await get_db_session()
    async with db.get_session() as session:
        result = await session.execute(select(1))
        print("✅ Connection successful")
```

### Query Performance Issues
```python
# Enable query logging
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

### Memory Leaks
```python
# Always close sessions properly
async with db.get_session() as session:
    # Use session
    pass  # Automatically closed
```

