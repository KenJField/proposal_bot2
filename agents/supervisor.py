"""Supervisor Agent - Orchestrates workflow and manages project lifecycle."""

from langchain_anthropic import ChatAnthropic
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from langchain.tools import tool
from config import SUPERVISOR_PROMPT, settings
from tools.email import send_email
from tools.project import (
    query_project,
    update_project,
    create_project,
    query_all_active_projects,
    update_project_status
)


@tool
async def start_research_brief(project_id: str) -> str:
    """
    Start the Research Brief Agent for a project.

    Args:
        project_id: Project UUID

    Returns:
        Status message
    """
    # In a full implementation, this would invoke the Research Brief Agent
    # For now, we update the project status and return
    await update_project(project_id, {"status": "brief_writing"})
    return f"Research Brief Agent started for project {project_id}"


@tool
async def continue_to_proposal(project_id: str) -> str:
    """
    Start the Proposal Agent for a project.

    Args:
        project_id: Project UUID

    Returns:
        Status message
    """
    await update_project(project_id, {"status": "proposal_writing"})
    return f"Proposal Agent started for project {project_id}"


@tool
async def continue_to_drafting(project_id: str) -> str:
    """
    Start the Drafting Agent for a project.

    Args:
        project_id: Project UUID

    Returns:
        Status message
    """
    await update_project(project_id, {"status": "drafting"})
    return f"Drafting Agent started for project {project_id}"


@tool
async def escalate_to_manager(project_id: str, reason: str) -> str:
    """
    Escalate a project issue to the system manager.

    Args:
        project_id: Project UUID
        reason: Reason for escalation

    Returns:
        Status message
    """
    # Get project details
    project = await query_project(project_id)

    # Send escalation email
    message = f"""
Project requiring attention:

Project ID: {project_id}
Client: {project.get('client_name', 'Unknown')}
Status: {project.get('status', 'Unknown')}
Reason: {reason}

Please review and take appropriate action.
"""

    await send_email(
        to="manager@company.com",  # Should be configurable
        subject=f"Project Escalation: {project.get('client_name', project_id)}",
        body=message,
        project_id=project_id
    )

    return f"Project {project_id} escalated to manager. Reason: {reason}"


def create_supervisor_agent():
    """
    Create the Supervisor Agent.

    Type: React Agent
    Model: Claude Sonnet 4.5
    Purpose: Orchestrate workflow, manage project lifecycle

    Returns:
        AgentExecutor instance
    """
    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.supervisor_model,
        temperature=0,
        max_tokens=4096
    )

    # Tools available to the agent
    tools = [
        start_research_brief,
        continue_to_proposal,
        continue_to_drafting,
        query_project,
        update_project,
        update_project_status,
        create_project,
        query_all_active_projects,
        send_email,
        escalate_to_manager
    ]

    # Create prompt template
    template = f"""
{SUPERVISOR_PROMPT}

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
Final Answer: the final routing decision and actions taken

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
        max_iterations=10,
        handle_parsing_errors=True
    )

    return agent_executor


async def handle_new_rfp(email_data: dict):
    """
    Handle a new RFP email.

    Args:
        email_data: Email data from triage

    Returns:
        Supervisor decision result
    """
    agent = create_supervisor_agent()

    result = await agent.ainvoke({
        "input": f"Handle new RFP email: {email_data}"
    })

    return result


async def handle_email_response(email_data: dict, project_id: str):
    """
    Handle an email response for an existing project.

    Args:
        email_data: Email data from triage
        project_id: Related project UUID

    Returns:
        Supervisor decision result
    """
    agent = create_supervisor_agent()

    result = await agent.ainvoke({
        "input": f"Handle email response for project {project_id}: {email_data}"
    })

    return result
