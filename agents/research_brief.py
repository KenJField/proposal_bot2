"""Research Brief Agent - Creates research briefs from RFPs."""

from langchain_anthropic import ChatAnthropic
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from config import RESEARCH_BRIEF_PROMPT, settings
from tools.knowledge import search_knowledge
from tools.project import query_project, update_project
from tools.email import send_email


def create_research_brief_agent():
    """
    Create the Research Brief Agent.

    Type: Deep Agent
    Model: Claude Sonnet 4.5
    Purpose: Create clear research brief from RFP with client collaboration

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
{RESEARCH_BRIEF_PROMPT}

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
Final Answer: summary of the research brief creation process and next steps

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
        max_iterations=20,
        handle_parsing_errors=True
    )

    return agent_executor


async def create_brief(project_id: str):
    """
    Create a research brief for a project.

    Args:
        project_id: Project UUID

    Returns:
        Brief creation result
    """
    agent = create_research_brief_agent()

    result = await agent.ainvoke({
        "input": f"""Create a research brief for project {project_id}.

Steps:
1. Query the project to get RFP content
2. Search knowledge base for similar projects and relevant capabilities
3. Draft initial research brief
4. Identify information gaps
5. Send questions to sales rep via email
6. Wait for response (you will be resumed when response arrives)
7. Incorporate feedback and finalize brief
8. Send final brief to sales rep for approval
9. Update project with completed brief
"""
    })

    return result


async def incorporate_feedback(project_id: str, feedback: str):
    """
    Incorporate feedback into the research brief.

    Args:
        project_id: Project UUID
        feedback: Feedback from sales rep

    Returns:
        Updated brief result
    """
    agent = create_research_brief_agent()

    result = await agent.ainvoke({
        "input": f"""Incorporate feedback into research brief for project {project_id}.

Feedback received:
{feedback}

Steps:
1. Query project to get current brief draft
2. Incorporate the feedback
3. Update the brief
4. Send updated brief to sales rep for approval
"""
    })

    return result
