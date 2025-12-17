"""Validation tools for resource availability and pricing checks."""

from typing import List, Dict, Any
from datetime import datetime, timedelta
from langchain.tools import tool
from database import get_db
from .email import send_email


@tool
async def validate_resource(
    resource_identifier: str,
    validation_question: str,
    project_id: str,
    timeout_hours: int = 48
) -> str:
    """
    Send validation request to any resource (team member, supplier, partner).
    System tracks response and associates with project.

    Args:
        resource_identifier: Email address or name of person/organization
        validation_question: Specific question(s) to ask. Be detailed.
        project_id: Project UUID
        timeout_hours: Hours to wait for response (default 48)

    Returns:
        Confirmation message

    Examples:
        validate_resource(
            "jane@company.com",
            "Are you available June 1-15 for 40 hours of segmentation analysis work? What is your rate?",
            "proj_123"
        )

        validate_resource(
            "supplier@panel.com",
            "Can you provide n=500 US consumers for 10-min survey, fielded June 5-7? CPI quote?",
            "proj_123"
        )
    """
    try:
        # Send email
        email_result = await send_email(
            to=resource_identifier,
            subject=f"Project Validation Request - {project_id}",
            body=validation_question,
            project_id=project_id
        )

        # Extract email ID from result
        email_id = None
        if "Message ID:" in email_result:
            email_id = email_result.split("Message ID:")[-1].strip()

        # Track validation request
        db = await get_db()
        timeout_timestamp = datetime.now() + timedelta(hours=timeout_hours)

        await db.execute("""
            INSERT INTO validation_requests
            (project_id, resource_identifier, validation_question,
             request_email_id, timeout_at, status)
            VALUES ($1, $2, $3, $4, $5, 'pending')
        """, project_id, resource_identifier, validation_question,
            email_id, timeout_timestamp)

        return f"Validation request sent to {resource_identifier}. Response will be tracked."

    except Exception as e:
        return f"Error sending validation request: {str(e)}"


@tool
async def check_validation_responses(project_id: str) -> List[Dict[str, Any]]:
    """
    Check status of all validation requests for a project.

    Args:
        project_id: Project UUID

    Returns:
        List of validation request statuses

    Examples:
        check_validation_responses("proj_123")
    """
    try:
        db = await get_db()

        results = await db.fetch("""
            SELECT
                resource_identifier,
                validation_question,
                status,
                response_text,
                sent_at,
                responded_at,
                timeout_at
            FROM validation_requests
            WHERE project_id = $1
            ORDER BY sent_at DESC
        """, project_id)

        validations = []
        for r in results:
            validation = {
                "resource": r["resource_identifier"],
                "question": r["validation_question"],
                "status": r["status"],
                "response": r["response_text"],
                "sent": r["sent_at"].isoformat() if r["sent_at"] else None,
                "responded": r["responded_at"].isoformat() if r["responded_at"] else None,
                "timeout": r["timeout_at"].isoformat() if r["timeout_at"] else None
            }
            validations.append(validation)

        return validations

    except Exception as e:
        return [{"error": f"Error checking validation responses: {str(e)}"}]


@tool
async def update_validation_response(
    project_id: str,
    resource_identifier: str,
    response_text: str,
    response_email_id: str = None
) -> str:
    """
    Update a validation request with a response.
    Typically called by Email Triage Agent when validation response email arrives.

    Args:
        project_id: Project UUID
        resource_identifier: Email address that responded
        response_text: The response content
        response_email_id: Optional Gmail message ID of the response

    Returns:
        Confirmation message

    Examples:
        update_validation_response(
            "proj_123",
            "jane@company.com",
            "Yes, I'm available. My rate is $150/hour."
        )
    """
    try:
        db = await get_db()

        # Find the pending validation request
        result = await db.execute("""
            UPDATE validation_requests
            SET status = 'responded',
                response_text = $3,
                response_email_id = $4,
                responded_at = NOW()
            WHERE project_id = $1
              AND resource_identifier = $2
              AND status = 'pending'
        """, project_id, resource_identifier, response_text, response_email_id)

        return f"Validation response recorded for {resource_identifier}"

    except Exception as e:
        return f"Error updating validation response: {str(e)}"


@tool
async def mark_validation_timeout(validation_id: str) -> str:
    """
    Mark a validation request as timed out.

    Args:
        validation_id: Validation request UUID

    Returns:
        Confirmation message

    Examples:
        mark_validation_timeout("val_123")
    """
    try:
        db = await get_db()

        await db.execute("""
            UPDATE validation_requests
            SET status = 'timeout'
            WHERE id = $1 AND status = 'pending'
        """, validation_id)

        return f"Validation {validation_id} marked as timed out"

    except Exception as e:
        return f"Error marking validation timeout: {str(e)}"


@tool
async def get_pending_validations(project_id: str) -> List[Dict[str, Any]]:
    """
    Get all pending (unanswered) validation requests for a project.

    Args:
        project_id: Project UUID

    Returns:
        List of pending validation requests

    Examples:
        get_pending_validations("proj_123")
    """
    try:
        db = await get_db()

        results = await db.fetch("""
            SELECT
                id,
                resource_identifier,
                validation_question,
                sent_at,
                timeout_at
            FROM validation_requests
            WHERE project_id = $1 AND status = 'pending'
            ORDER BY sent_at ASC
        """, project_id)

        pending = []
        for r in results:
            validation = {
                "id": str(r["id"]),
                "resource": r["resource_identifier"],
                "question": r["validation_question"],
                "sent": r["sent_at"].isoformat() if r["sent_at"] else None,
                "timeout": r["timeout_at"].isoformat() if r["timeout_at"] else None
            }
            pending.append(validation)

        return pending

    except Exception as e:
        return [{"error": f"Error getting pending validations: {str(e)}"}]
