"""Repository Layer for NewSpeech Database Operations

Provides domain-specific methods for Session, Answer, Evaluation, and Result operations.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import desc, and_, or_
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
import uuid

from .models import (
    User, Session, QuestionBank, Answer, Evaluation, Result,
    AuditLog, Configuration, SessionStatus, FeedbackType, UserRole
)

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for user operations"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_user(self, username: str, email: str, password_hash: str, 
                         full_name: str, role: str, college_type: str) -> User:
        """Create a new user"""
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
            college_type=college_type
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        logger.info(f"✅ User created: {username}")
        return user

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        query = select(User).where(User.username == username)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_users_by_college(self, college_type: str) -> List[User]:
        """Get all users for a college type"""
        query = select(User).where(User.college_type == college_type)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_last_login(self, user_id: int):
        """Update user's last login timestamp"""
        user = await self.get_user_by_id(user_id)
        if user:
            user.last_login = datetime.utcnow()
            await self.db.commit()


class SessionRepository:
    """Repository for session operations"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_session(self, user_id: int, college_type: str) -> Session:
        """Create a new exam session"""
        session_code = f"VIVA-{uuid.uuid4().hex[:12].upper()}"
        session = Session(
            user_id=user_id,
            college_type=college_type,
            session_code=session_code,
            status=SessionStatus.PENDING
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        logger.info(f"✅ Session created: {session_code}")
        return session

    async def get_session_by_id(self, session_id: int) -> Optional[Session]:
        """Get session with all relationships"""
        query = select(Session).where(Session.id == session_id).options(
            joinedload(Session.user),
            selectinload(Session.answers).joinedload(Answer.evaluation),
            selectinload(Session.result)
        )
        result = await self.db.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_session_by_code(self, session_code: str) -> Optional[Session]:
        """Get session by code"""
        query = select(Session).where(Session.session_code == session_code)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_active_sessions(self) -> List[Session]:
        """Get all active sessions"""
        query = select(Session).where(
            Session.status.in_([SessionStatus.PENDING, SessionStatus.IN_PROGRESS])
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_user_sessions(self, user_id: int, limit: int = 10) -> List[Session]:
        """Get user's recent sessions"""
        query = select(Session).where(
            Session.user_id == user_id
        ).order_by(desc(Session.created_at)).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def start_session(self, session_id: int):
        """Start a session"""
        session = await self.get_session_by_id(session_id)
        if session:
            session.status = SessionStatus.IN_PROGRESS
            session.start_time = datetime.utcnow()
            await self.db.commit()
            logger.info(f"✅ Session started: {session.session_code}")

    async def complete_session(self, session_id: int):
        """Complete a session"""
        session = await self.get_session_by_id(session_id)
        if session:
            session.status = SessionStatus.COMPLETED
            session.end_time = datetime.utcnow()
            session.duration_seconds = int(
                (session.end_time - session.start_time).total_seconds()
            )
            await self.db.commit()
            logger.info(f"✅ Session completed: {session.session_code}")

    async def update_session_metrics(self, session_id: int, 
                                    voice_count: int, avg_latency: float, max_latency: float):
        """Update session performance metrics"""
        session = await self.get_session_by_id(session_id)
        if session:
            session.voice_detected_count = voice_count
            session.avg_latency_ms = avg_latency
            session.max_latency_ms = max_latency
            await self.db.commit()


class QuestionRepository:
    """Repository for question bank operations"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_question(self, question_id: int) -> Optional[QuestionBank]:
        """Get question by ID"""
        query = select(QuestionBank).where(QuestionBank.id == question_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_questions_by_college_and_scenario(
        self, college_type: str, scenario_id: int
    ) -> List[QuestionBank]:
        """Get all questions for college type and scenario"""
        query = select(QuestionBank).where(
            and_(
                QuestionBank.college_type == college_type,
                QuestionBank.scenario_id == scenario_id
            )
        ).order_by(QuestionBank.question_number)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_all_scenarios(self, college_type: str) -> List[int]:
        """Get all scenario IDs for college type"""
        query = select(QuestionBank.scenario_id).where(
            QuestionBank.college_type == college_type
        ).distinct()
        result = await self.db.execute(query)
        return result.scalars().all()

    async def bulk_insert_questions(self, questions: List[Dict[str, Any]]):
        """Bulk insert questions"""
        question_objs = [
            QuestionBank(**q) for q in questions
        ]
        self.db.add_all(question_objs)
        await self.db.commit()
        logger.info(f"✅ Inserted {len(question_objs)} questions")


class AnswerRepository:
    """Repository for answer operations"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def store_answer(self, session_id: int, question_id: int,
                          answer_text: str, transcribed_text: str,
                          audio_path: str, confidence: float) -> Answer:
        """Store student answer"""
        answer = Answer(
            session_id=session_id,
            question_bank_id=question_id,
            answer_text=answer_text,
            transcribed_text=transcribed_text,
            answer_audio_path=audio_path,
            confidence_score=confidence,
            started_at=datetime.utcnow(),
            is_complete=True
        )
        self.db.add(answer)
        await self.db.commit()
        await self.db.refresh(answer)
        logger.info(f"✅ Answer stored: session={session_id}, question={question_id}")
        return answer

    async def get_answer(self, answer_id: int) -> Optional[Answer]:
        """Get answer with evaluation"""
        query = select(Answer).where(Answer.id == answer_id).options(
            joinedload(Answer.evaluation),
            joinedload(Answer.question_bank)
        )
        result = await self.db.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_session_answers(self, session_id: int) -> List[Answer]:
        """Get all answers for a session"""
        query = select(Answer).where(
            Answer.session_id == session_id
        ).options(
            joinedload(Answer.evaluation),
            joinedload(Answer.question_bank)
        ).order_by(Answer.question_number)
        result = await self.db.execute(query)
        return result.unique().scalars().all()

    async def get_unevaluated_answers(self, session_id: int) -> List[Answer]:
        """Get answers pending evaluation"""
        query = select(Answer).where(
            and_(
                Answer.session_id == session_id,
                ~Answer.evaluation.any()  # No evaluation yet
            )
        )
        result = await self.db.execute(query)
        return result.scalars().all()


class EvaluationRepository:
    """Repository for evaluation operations"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def store_evaluation(self, answer_id: int, session_id: int,
                              score: int, feedback: str, feedback_type: str,
                              matched_keywords: List[str],
                              latency_ms: float) -> Evaluation:
        """Store answer evaluation"""
        evaluation = Evaluation(
            answer_id=answer_id,
            session_id=session_id,
            score_obtained=score,
            feedback=feedback,
            feedback_type=feedback_type,
            matched_keywords=matched_keywords,
            latency_ms=latency_ms,
            percentage_correct=(score / 10) * 100 if score > 0 else 0
        )
        self.db.add(evaluation)
        await self.db.commit()
        await self.db.refresh(evaluation)
        logger.info(f"✅ Evaluation stored: answer={answer_id}, score={score}")
        return evaluation

    async def get_session_evaluations(self, session_id: int) -> List[Evaluation]:
        """Get all evaluations for session"""
        query = select(Evaluation).where(
            Evaluation.session_id == session_id
        ).order_by(Evaluation.created_at)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def calculate_session_score(self, session_id: int) -> int:
        """Calculate total score for session"""
        query = select(
            func.sum(Evaluation.score_obtained)
        ).where(Evaluation.session_id == session_id)
        result = await self.db.execute(query)
        total = result.scalar()
        return total or 0


class ResultRepository:
    """Repository for result operations"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_result(self, session_id: int, user_id: int,
                           college_type: str, total_score: int) -> Result:
        """Create final result"""
        percentage = (total_score / 120) * 100
        grade = self._calculate_grade(percentage)
        pass_status = total_score >= 60

        result = Result(
            session_id=session_id,
            user_id=user_id,
            college_type=college_type,
            total_score=total_score,
            percentage_correct=percentage,
            grade=grade,
            pass_status=pass_status,
            result_json={
                "total_score": total_score,
                "percentage": percentage,
                "grade": grade,
                "pass": pass_status
            }
        )
        self.db.add(result)
        await self.db.commit()
        await self.db.refresh(result)
        logger.info(f"✅ Result created: session={session_id}, score={total_score}")
        return result

    async def get_result(self, result_id: int) -> Optional[Result]:
        """Get result by ID"""
        query = select(Result).where(Result.id == result_id).options(
            joinedload(Result.session),
            joinedload(Result.user)
        )
        result = await self.db.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_session_result(self, session_id: int) -> Optional[Result]:
        """Get result for session"""
        query = select(Result).where(Result.session_id == session_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_results(self, user_id: int, limit: int = 10) -> List[Result]:
        """Get user's results"""
        query = select(Result).where(
            Result.user_id == user_id
        ).order_by(desc(Result.generated_at)).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_college_statistics(self, college_type: str) -> Dict[str, Any]:
        """Get statistics for college type"""
        query = select(Result).where(Result.college_type == college_type)
        result = await self.db.execute(query)
        results = result.scalars().all()

        if not results:
            return {}

        scores = [r.total_score for r in results]
        return {
            "total_attempts": len(results),
            "pass_count": sum(1 for r in results if r.pass_status),
            "average_score": sum(scores) / len(scores),
            "highest_score": max(scores),
            "lowest_score": min(scores)
        }

    @staticmethod
    def _calculate_grade(percentage: float) -> str:
        """Calculate grade from percentage"""
        if percentage >= 90:
            return "A"
        elif percentage >= 80:
            return "B"
        elif percentage >= 70:
            return "C"
        elif percentage >= 60:
            return "D"
        else:
            return "F"


class AuditLogRepository:
    """Repository for audit log operations"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def log_action(self, user_id: int, action: str, 
                        resource_type: str, resource_id: int,
                        status: str, details: Dict[str, Any] = None,
                        session_id: int = None, ip_address: str = None):
        """Log system action"""
        audit_log = AuditLog(
            user_id=user_id,
            session_id=session_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            details=details or {},
            ip_address=ip_address
        )
        self.db.add(audit_log)
        await self.db.commit()

    async def get_user_audit_logs(self, user_id: int, limit: int = 50) -> List[AuditLog]:
        """Get user's audit logs"""
        query = select(AuditLog).where(
            AuditLog.user_id == user_id
        ).order_by(desc(AuditLog.created_at)).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_session_audit_logs(self, session_id: int) -> List[AuditLog]:
        """Get session's audit logs"""
        query = select(AuditLog).where(
            AuditLog.session_id == session_id
        ).order_by(AuditLog.created_at)
        result = await self.db.execute(query)
        return result.scalars().all()


from sqlalchemy import func
