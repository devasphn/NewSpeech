"""Database Configuration and Connection Pool Setup

Handles database initialization, connection pooling, and session management.
"""

import os
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.future import select
import logging

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Database configuration class"""

    def __init__(self):
        # Database URL from environment
        # Support PostgreSQL and MySQL
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://user:password@localhost:5432/newspeech"
        )

        # Connection pool configuration
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "20"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
        self.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))  # 1 hour
        self.pool_pre_ping = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"

        # Performance settings
        self.echo = os.getenv("DB_ECHO", "false").lower() == "true"
        self.echo_pool = os.getenv("DB_ECHO_POOL", "false").lower() == "true"
        self.connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))

        # Feature flags
        self.enable_audit_logs = os.getenv("ENABLE_AUDIT_LOGS", "true").lower() == "true"
        self.enable_result_caching = os.getenv("ENABLE_RESULT_CACHING", "true").lower() == "true"
        self.cache_ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "300"))

    def get_engine_options(self):
        """Get SQLAlchemy engine options"""
        return {
            "echo": self.echo,
            "echo_pool": self.echo_pool,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": self.pool_pre_ping,
            "connect_args": {
                "timeout": self.connect_timeout,
                "server_settings": {"application_name": "newspeech_app"}
            }
        }


class AsyncDatabaseSession:
    """Async database session manager"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.async_session_maker = None
        self.config = DatabaseConfig()

    async def initialize(self):
        """Initialize async engine and session maker"""
        try:
            engine_options = self.config.get_engine_options()
            
            self.engine = create_async_engine(
                self.database_url,
                **engine_options
            )

            self.async_session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False
            )

            # Test connection
            async with self.engine.begin() as conn:
                await conn.execute(select(1))
                logger.info("✅ Database connection established successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {str(e)}")
            raise

    async def close(self):
        """Close async engine"""
        if self.engine:
            await self.engine.dispose()
            logger.info("✅ Database connection closed")

    def get_session(self) -> AsyncSession:
        """Get async session"""
        if self.async_session_maker is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self.async_session_maker()


class DatabaseManager:
    """Database manager for CRUD operations"""

    def __init__(self, db_session: AsyncDatabaseSession):
        self.db_session = db_session

    async def create(self, model_instance):
        """Create a new record"""
        async with self.db_session.get_session() as session:
            try:
                session.add(model_instance)
                await session.commit()
                await session.refresh(model_instance)
                logger.debug(f"✅ Created: {model_instance}")
                return model_instance
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error creating record: {str(e)}")
                raise

    async def read(self, model_class, record_id):
        """Read a record by ID"""
        async with self.db_session.get_session() as session:
            try:
                query = select(model_class).where(model_class.id == record_id)
                result = await session.execute(query)
                record = result.scalar_one_or_none()
                if record:
                    logger.debug(f"✅ Read: {record}")
                else:
                    logger.debug(f"⚠️  Record not found: {model_class.__name__}(id={record_id})")
                return record
            except Exception as e:
                logger.error(f"❌ Error reading record: {str(e)}")
                raise

    async def update(self, model_instance):
        """Update a record"""
        async with self.db_session.get_session() as session:
            try:
                await session.merge(model_instance)
                await session.commit()
                logger.debug(f"✅ Updated: {model_instance}")
                return model_instance
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error updating record: {str(e)}")
                raise

    async def delete(self, model_class, record_id):
        """Delete a record by ID"""
        async with self.db_session.get_session() as session:
            try:
                record = await session.get(model_class, record_id)
                if record:
                    await session.delete(record)
                    await session.commit()
                    logger.debug(f"✅ Deleted: {record}")
                    return True
                else:
                    logger.warning(f"⚠️  Record not found for deletion: {model_class.__name__}(id={record_id})")
                    return False
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error deleting record: {str(e)}")
                raise

    async def query(self, model_class, **filters):
        """Query records with filters"""
        async with self.db_session.get_session() as session:
            try:
                query = select(model_class)
                for key, value in filters.items():
                    if hasattr(model_class, key):
                        query = query.where(getattr(model_class, key) == value)
                
                result = await session.execute(query)
                records = result.scalars().all()
                logger.debug(f"✅ Query results: {len(records)} records found")
                return records
            except Exception as e:
                logger.error(f"❌ Error querying records: {str(e)}")
                raise

    async def bulk_insert(self, model_class, data_list: list):
        """Bulk insert records"""
        async with self.db_session.get_session() as session:
            try:
                session.add_all(data_list)
                await session.commit()
                logger.debug(f"✅ Bulk inserted: {len(data_list)} records")
                return data_list
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Error bulk inserting records: {str(e)}")
                raise


# Global database session instance
_db_session: Optional[AsyncDatabaseSession] = None


async def get_db_session() -> AsyncDatabaseSession:
    """Get or create global database session"""
    global _db_session
    if _db_session is None:
        config = DatabaseConfig()
        _db_session = AsyncDatabaseSession(config.database_url)
        await _db_session.initialize()
    return _db_session


async def close_db_session():
    """Close global database session"""
    global _db_session
    if _db_session:
        await _db_session.close()
        _db_session = None
