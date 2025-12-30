"""SQLAlchemy ORM Models for NewSpeech Voice Agent

Defines all database models with relationships, constraints, and validations.
"""

from sqlalchemy import (
    Column, BigInteger, Integer, String, Float, Text, Boolean,
    DateTime, Enum, JSON, ForeignKey, Index, UniqueConstraint,
    func, Numeric
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum as PyEnum

Base = declarative_base()


class UserRole(PyEnum):
    """User role enumeration"""
    STUDENT = "student"
    EXAMINER = "examiner"
    ADMIN = "admin"


class CollegeType(PyEnum):
    """College type enumeration"""
    MEDICAL = "medical"
    LAW = "law"
    AVIATION = "aviation"
    AUTOMOBILE = "automobile"
    ENGINEERING = "engineering"
    MANAGEMENT = "management"


class DifficultyLevel(PyEnum):
    """Question difficulty enumeration"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class SessionStatus(PyEnum):
    """Session status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class FeedbackType(PyEnum):
    """Answer feedback type enumeration"""
    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"


class EvaluatorType(PyEnum):
    """Evaluator type enumeration"""
    KEYWORD_MATCH = "keyword_match"
    LLM_BASED = "llm_based"
    MANUAL = "manual"
    HYBRID = "hybrid"


class User(Base):
    """User model for student, examiner, and admin accounts"""
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(Enum(UserRole), default=UserRole.STUDENT)
    college_type = Column(Enum(CollegeType))
    status = Column(String(50), default="active")  # active, inactive, suspended
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)

    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    results = relationship("Result", back_populates="user", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_email', 'email'),
        Index('idx_role', 'role'),
        Index('idx_college_type', 'college_type'),
        Index('idx_status', 'status'),
    )

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role={self.role})>"


class Session(Base):
    """Session model for viva examination sessions"""
    __tablename__ = "sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    college_type = Column(String(50), nullable=False)
    session_code = Column(String(50), unique=True, nullable=False)
    status = Column(Enum(SessionStatus), default=SessionStatus.PENDING)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration_seconds = Column(Integer, default=0)
    total_score = Column(Integer, default=0)
    total_questions = Column(Integer, default=12)
    questions_answered = Column(Integer, default=0)
    voice_detected_count = Column(Integer, default=0)
    avg_latency_ms = Column(Float, default=0.0)
    max_latency_ms = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="sessions")
    answers = relationship("Answer", back_populates="session", cascade="all, delete-orphan")
    result = relationship("Result", back_populates="session", uselist=False, cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="session", cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="session", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_session_code', 'session_code'),
        Index('idx_status', 'status'),
        Index('idx_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<Session(id={self.id}, code='{self.session_code}', status={self.status})>"


class QuestionBank(Base):
    """Question bank model for storing questions across college types"""
    __tablename__ = "question_banks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    college_type = Column(String(50), nullable=False)
    scenario_id = Column(Integer, nullable=False)
    scenario_name = Column(String(255), nullable=False)
    question_number = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    category = Column(String(100))
    difficulty_level = Column(Enum(DifficultyLevel), default=DifficultyLevel.MEDIUM)
    keywords = Column(JSON)  # List of keywords
    expected_keywords = Column(JSON)  # Expected answer keywords
    max_score = Column(Integer, default=10)
    min_score = Column(Integer, default=0)
    answer_guidelines = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    answers = relationship("Answer", back_populates="question_bank")

    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint('college_type', 'scenario_id', 'question_number', name='uk_question'),
        Index('idx_college_type', 'college_type'),
        Index('idx_scenario', 'scenario_id'),
        Index('idx_difficulty', 'difficulty_level'),
    )

    def __repr__(self):
        return f"<QuestionBank(id={self.id}, college_type='{self.college_type}', q_num={self.question_number})>"


class Answer(Base):
    """Answer model for storing student responses"""
    __tablename__ = "answers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(BigInteger, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    question_bank_id = Column(BigInteger, ForeignKey("question_banks.id", ondelete="RESTRICT"), nullable=False)
    question_number = Column(Integer, nullable=False)
    answer_text = Column(Text)
    answer_audio_path = Column(String(255))  # Path to stored audio file
    audio_duration_seconds = Column(Float, default=0.0)
    transcribed_text = Column(Text)  # ASR transcription result
    confidence_score = Column(Float, default=0.0)  # ASR confidence
    is_complete = Column(Boolean, default=False)
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("Session", back_populates="answers")
    question_bank = relationship("QuestionBank", back_populates="answers")
    evaluation = relationship("Evaluation", back_populates="answer", uselist=False, cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_session_id', 'session_id'),
        Index('idx_question_bank_id', 'question_bank_id'),
        Index('idx_question_number', 'question_number'),
        Index('idx_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<Answer(id={self.id}, session_id={self.session_id}, q_num={self.question_number})>"


class Evaluation(Base):
    """Evaluation model for answer scoring and feedback"""
    __tablename__ = "evaluations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    answer_id = Column(BigInteger, ForeignKey("answers.id", ondelete="CASCADE"), nullable=False, unique=True)
    session_id = Column(BigInteger, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    evaluator_type = Column(Enum(EvaluatorType), default=EvaluatorType.KEYWORD_MATCH)
    score_obtained = Column(Integer, default=0)
    max_score = Column(Integer, default=10)
    percentage_correct = Column(Float, default=0.0)
    feedback = Column(Text)
    feedback_type = Column(Enum(FeedbackType), default=FeedbackType.INCORRECT)
    matched_keywords = Column(JSON)  # Keywords found in answer
    missing_keywords = Column(JSON)  # Keywords not found
    latency_ms = Column(Float, default=0.0)  # Evaluation latency
    processing_time_ms = Column(Float, default=0.0)  # Total processing time
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    answer = relationship("Answer", back_populates="evaluation")
    session = relationship("Session", back_populates="evaluations")

    # Indexes
    __table_args__ = (
        Index('idx_answer_id', 'answer_id'),
        Index('idx_session_id', 'session_id'),
        Index('idx_feedback_type', 'feedback_type'),
        Index('idx_score_obtained', 'score_obtained'),
    )

    def __repr__(self):
        return f"<Evaluation(id={self.id}, answer_id={self.answer_id}, score={self.score_obtained})>"


class Result(Base):
    """Result model for session summary and grading"""
    __tablename__ = "results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(BigInteger, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    college_type = Column(String(50), nullable=False)
    total_score = Column(Integer, default=0)
    max_score = Column(Integer, default=120)
    percentage_correct = Column(Float, default=0.0)
    grade = Column(String(2))  # A, B, C, D, F
    pass_status = Column(Boolean, default=False)  # True if score >= 60
    result_json = Column(JSON)  # Complete result data
    certificate_path = Column(String(255))  # Path to generated certificate
    generated_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("Session", back_populates="result")
    user = relationship("User", back_populates="results")

    # Indexes
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_college_type', 'college_type'),
        Index('idx_pass_status', 'pass_status'),
        Index('idx_generated_at', 'generated_at'),
    )

    def __repr__(self):
        return f"<Result(id={self.id}, session_id={self.session_id}, score={self.total_score})>"


class AuditLog(Base):
    """Audit log model for tracking system events and API calls"""
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(BigInteger, ForeignKey("sessions.id", ondelete="SET NULL"))
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(String(255), nullable=False)  # e.g., 'session_created', 'answer_submitted'
    resource_type = Column(String(100))  # e.g., 'session', 'answer', 'evaluation'
    resource_id = Column(BigInteger)
    status = Column(String(50))  # success, failure, error
    details = Column(JSON)  # Additional details
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(Text)  # Browser/client information
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("Session", back_populates="audit_logs")
    user = relationship("User", back_populates="audit_logs")

    # Indexes
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
        Index('idx_session_id', 'session_id'),
        Index('idx_action', 'action'),
        Index('idx_created_at', 'created_at'),
        Index('idx_resource', 'resource_type', 'resource_id'),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', user_id={self.user_id})>"


class Configuration(Base):
    """Configuration model for system settings and parameters"""
    __tablename__ = "configuration"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(255), unique=True, nullable=False)
    config_value = Column(Text)
    value_type = Column(String(50), default="string")  # string, integer, float, boolean, json
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_config_key', 'config_key'),
    )

    def __repr__(self):
        return f"<Configuration(key='{self.config_key}', value='{self.config_value}')>"


# Sample configuration defaults
DEFAULT_CONFIGURATIONS = {
    "voice_threshold": {"value": "45", "type": "integer", "description": "Voice detection threshold"},
    "vad_sensitivity": {"value": "0.5", "type": "float", "description": "VAD sensitivity (0.0-1.0)"},
    "latency_target_ms": {"value": "400", "type": "integer", "description": "Target latency in ms"},
    "max_question_duration_seconds": {"value": "120", "type": "integer", "description": "Max time per question"},
    "min_answer_duration_seconds": {"value": "3", "type": "integer", "description": "Min answer duration"},
    "keyword_matching_threshold": {"value": "0.6", "type": "float", "description": "Keyword match threshold"},
    "tts_max_buffer_size": {"value": "16000", "type": "integer", "description": "TTS buffer size"},
    "asr_language": {"value": "en-US", "type": "string", "description": "ASR language code"},
    "llm_temperature": {"value": "0.7", "type": "float", "description": "LLM temperature parameter"},
}
