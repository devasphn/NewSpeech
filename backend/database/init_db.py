#!/usr/bin/env python3
"""Database Initialization Script for NewSpeech

Creates all tables and loads sample data.
Usage: python init_db.py
"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from datetime import datetime
import os

from models import (
    Base, User, QuestionBank, Configuration, DEFAULT_CONFIGURATIONS,
    UserRole, CollegeType, DifficultyLevel
)
from config import DatabaseConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """Database initialization handler"""

    def __init__(self):
        self.config = DatabaseConfig()
        self.engine = None

    async def initialize(self):
        """Initialize database"""
        try:
            logger.info("🕺 Starting database initialization...")

            # Create engine
            self.engine = create_async_engine(
                self.config.database_url,
                echo=self.config.echo
            )

            # Create all tables
            async with self.engine.begin() as conn:
                logger.info("⚙️ Creating database tables...")
                await conn.run_sync(Base.metadata.create_all)
                logger.info("✅ Tables created successfully")

            # Load sample data
            await self._load_sample_data()
            logger.info("✅ Sample data loaded")

            # Load configurations
            await self._load_configurations()
            logger.info("✅ Configurations loaded")

            logger.info("✅ Database initialization complete!")

        except Exception as e:
            logger.error(f"❌ Database initialization failed: {str(e)}")
            raise
        finally:
            if self.engine:
                await self.engine.dispose()

    async def _load_sample_data(self):
        """Load sample users and questions"""
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker

        async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            # Sample users
            sample_users = [
                User(
                    username="student_medical_001",
                    email="student1@medical.edu",
                    password_hash="hashed_password_1",
                    full_name="Arun Kumar",
                    role=UserRole.STUDENT,
                    college_type=CollegeType.MEDICAL,
                    status="active"
                ),
                User(
                    username="student_engineering_001",
                    email="student2@engineering.edu",
                    password_hash="hashed_password_2",
                    full_name="Priya Sharma",
                    role=UserRole.STUDENT,
                    college_type=CollegeType.ENGINEERING,
                    status="active"
                ),
                User(
                    username="examiner_admin",
                    email="admin@newspeech.edu",
                    password_hash="hashed_admin_password",
                    full_name="Dr. Admin",
                    role=UserRole.ADMIN,
                    college_type=CollegeType.MEDICAL,
                    status="active"
                ),
            ]

            session.add_all(sample_users)
            await session.commit()
            logger.info("✅ Sample users created")

            # Sample questions
            sample_questions = [
                # Medical College - Scenario 1
                QuestionBank(
                    college_type="medical",
                    scenario_id=1,
                    scenario_name="Patient Assessment",
                    question_number=1,
                    question_text="Describe the procedure for taking a patient's medical history.",
                    category="Clinical Practice",
                    difficulty_level=DifficultyLevel.MEDIUM,
                    keywords=["history", "chief complaint", "medical history", "symptoms"],
                    expected_keywords=["chief complaint", "history", "symptoms", "duration"],
                    max_score=10,
                    answer_guidelines="Student should mention chief complaint, duration, severity, and associated symptoms."
                ),
                QuestionBank(
                    college_type="medical",
                    scenario_id=1,
                    scenario_name="Patient Assessment",
                    question_number=2,
                    question_text="What are the vital signs you would record for a patient?",
                    category="Clinical Practice",
                    difficulty_level=DifficultyLevel.EASY,
                    keywords=["vital signs", "temperature", "pulse", "blood pressure", "respiration"],
                    expected_keywords=["temperature", "pulse", "blood pressure", "respiration"],
                    max_score=10,
                    answer_guidelines="Temperature, Pulse, Respiration, Blood Pressure, and Oxygen saturation."
                ),
                QuestionBank(
                    college_type="medical",
                    scenario_id=1,
                    scenario_name="Patient Assessment",
                    question_number=3,
                    question_text="Explain the importance of physical examination in diagnosis.",
                    category="Clinical Practice",
                    difficulty_level=DifficultyLevel.HARD,
                    keywords=["examination", "diagnosis", "palpation", "auscultation", "inspection"],
                    expected_keywords=["inspection", "palpation", "percussion", "auscultation", "diagnosis"],
                    max_score=10,
                    answer_guidelines="Describe inspection, palpation, percussion, and auscultation methods."
                ),
                # Engineering College - Scenario 1
                QuestionBank(
                    college_type="engineering",
                    scenario_id=1,
                    scenario_name="Software Design",
                    question_number=1,
                    question_text="What are the SOLID principles in object-oriented design?",
                    category="Software Engineering",
                    difficulty_level=DifficultyLevel.HARD,
                    keywords=["SOLID", "single responsibility", "open closed", "liskov", "interface segregation", "dependency inversion"],
                    expected_keywords=["Single Responsibility", "Open-Closed", "Liskov Substitution", "Interface Segregation", "Dependency Inversion"],
                    max_score=10,
                    answer_guidelines="Explain all 5 SOLID principles with examples."
                ),
            ]

            session.add_all(sample_questions)
            await session.commit()
            logger.info("✅ Sample questions created")

    async def _load_configurations(self):
        """Load default configurations"""
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker

        async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            for key, config_data in DEFAULT_CONFIGURATIONS.items():
                config = Configuration(
                    config_key=key,
                    config_value=config_data["value"],
                    value_type=config_data["type"],
                    description=config_data["description"],
                    is_active=True
                )
                session.add(config)

            await session.commit()
            logger.info(f"✅ Loaded {len(DEFAULT_CONFIGURATIONS)} configurations")


async def main():
    """Main entry point"""
    initializer = DatabaseInitializer()
    await initializer.initialize()


if __name__ == "__main__":
    asyncio.run(main())
