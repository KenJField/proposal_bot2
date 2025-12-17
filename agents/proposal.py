"""Proposal Agent - Generates full proposals with validated resources and pricing."""

from langchain_anthropic import ChatAnthropic
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from config import PROPOSAL_PROMPT, settings
from tools.knowledge import search_knowledge
from tools.project import query_project, update_project
from tools.validation import (
    validate_resource,
    check_validation_responses,
    get_pending_validations
)
from tools.email import send_email


def create_proposal_agent():
    """
    Create the Proposal Agent.

    Type: Deep Agent
    Model: Claude Sonnet 4.5
    Purpose: Generate full proposal with validated resources and pricing

    Returns:
        AgentExecutor instance
    """
    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.deep_agent_model,
        temperature=0.3,
        max_tokens=8192
    )

    # Tools available to the agent
    tools = [
        search_knowledge,
        query_project,
        update_project,
        validate_resource,
        check_validation_responses,
        get_pending_validations,
        send_email
    ]

    # Create prompt template
    template = f"""
{PROPOSAL_PROMPT}

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
Final Answer: summary of the proposal generation process and next steps

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
        max_iterations=30,
        handle_parsing_errors=True
    )

    return agent_executor


async def generate_proposal(project_id: str):
    """
    Generate a proposal for a project.

    Args:
        project_id: Project UUID

    Returns:
        Proposal generation result
    """
    agent = create_proposal_agent()

    result = await agent.ainvoke({
        "input": f"""Generate a comprehensive proposal for project {project_id}.

Execute all 4 phases:

PHASE 1: PROJECT LEAD ASSIGNMENT
- Query project to get research brief and sales rep email
- Ask sales rep if they want to be project lead
- If declined, search knowledge base for suitable team member
- Assign project lead

PHASE 2: PROJECT DESIGN
- Design detailed project approach based on brief
- Search knowledge base for past similar projects
- Send design to project lead for approval
- Incorporate feedback

PHASE 3: RESOURCING & VALIDATION
- Identify all internal and external resources needed
- Send specific validation requests to each resource
- Track responses periodically
- Make assumptions if needed after timeout

PHASE 4: PRICING & FINALIZATION
- Calculate pricing based on validated resources
- Draft complete proposal text
- Send to project lead for final approval
- Update project with completed proposal
"""
    })

    return result


async def handle_validation_response(project_id: str, resource: str, response: str):
    """
    Handle a validation response and continue proposal generation.

    Args:
        project_id: Project UUID
        resource: Resource identifier
        response: Response text

    Returns:
        Result of processing the validation response
    """
    agent = create_proposal_agent()

    result = await agent.ainvoke({
        "input": f"""Process validation response for project {project_id}.

Resource: {resource}
Response: {response}

Steps:
1. Update validation response in database
2. Check if all critical validations are complete
3. Continue with pricing and finalization if ready
4. Otherwise, wait for more responses or make assumptions after timeout
"""
    })

    return result
