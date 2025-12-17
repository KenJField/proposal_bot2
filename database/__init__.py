"""Database module for Supabase PostgreSQL integration."""

from .connection import db, get_db, get_vector_store, DatabaseConnection

__all__ = ['db', 'get_db', 'get_vector_store', 'DatabaseConnection']
