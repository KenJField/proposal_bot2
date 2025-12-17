"""Knowledge Agent - Extracts knowledge from email communications."""

from langchain_anthropic import ChatAnthropic
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from langchain.tools import tool
from config import KNOWLEDGE_PROMPT, settings
from tools.email import read_email
from tools.knowledge import add_knowledge, search_knowledge
from database import get_db


@tool
async def query_recent_emails(since_timestamp: str) -> list:
    """
    Query emails from email_tracking table since a timestamp.

    Args:
        since_timestamp: ISO format timestamp

    Returns:
        List of email IDs
    """
    db = await get_db()

    results = await db.fetch("""
        SELECT email_id, from_email, subject, created_at
        FROM email_tracking
        WHERE created_at > $1
          AND direction = 'inbound'
        ORDER BY created_at DESC
        LIMIT 100
    """, since_timestamp)

    emails = []
    for row in results:
        emails.append({
            "email_id": row["email_id"],
            "from": row["from_email"],
            "subject": row["subject"],
            "date": row["created_at"].isoformat()
        })

    return emails


@tool
async def create_knowledge_review_sheet(updates: list) -> str:
    """
    Create Excel review sheet for knowledge updates.

    Args:
        updates: List of knowledge items to review

    Returns:
        Path to created Excel file
    """
    import openpyxl
    from datetime import datetime

    # Create workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Knowledge Updates"

    # Headers
    headers = [
        "ID", "Knowledge Type", "Content", "Metadata (JSON)",
        "Source Email ID", "Suggested Action", "Approve?", "Notes"
    ]
    ws.append(headers)

    # Add data
    for i, item in enumerate(updates, 1):
        ws.append([
            i,
            item.get("knowledge_type", ""),
            item.get("content", ""),
            str(item.get("metadata", {})),
            item.get("source_email_id", ""),
            item.get("suggested_action", "add"),
            "",  # Approve column for manager
            ""   # Notes column for manager
        ])

    # Save file
    filename = f"/tmp/knowledge_updates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(filename)

    return filename


@tool
async def update_system_state_knowledge(key: str, value: dict) -> str:
    """
    Update system state for knowledge agent.

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


def create_knowledge_agent():
    """
    Create the Knowledge Agent.

    Type: Deep Agent
    Model: Claude Sonnet 4.5
    Purpose: Extract knowledge from email communications, propose updates

    Returns:
        AgentExecutor instance
    """
    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.deep_agent_model,
        temperature=0.2,
        max_tokens=8192
    )

    # Tools available to the agent
    tools = [
        query_recent_emails,
        read_email,
        search_knowledge,
        add_knowledge,
        create_knowledge_review_sheet,
        update_system_state_knowledge
    ]

    # Create prompt template
    template = f"""
{KNOWLEDGE_PROMPT}

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
Final Answer: summary of knowledge extraction run and items proposed

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


async def run_nightly_knowledge_extraction():
    """
    Run nightly knowledge extraction workflow.

    Returns:
        Extraction result
    """
    from datetime import datetime, timedelta

    # Get last run time from database
    db = await get_db()
    state = await db.fetchrow("""
        SELECT value FROM system_state
        WHERE key = 'knowledge_agent_last_run'
    """)

    last_run = None
    if state and state["value"]:
        last_run_str = state["value"].get("last_run_time")
        if last_run_str:
            last_run = last_run_str
        else:
            # Default to 24 hours ago
            last_run = (datetime.now() - timedelta(days=1)).isoformat()
    else:
        last_run = (datetime.now() - timedelta(days=1)).isoformat()

    agent = create_knowledge_agent()

    result = await agent.ainvoke({
        "input": f"""Run nightly knowledge extraction for {datetime.now().strftime('%Y-%m-%d')}.

Last run: {last_run}

Steps:
1. Query emails since last run
2. Analyze each email for valuable knowledge
3. Extract and categorize knowledge items
4. Create review sheet for manager approval
5. Email review sheet to manager
6. Update system_state.knowledge_agent_last_run
"""
    })

    return result
