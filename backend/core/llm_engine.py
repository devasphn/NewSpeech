"""
Large Language Model (LLM) Engine for Viva Voce Evaluation
Model: Llama 3.1 8B Instruct
Purpose: Question evaluation, feedback generation, and scoring for exam candidates
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import json
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch
except ImportError:
    raise ImportError("Install transformers: pip install transformers torch")

logger = logging.getLogger(__name__)


class AnswerEvaluation(str, Enum):
    """Evaluation result categories"""
    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"


class CollegeType(str, Enum):
    """Supported college types for viva examination"""
    LAW = "law"
    MEDICAL = "medical"
    AVIATION = "aviation"
    AUTOMOBILE = "automobile"
    ENGINEERING = "engineering"
    COMMERCE = "commerce"
    ARTS = "arts"
    SCIENCE = "science"


@dataclass
class LLMConfig:
    """Configuration for Llama LLM Engine"""
    model_name: str = "meta-llama/Llama-2-7b-chat-hf"
    device: Optional[str] = None
    max_length: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    num_return_sequences: int = 1


@dataclass
class EvaluationResult:
    """Output from LLM evaluation"""
    evaluation: AnswerEvaluation
    confidence: float
    feedback: str
    key_points: List[str] = field(default_factory=list)
    score: float = 0.0
    next_question_prompt: str = ""


@dataclass
class VivaQuestion:
    """Structure for viva questions"""
    question_id: str
    scenario: str
    question_text: str
    expected_answer: str
    college_type: CollegeType
    difficulty: str = "medium"


class LlamaLLMEngine:
    """Production-grade Llama LLM engine for viva examination evaluation"""

    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialize LLM engine with Llama model"""
        self.config = config or LLMConfig()
        self._setup_device()
        self._load_model()
        self.conversation_history = []
        logger.info(f"Llama LLM Engine initialized on {self.device}")

    def _setup_device(self):
        """Setup GPU/CPU device"""
        if self.config.device:
            self.device = self.config.device
        else:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")

    def _load_model(self):
        """Load Llama model and tokenizer"""
        try:
            logger.info(f"Loading {self.config.model_name}...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None
            )
            self.model.eval()
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise

    def evaluate_answer(
        self,
        question: VivaQuestion,
        student_answer: str,
        college_type: CollegeType
    ) -> EvaluationResult:
        """Evaluate student answer against expected answer
        
        Args:
            question: VivaQuestion object
            student_answer: Student's text response
            college_type: Type of college for context
            
        Returns:
            EvaluationResult with evaluation and feedback
        """
        try:
            # Construct evaluation prompt
            prompt = self._build_evaluation_prompt(
                question, student_answer, college_type
            )
            
            # Generate evaluation using LLM
            response = self._generate_response(prompt)
            
            # Parse response
            evaluation_result = self._parse_evaluation_response(response)
            
            # Update conversation history
            self.conversation_history.append({
                "role": "user",
                "content": prompt
            })
            self.conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            return evaluation_result
        except Exception as e:
            logger.error(f"Error evaluating answer: {e}")
            return EvaluationResult(
                evaluation=AnswerEvaluation.INCORRECT,
                confidence=0.0,
                feedback="Error processing your answer. Please try again.",
                score=0.0
            )

    def generate_next_question(
        self,
        college_type: CollegeType,
        scenario: str,
        current_questions_count: int
    ) -> VivaQuestion:
        """Generate next viva question based on college type and scenario
        
        Args:
            college_type: Type of college
            scenario: Current scenario for questions
            current_questions_count: Number of questions asked so far
            
        Returns:
            VivaQuestion object
        """
        try:
            prompt = self._build_question_generation_prompt(
                college_type, scenario, current_questions_count
            )
            response = self._generate_response(prompt)
            question = self._parse_question_response(response, college_type, scenario)
            return question
        except Exception as e:
            logger.error(f"Error generating question: {e}")
            return VivaQuestion(
                question_id="fallback",
                scenario=scenario,
                question_text="Explain the key concepts related to this topic.",
                expected_answer="Student should provide comprehensive explanation",
                college_type=college_type
            )

    def get_score_and_report(
        self,
        evaluations: List[EvaluationResult],
        total_questions: int = 12
    ) -> Dict[str, Any]:
        """Generate final score and report
        
        Args:
            evaluations: List of all evaluation results
            total_questions: Total questions asked
            
        Returns:
            Report dictionary with scores and analysis
        """
        correct_count = sum(1 for e in evaluations if e.evaluation == AnswerEvaluation.CORRECT)
        partial_count = sum(1 for e in evaluations if e.evaluation == AnswerEvaluation.PARTIAL)
        incorrect_count = sum(1 for e in evaluations if e.evaluation == AnswerEvaluation.INCORRECT)
        
        total_score = (
            (correct_count * 10) +
            (partial_count * 5) +
            (incorrect_count * 0)
        )
        percentage = (total_score / (total_questions * 10)) * 100
        
        return {
            "total_questions": total_questions,
            "correct": correct_count,
            "partial": partial_count,
            "incorrect": incorrect_count,
            "total_score": total_score,
            "percentage": percentage,
            "grade": self._compute_grade(percentage),
            "performance": self._compute_performance_level(percentage)
        }

    def _build_evaluation_prompt(self, question: VivaQuestion, student_answer: str, college_type: CollegeType) -> str:
        """Build evaluation prompt for LLM"""
        return f"""
You are an experienced {college_type.value} examiner evaluating a student's answer.

Question: {question.question_text}

Expected Answer: {question.expected_answer}

Student's Answer: {student_answer}

Evaluate the student's answer and provide:
1. Evaluation (correct/partial/incorrect)
2. Confidence score (0-1)
3. Detailed feedback
4. Key points covered

Respond in JSON format.
"""

    def _build_question_generation_prompt(self, college_type: CollegeType, scenario: str, question_num: int) -> str:
        """Build question generation prompt"""
        return f"""
Generate a viva question for {college_type.value} college student.

Scenario: {scenario}
Question Number: {question_num + 1} of 3

Requirements:
- Relevant to scenario
- Appropriate difficulty level
- Clear and concise
- Expected answer in 2-3 sentences

Respond in JSON format with 'question' and 'expected_answer' fields.
"""

    def _generate_response(self, prompt: str) -> str:
        """Generate response from LLM"""
        try:
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=self.config.max_length,
                    temperature=self.config.temperature,
                    top_p=self.config.top_p,
                    num_return_sequences=self.config.num_return_sequences,
                    do_sample=True
                )
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return response
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return ""

    def _parse_evaluation_response(self, response: str) -> EvaluationResult:
        """Parse LLM evaluation response"""
        try:
            # Extract JSON from response
            start = response.find("{")
            end = response.rfind("}")+1
            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)
                return EvaluationResult(
                    evaluation=AnswerEvaluation(data.get("evaluation", "incorrect").lower()),
                    confidence=float(data.get("confidence", 0.5)),
                    feedback=data.get("feedback", ""),
                    key_points=data.get("key_points", [])
                )
        except Exception as e:
            logger.error(f"Error parsing evaluation: {e}")
        
        return EvaluationResult(
            evaluation=AnswerEvaluation.PARTIAL,
            confidence=0.5,
            feedback="Could not parse evaluation",
            score=5.0
        )

    def _parse_question_response(self, response: str, college_type: CollegeType, scenario: str) -> VivaQuestion:
        """Parse LLM question response"""
        try:
            start = response.find("{")
            end = response.rfind("}")+1
            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)
                return VivaQuestion(
                    question_id=f"{college_type}_{scenario}_{len(self.conversation_history)}",
                    scenario=scenario,
                    question_text=data.get("question", ""),
                    expected_answer=data.get("expected_answer", ""),
                    college_type=college_type
                )
        except Exception as e:
            logger.error(f"Error parsing question: {e}")
        
        return VivaQuestion(
            question_id="fallback",
            scenario=scenario,
            question_text="Describe the key concept in detail.",
            expected_answer="Comprehensive explanation expected",
            college_type=college_type
        )

    def _compute_grade(self, percentage: float) -> str:
        """Compute letter grade from percentage"""
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

    def _compute_performance_level(self, percentage: float) -> str:
        """Compute performance level"""
        if percentage >= 85:
            return "Excellent"
        elif percentage >= 70:
            return "Good"
        elif percentage >= 55:
            return "Satisfactory"
        else:
            return "Needs Improvement"

    def reset_conversation(self):
        """Reset conversation history for new session"""
        self.conversation_history = []

    def __repr__(self) -> str:
        return f"LlamaLLMEngine(model={self.config.model_name}, device={self.device})"


def create_llm_engine(config: Optional[LLMConfig] = None) -> LlamaLLMEngine:
    """Factory function for LLM engine initialization"""
    return LlamaLLMEngine(config)
