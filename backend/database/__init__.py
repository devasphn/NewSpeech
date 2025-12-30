"""Database Module for NewSpeech Voice Agent

Exports database configuration, models, and repositories.
"""

from .config import AsyncDatabaseSession, DatabaseConfig, DatabaseManager, get_db_session, close_db_session
from .models import (
    Base, User, Session, QuestionBank, Answer, Evaluation, Result, AuditLog, Configuration,
    UserRole, CollegeType, DifficultyLevel, SessionStatus, FeedbackType, EvaluatorType,
    DEFAULT_CONFIGURATIONS
)
from .repositories import (
    UserRepository, SessionRepository, QuestionRepository, AnswerRepository,
    EvaluationRepository, ResultRepository, AuditLogRepository
)

__all__ = [
    # Config
    "AsyncDatabaseSession",
    "DatabaseConfig",
    "DatabaseManager",
    "get_db_session",
    "close_db_session",
    # Models
    "Base",
    "User",
    "Session",
    "QuestionBank",
    "Answer",
    "Evaluation",
    "Result",
    "AuditLog",
    "Configuration",
    # Enums
    "UserRole",
    "CollegeType",
    "DifficultyLevel",
    "SessionStatus",
    "FeedbackType",
    "EvaluatorType",
    "DEFAULT_CONFIGURATIONS",
    # Repositories
    "UserRepository",
    "SessionRepository",
    "QuestionRepository",
    "AnswerRepository",
    "EvaluationRepository",
    "ResultRepository",
    "AuditLogRepository",
]
