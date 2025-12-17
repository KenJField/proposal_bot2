"""Email tools for Gmail integration."""

import os
from typing import Optional, List
from datetime import datetime
from langchain.tools import tool
from langchain_google_community import GmailToolkit
from database import get_db


# Initialize Gmail toolkit
gmail_toolkit = GmailToolkit()


@tool
async def send_email(
    to: str,
    subject: str,
    body: str,
    project_id: Optional[str] = None,
    attachments: Optional[List[str]] = None
) -> str:
    """
    Send an email via Gmail. Optionally associate with a project.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Email body content
        project_id: Optional project UUID to associate email
        attachments: Optional list of file paths to attach

    Returns:
        Email ID of sent message

    Examples:
        send_email("client@example.com", "Research Brief Questions", "Hi, I have a few questions...")
        send_email("jane@company.com", "Validation Request", "Are you available?", project_id="proj_123")
    """
    try:
        # Get Gmail tools from toolkit
        gmail_tools = gmail_toolkit.get_tools()
        send_tool = next(t for t in gmail_tools if "send" in t.name.lower())

        # Send email using Gmail API
        # Note: The actual implementation depends on the GmailToolkit's send message tool
        message_data = {
            "to": to,
            "subject": subject,
            "message": body
        }

        if attachments:
            message_data["attachments"] = attachments

        # Send the email
        result = send_tool.run(message_data)

        # Extract message ID from result (format depends on Gmail API response)
        message_id = result.get("id") if isinstance(result, dict) else str(result)

        # Track in database
        db = await get_db()
        await db.execute("""
            INSERT INTO email_tracking
            (email_id, project_id, direction, from_email, to_email, subject)
            VALUES ($1, $2, 'outbound', $3, $4, $5)
        """, message_id, project_id, os.getenv("COMPANY_EMAIL", "proposals@company.com"),
            [to], subject)

        # Update project last_email_at
        if project_id:
            await db.execute("""
                UPDATE projects
                SET last_email_at = NOW()
                WHERE id = $1
            """, project_id)

        return f"Email sent successfully to {to}. Message ID: {message_id}"

    except Exception as e:
        return f"Error sending email: {str(e)}"


@tool
async def read_email(email_id: str) -> dict:
    """
    Read an email by ID from Gmail.

    Args:
        email_id: Gmail message ID

    Returns:
        Dictionary with email details including from, to, subject, body, date, thread_id

    Examples:
        read_email("msg_abc123")
    """
    try:
        # Get Gmail tools from toolkit
        gmail_tools = gmail_toolkit.get_tools()
        get_tool = next(t for t in gmail_tools if "get" in t.name.lower() or "read" in t.name.lower())

        # Fetch the email
        message = get_tool.run({"message_id": email_id})

        # Parse message based on Gmail API response format
        if isinstance(message, dict):
            email_data = {
                "id": email_id,
                "from": message.get("from", ""),
                "to": message.get("to", ""),
                "subject": message.get("subject", ""),
                "body": message.get("body", message.get("snippet", "")),
                "date": message.get("date", ""),
                "thread_id": message.get("thread_id", message.get("threadId", "")),
                "attachments": message.get("attachments", [])
            }
        else:
            # Handle string response
            email_data = {
                "id": email_id,
                "raw_content": str(message)
            }

        # Track in database if not already tracked
        db = await get_db()
        await db.execute("""
            INSERT INTO email_tracking
            (email_id, direction, from_email, to_email, subject, thread_id, processed)
            VALUES ($1, 'inbound', $2, $3, $4, $5, true)
            ON CONFLICT (email_id) DO UPDATE
            SET processed = true, processed_at = NOW()
        """, email_id, email_data.get("from"), [email_data.get("to")],
            email_data.get("subject"), email_data.get("thread_id"))

        return email_data

    except Exception as e:
        return {
            "error": f"Error reading email: {str(e)}",
            "email_id": email_id
        }


@tool
async def get_unread_emails(max_results: int = 10) -> List[dict]:
    """
    Get unread emails from Gmail inbox.

    Args:
        max_results: Maximum number of emails to retrieve (default 10)

    Returns:
        List of email dictionaries

    Examples:
        get_unread_emails(5)
    """
    try:
        # Get Gmail tools from toolkit
        gmail_tools = gmail_toolkit.get_tools()
        search_tool = next(t for t in gmail_tools if "search" in t.name.lower())

        # Search for unread emails
        results = search_tool.run({
            "query": "is:unread",
            "max_results": max_results
        })

        emails = []
        if isinstance(results, list):
            for msg_id in results:
                email = await read_email(msg_id)
                if "error" not in email:
                    emails.append(email)

        return emails

    except Exception as e:
        return [{"error": f"Error fetching unread emails: {str(e)}"}]
