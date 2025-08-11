import os
import structlog
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from src.core.models import Base

logger = structlog.get_logger(__name__)


class DatabaseManager:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/ai_spine")
        
        # Clean up the URL for different drivers
        self.sync_database_url = self._prepare_sync_url(self.database_url)
        self.async_database_url = self._prepare_async_url(self.database_url)
        
        # Initialize as None - will be created when needed
        self.engine = None
        self.async_engine = None
        self.SessionLocal = None
        self.AsyncSessionLocal = None
        self._initialized = False

    def _prepare_sync_url(self, url: str) -> str:
        """Prepare URL for psycopg2 (sync)"""
        if url.startswith("postgresql+psycopg2://"):
            return url
        elif url.startswith("postgresql://"):
            # Parse URL to handle SSL parameters
            parsed = urlparse(url)
            # psycopg2 handles sslmode in the URL just fine
            return url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url

    def _prepare_async_url(self, url: str) -> str:
        """Prepare URL for asyncpg (async) - remove incompatible SSL params"""
        if url.startswith("postgresql+asyncpg://"):
            base_url = url
        elif url.startswith("postgresql://"):
            base_url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            base_url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        
        # Parse the URL to remove SSL parameters that asyncpg doesn't understand
        parsed = urlparse(base_url)
        query_params = parse_qs(parsed.query)
        
        # Remove parameters that asyncpg doesn't support
        params_to_remove = ['sslmode', 'channel_binding']
        for param in params_to_remove:
            query_params.pop(param, None)
        
        # Add asyncpg-specific SSL parameter if needed
        if 'sslmode' in urlparse(url).query:
            query_params['ssl'] = ['require']
        
        # Rebuild the URL
        new_query = urlencode(query_params, doseq=True)
        new_parsed = parsed._replace(query=new_query)
        return urlunparse(new_parsed)

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