"""Viva Examiner Engine - Question Answer Session Management

Orchestrates Q&A sessions for 6 college types with scenario-based questions,
answer evaluation, feedback generation, and score calculation.
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class CollegeType(Enum):
    """6 College Types for Viva Examiner"""
    MEDICAL = "medical"
    LAW = "law"
    AVIATION = "aviation"
    AUTOMOBILE = "automobile"
    ENGINEERING = "engineering"
    MANAGEMENT = "management"

@dataclass
class Question:
    """Question structure"""
    id: str
    college_type: CollegeType
    scenario: str
    question_text: str
    expected_answer: str
    difficulty: str  # beginner, intermediate, advanced
    keywords: List[str] = field(default_factory=list)

@dataclass
class Answer:
    """Answer structure"""
    question_id: str
    student_answer: str
    timestamp: float
    duration_seconds: float
    confidence: float  # 0.0 to 1.0 (TTS completion ratio)

@dataclass
class Evaluation:
    """Answer evaluation"""
    answer_id: str
    is_correct: bool
    match_score: float  # 0.0 to 1.0 (keyword matching)
    feedback: str
    score_points: int  # 0-10 per question

@dataclass
class SessionConfig:
    """Viva Session Configuration"""
    college_type: CollegeType
    questions_per_scenario: int = 3
    num_scenarios: int = 4
    total_questions: int = 12  # 4 x 3
    max_time_per_question: int = 60  # seconds
    enable_barge_in: bool = True

class VivaExaminer:
    """Main Viva Examiner Engine"""
    
    def __init__(self, config: Optional[SessionConfig] = None):
        """Initialize Viva Examiner
        
        Args:
            config: SessionConfig object
        """
        self.config = config or SessionConfig(
            college_type=CollegeType.MEDICAL
        )
        self.session_id = str(uuid.uuid4())[:8]
        self.logger = logger
        
        # Session state
        self.current_question_idx = 0
        self.questions: List[Question] = []
        self.answers: List[Answer] = []
        self.evaluations: List[Evaluation] = []
        self.session_start_time = None
        self.session_active = False
        
        # Scenario management
        self.current_scenario_idx = 0
        self.scenarios: List[str] = []
        
    async def initialize_session(self, 
                                college_type: CollegeType,
                                student_name: str) -> Dict:
        """Initialize viva session
        
        Args:
            college_type: Type of college
            student_name: Student identifier
            
        Returns:
            Session metadata
        """
        self.config.college_type = college_type
        self.session_start_time = datetime.now()
        self.session_active = True
        
        # Load questions from question bank
        await self._load_questions(college_type)
        
        self.logger.info(
            f"Session started: {self.session_id} | "
            f"Student: {student_name} | College: {college_type.value}"
        )
        
        return {
            "session_id": self.session_id,
            "student_name": student_name,
            "college_type": college_type.value,
            "total_questions": self.config.total_questions,
            "start_time": self.session_start_time.isoformat()
        }
    
    async def _load_questions(self, college_type: CollegeType) -> None:
        """Load questions for college type from question bank
        
        Args:
            college_type: Type of college
        """
        # This would be replaced with actual question bank integration
        # For now, placeholder structure
        self.questions = [
            Question(
                id=f"q_{college_type.value}_{i}",
                college_type=college_type,
                scenario=f"Scenario {(i // 3) + 1}",
                question_text=f"Question {i+1} for {college_type.value}",
                expected_answer=f"Model answer for question {i+1}",
                difficulty="intermediate",
                keywords=[f"keyword{j}" for j in range(5)]
            )
            for i in range(self.config.total_questions)
        ]
    
    async def get_current_question(self) -> Optional[Dict]:
        """Get current question
        
        Returns:
            Current question or None if session ended
        """
        if self.current_question_idx >= len(self.questions):
            self.session_active = False
            return None
        
        question = self.questions[self.current_question_idx]
        return {
            "question_id": question.id,
            "scenario": question.scenario,
            "question_text": question.question_text,
            "question_number": self.current_question_idx + 1,
            "total_questions": self.config.total_questions,
            "max_duration": self.config.max_time_per_question
        }
    
    async def submit_answer(self, 
                           student_answer: str,
                           duration_seconds: float) -> Dict:
        """Submit answer for evaluation
        
        Args:
            student_answer: Student's spoken answer (transcribed)
            duration_seconds: Time taken to answer
            
        Returns:
            Evaluation result
        """
        if not self.session_active or self.current_question_idx >= len(self.questions):
            return {"error": "Session not active"}
        
        question = self.questions[self.current_question_idx]
        
        # Record answer
        answer = Answer(
            question_id=question.id,
            student_answer=student_answer,
            timestamp=datetime.now().timestamp(),
            duration_seconds=duration_seconds,
            confidence=min(1.0, duration_seconds / self.config.max_time_per_question)
        )
        self.answers.append(answer)
        
        # Evaluate answer
        evaluation = await self._evaluate_answer(question, answer)
        self.evaluations.append(evaluation)
        
        # Prepare feedback
        feedback_dict = await self._generate_feedback(question, evaluation)
        
        # Move to next question
        self.current_question_idx += 1
        
        return feedback_dict
    
    async def _evaluate_answer(self, question: Question, 
                              answer: Answer) -> Evaluation:
        """Evaluate student answer
        
        Args:
            question: Question object
            answer: Answer object
            
        Returns:
            Evaluation object
        """
        # Simple keyword matching (0.0 to 1.0)
        match_score = self._calculate_match_score(
            answer.student_answer,
            question.keywords
        )
        
        # Determine correctness
        is_correct = match_score >= 0.6
        
        # Calculate score (0-10)
        score_points = int(match_score * 10)
        
        # Create evaluation
        evaluation = Evaluation(
            answer_id=answer.question_id,
            is_correct=is_correct,
            match_score=match_score,
            feedback="",  # Will be filled by feedback generator
            score_points=score_points
        )
        
        return evaluation
    
    def _calculate_match_score(self, answer: str, 
                               keywords: List[str]) -> float:
        """Calculate keyword match score
        
        Args:
            answer: Student answer text
            keywords: Expected keywords
            
        Returns:
            Match score (0.0 to 1.0)
        """
        answer_lower = answer.lower()
        matched_keywords = sum(
            1 for kw in keywords if kw.lower() in answer_lower
        )
        
        return matched_keywords / len(keywords) if keywords else 0.0
    
    async def _generate_feedback(self, question: Question,
                                evaluation: Evaluation) -> Dict:
        """Generate feedback for answer
        
        Args:
            question: Question object
            evaluation: Evaluation object
            
        Returns:
            Feedback dictionary
        """
        if evaluation.is_correct:
            feedback_text = (
                f"That's exactly right. You've covered the key points. "
                f"Let me explain: {question.expected_answer}"
            )
        elif evaluation.match_score > 0.3:
            feedback_text = (
                f"You're on the right track. However, you missed some important points. "
                f"The complete answer is: {question.expected_answer}"
            )
        else:
            feedback_text = (
                f"Not quite. The correct approach is: {question.expected_answer}"
            )
        
        return {
            "feedback": feedback_text,
            "score_points": evaluation.score_points,
            "is_correct": evaluation.is_correct,
            "match_score": evaluation.match_score,
            "question_number": self.current_question_idx,
            "next_question_available": self.current_question_idx < len(self.questions)
        }
    
    async def get_session_report(self) -> Dict:
        """Generate final session report
        
        Returns:
            Session report with scores and metrics
        """
        if not self.evaluations:
            return {"error": "No evaluations yet"}
        
        total_score = sum(e.score_points for e in self.evaluations)
        max_score = 10 * len(self.evaluations)
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        
        correct_count = sum(1 for e in self.evaluations if e.is_correct)
        
        session_duration = (
            datetime.now() - self.session_start_time
        ).total_seconds() if self.session_start_time else 0
        
        return {
            "session_id": self.session_id,
            "college_type": self.config.college_type.value,
            "total_questions": len(self.evaluations),
            "correct_answers": correct_count,
            "total_score": total_score,
            "max_score": max_score,
            "percentage": round(percentage, 2),
            "session_duration": round(session_duration, 2),
            "timestamp": datetime.now().isoformat(),
            "evaluations": [asdict(e) for e in self.evaluations]
        }
    
    async def end_session(self) -> Dict:
        """End viva session
        
        Returns:
            Final report
        """
        self.session_active = False
        report = await self.get_session_report()
        self.logger.info(f"Session ended: {self.session_id}")
        return report

# Singleton instance
_viva_instance: Optional[VivaExaminer] = None

async def get_viva_examiner(config: Optional[SessionConfig] = None) -> VivaExaminer:
    """Get or create Viva Examiner instance"""
    global _viva_instance
    if _viva_instance is None:
        _viva_instance = VivaExaminer(config)
    return _viva_instance

async def shutdown_viva_examiner() -> None:
    """Shutdown Viva Examiner"""
    global _viva_instance
    if _viva_instance:
        _viva_instance = None
