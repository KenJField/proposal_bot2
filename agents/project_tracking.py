"""Project Tracking Agent - Monitors active projects and follows up on stalled work."""

from langchain_anthropic import ChatAnthropic
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from langchain.tools import tool
from config import PROJECT_TRACKING_PROMPT, settings
from tools.project import query_all_active_projects, update_project
from tools.email import send_email
from database import get_db


@tool
async def escalate_to_supervisor(project_id: str, reason: str) -> str:
    """
    Create a task for the Supervisor to handle a project issue.

    Args:
        project_id: Project UUID
        reason: Reason for escalation

    Returns:
        Confirmation message
    """
    # In full implementation, this would create a task in a queue
    # For now, we'll just log it
    return f"Project {project_id} escalated to supervisor. Reason: {reason}"


@tool
async def update_system_state(key: str, value: dict) -> str:
    """
    Update system state table.

    Args:
        key: State key
        value: State value as dictionary

    Returns:
        Confirmation message
    """
    import json
    db = await get_db()

    await db.execute("""
        INSERT INTO system_state (key, value)
        VALUES ($1, $2)
        ON CONFLICT (key) DO UPDATE
        SET value = $2, updated_at = NOW()
    """, key, json.dumps(value))

    return f"System state '{key}' updated"


def create_project_tracking_agent():
    """
    Create the Project Tracking Agent.

    Type: React Agent
    Model: Claude Haiku 4.5 (cost-effective for monitoring)
    Purpose: Monitor all active projects, follow up on stalled work

    Returns:
        AgentExecutor instance
    """
    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.triage_model,
        temperature=0,
        max_tokens=4096
    )

    # Tools available to the agent
    tools = [
        query_all_active_projects,
        update_project,
        send_email,
        escalate_to_supervisor,
        update_system_state
    ]

    # Create prompt template
    template = f"""
{PROJECT_TRACKING_PROMPT}

You have access to the following tools:
{{tools}}

Tool Names: {{tool_names}}

Use this format:
Thought: Consider what needs to be done
Action: the action to take, should be one of [{{tool_names}}]
Action Input: the input to the action
Observation: the result of the action
... (repeat Thought/Action/Action Input/Observation as needed)
Thought: I now know the final answer
Final Answer: summary of tracking run and actions taken

Current task:
{{input}}

{{agent_scratchpad}}
"""

    prompt = PromptTemplate(
        template=template,
        input_variables=["input", "agent_scratchpad"],
        partial_variables={
            "tools": "\n".join([f"{tool.name}: {tool.description}" for tool in tools]),
            "tool_names": ", ".join([tool.name for tool in tools])
        }
    )

    # Create agent
    agent = create_react_agent(llm, tools, prompt)

    # Create executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=15,
        handle_parsing_errors=True
    )

    return agent_executor


async def run_daily_tracking():
    """
    Run daily project tracking workflow.

    Returns:
        Tracking result
    """
    from datetime import datetime

    agent = create_project_tracking_agent()

    result = await agent.ainvoke({
        "input": f"""Run daily project tracking for {datetime.now().strftime('%Y-%m-%d')}.

Steps:
1. Query all active projects
2. Check each project for:
   - Days since last activity
   - Current status
   - Deadline proximity
3. Take appropriate actions based on rules
4. Generate daily status report
5. Update system_state.project_tracking_last_run
"""
    })

    return result
