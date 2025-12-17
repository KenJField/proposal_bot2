"""Basic tests for agents."""

import pytest


class TestEmailTriageAgent:
    """Tests for Email Triage Agent."""

    def test_create_agent(self):
        """Test agent creation."""
        from agents.email_triage import create_email_triage_agent

        agent = create_email_triage_agent()
        assert agent is not None


class TestSupervisorAgent:
    """Tests for Supervisor Agent."""

    def test_create_agent(self):
        """Test agent creation."""
        from agents.supervisor import create_supervisor_agent

        agent = create_supervisor_agent()
        assert agent is not None


class TestResearchBriefAgent:
    """Tests for Research Brief Agent."""

    def test_create_agent(self):
        """Test agent creation."""
        from agents.research_brief import create_research_brief_agent

        agent = create_research_brief_agent()
        assert agent is not None


# Run tests with: pytest tests/test_agents.py -v
