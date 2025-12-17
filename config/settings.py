"""Settings and configuration for the proposal automation system."""

import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    anthropic_api_key: str
    openai_api_key: str
    langsmith_api_key: Optional[str] = None

    # Supabase
    supabase_url: str
    supabase_service_key: str
    supabase_db_url: str

    # Gmail
    gmail_credentials_path: str = "credentials.json"
    gmail_token_path: str = "token.json"
    company_email: str = "proposals@company.com"

    # LangSmith
    langsmith_tracing: bool = True
    langsmith_project: str = "proposal-automation"

    # Application
    company_id: str = "default"
    environment: str = "development"

    # Email Settings
    email_check_interval: int = 120  # seconds
    validation_timeout_hours: int = 48

    # Model Configuration
    triage_model: str = "claude-haiku-4.5"
    supervisor_model: str = "claude-sonnet-4.5"
    deep_agent_model: str = "claude-sonnet-4.5"
    embedding_model: str = "text-embedding-3-large"

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
