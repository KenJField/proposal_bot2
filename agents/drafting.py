"""Drafting Agent - Converts proposals to professional documents."""

from langchain_anthropic import ChatAnthropic
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from config import DRAFTING_PROMPT, settings
from tools.knowledge import search_knowledge
from tools.project import query_project, update_project
from tools.email import send_email


def create_drafting_agent():
    """
    Create the Drafting Agent.

    Type: Deep Agent
    Model: Claude Sonnet 4.5
    Purpose: Convert proposal to professional documents (PowerPoint, Word, PDF)

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
        send_email
    ]

    # Create prompt template
    template = f"""
{DRAFTING_PROMPT}

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
Final Answer: summary of document creation process and next steps

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
        max_iterations=25,
        handle_parsing_errors=True
    )

    return agent_executor


async def create_documents(project_id: str):
    """
    Create professional documents for a proposal.

    Args:
        project_id: Project UUID

    Returns:
        Document creation result
    """
    agent = create_drafting_agent()

    result = await agent.ainvoke({
        "input": f"""Create professional proposal documents for project {project_id}.

Steps:
1. Query project to get approved proposal text
2. Search knowledge base for templates and standard assets
3. Create document production plan
4. Send plan to project lead for approval
5. Generate documents (PowerPoint, Word, PDF as needed)
6. Send drafts to project lead for review
7. Incorporate feedback and iterate
8. Finalize documents
9. Update project status to 'submitted'
"""
    })

    return result
