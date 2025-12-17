"""Database connection module for Supabase PostgreSQL."""

import os
import asyncpg
from typing import Optional
from langchain_postgres import PGVector
from langchain_openai import OpenAIEmbeddings


class DatabaseConnection:
    """Manages database connections and vector store."""

    def __init__(self):
        self.db_url = os.getenv("SUPABASE_DB_URL")
        self.pool: Optional[asyncpg.Pool] = None
        self.vector_store: Optional[PGVector] = None

    async def initialize(self):
        """Initialize database pool and vector store."""
        # Create connection pool for regular database operations
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=2,
            max_size=10,
            command_timeout=60
        )

        # Initialize vector store for knowledge base
        embeddings = OpenAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
        )

        self.vector_store = PGVector(
            embeddings=embeddings,
            collection_name="knowledge",
            connection_string=self.db_url,
            use_jsonb=True
        )

        print("✓ Database connection initialized")

    async def close(self):
        """Close database connections."""
        if self.pool:
            await self.pool.close()
            print("✓ Database connection closed")

    async def execute(self, query: str, *args):
        """Execute a database query."""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        """Fetch multiple rows from database."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        """Fetch a single row from database."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        """Fetch a single value from database."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)


# Global database instance
db = DatabaseConnection()


async def get_db() -> DatabaseConnection:
    """Get the global database instance."""
    if not db.pool:
        await db.initialize()
    return db


async def get_vector_store() -> PGVector:
    """Get the vector store instance."""
    if not db.vector_store:
        await db.initialize()
    return db.vector_store
