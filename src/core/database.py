import os
import structlog
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from .models import Base

logger = structlog.get_logger(__name__)


class DatabaseManager:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/ai_spine")
        
        # Convert to sync and async URLs
        if self.database_url.startswith("postgresql+psycopg2://"):
            # Convert psycopg2 URL to base postgresql URL
            self.sync_database_url = self.database_url
            self.async_database_url = self.database_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
        else:
            # Assume base postgresql URL
            self.sync_database_url = self.database_url.replace("postgresql://", "postgresql+psycopg2://")
            self.async_database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://")
        
        # Initialize as None - will be created when needed
        self.engine = None
        self.async_engine = None
        self.SessionLocal = None
        self.AsyncSessionLocal = None
        self._initialized = False

    def _initialize_engines(self):
        """Initialize database engines when needed"""
        if self._initialized:
            return
            
        try:
            # Create engines
            self.engine = create_engine(
                self.sync_database_url,
                pool_pre_ping=True,
                pool_recycle=300,
                echo=os.getenv("SQL_DEBUG", "false").lower() == "true"
            )
            
            self.async_engine = create_async_engine(
                self.async_database_url,
                pool_pre_ping=True,
                pool_recycle=300,
                echo=os.getenv("SQL_DEBUG", "false").lower() == "true"
            )
            
            # Create session factories
            self.SessionLocal = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False
            )
            
            self.AsyncSessionLocal = sessionmaker(
                bind=self.async_engine,
                class_=AsyncSession,
                autocommit=False,
                autoflush=False
            )
            
            self._initialized = True
            logger.info("Database engines initialized")
        except Exception as e:
            logger.error("Failed to initialize database engines", error=str(e))
            raise

    async def create_tables(self):
        """Create all database tables"""
        try:
            self._initialize_engines()
            async with self.async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error("Failed to create database tables", error=str(e))
            raise

    async def drop_tables(self):
        """Drop all database tables"""
        try:
            self._initialize_engines()
            async with self.async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error("Failed to drop database tables", error=str(e))
            raise

    def get_sync_session(self) -> Session:
        """Get a synchronous database session"""
        self._initialize_engines()
        return self.SessionLocal()

    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an asynchronous database session"""
        self._initialize_engines()
        async with self.AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def close(self):
        """Close database connections"""
        if self._initialized:
            await self.async_engine.dispose()
            self.engine.dispose()
            logger.info("Database connections closed")


# Global database manager instance
db_manager = DatabaseManager()


@asynccontextmanager
async def get_db_session():
    """Dependency to get database session"""
    async with db_manager.get_async_session() as session:
        yield session