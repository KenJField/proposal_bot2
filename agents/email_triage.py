"""Email Triage Agent - Classifies and routes incoming emails."""

from langchain_anthropic import ChatAnthropic
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from config import EMAIL_TRIAGE_PROMPT, settings
from tools.email import read_email, get_unread_emails
from tools.project import query_project


def create_email_triage_agent():
    """
    Create the Email Triage Agent.

    Type: React Agent
    Model: Claude Haiku 4.5 (cost-effective for simple classification)
    Purpose: Classify and route incoming emails

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
        read_email,
        get_unread_emails,
        query_project
    ]

    # Create prompt template
    template = f"""
{EMAIL_TRIAGE_PROMPT}

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
Final Answer: the final classification and routing decision

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
        max_iterations=5,
        handle_parsing_errors=True
    )

    return agent_executor


async def triage_email(email_id: str):
    """
    Triage a single email.

    Args:
        email_id: Gmail message ID

    Returns:
        Classification result
    """
    agent = create_email_triage_agent()

    result = await agent.ainvoke({
        "input": f"Classify and route email with ID: {email_id}"
    })

    return result


async def process_unread_emails(max_emails: int = 10):
    """
    Process all unread emails in the inbox.

    Args:
        max_emails: Maximum number of emails to process

    Returns:
        List of classification results
    """
    agent = create_email_triage_agent()

    result = await agent.ainvoke({
        "input": f"Process up to {max_emails} unread emails from the inbox"
    })

    return result
