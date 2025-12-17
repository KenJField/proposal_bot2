"""Project management tools for database operations."""

import json
from typing import Dict, Any, Optional
from datetime import datetime
from langchain.tools import tool
from database import get_db


@tool
async def create_project(
    client_name: str,
    sales_rep_email: str,
    rfp_content: str,
    initial_email_id: Optional[str] = None
) -> str:
    """
    Create new project in database.

    Args:
        client_name: Name of the client company
        sales_rep_email: Email of the sales representative
        rfp_content: The RFP content/text
        initial_email_id: Optional Gmail message ID that started this project

    Returns:
        Project UUID

    Examples:
        create_project("Acme Corp", "sales@company.com", "We need a brand study...")
    """
    try:
        db = await get_db()

        project_id = await db.fetchval("""
            INSERT INTO projects
            (client_name, sales_rep_email, initial_email_id, data, status)
            VALUES ($1, $2, $3, $4, 'brief_writing')
            RETURNING id
        """, client_name, sales_rep_email, initial_email_id,
            json.dumps({"rfp_content": rfp_content}))

        return str(project_id)

    except Exception as e:
        return f"Error creating project: {str(e)}"


@tool
async def update_project(project_id: str, updates: Dict[str, Any]) -> str:
    """
    Update project fields. Flexible - can update any field in data JSONB.

    Args:
        project_id: Project UUID
        updates: Dictionary of updates. Can include:
                 - status: 'brief_writing', 'proposal_writing', etc.
                 - client_name, project_lead_email, deadline: top-level fields
                 - Any other data goes into data JSONB

    Returns:
        Confirmation message

    Examples:
        update_project("proj_123", {
            "status": "proposal_writing",
            "research_brief": "Complete brief text...",
            "methodologies": ["survey", "conjoint"],
            "estimated_cost": 50000
        })
    """
    try:
        db = await get_db()

        # Separate top-level vs JSONB fields
        top_level_fields = ['status', 'client_name', 'project_lead_email', 'deadline',
                           'supervisor_thread_id', 'brief_agent_thread_id',
                           'proposal_agent_thread_id', 'drafting_agent_thread_id']

        top_level = {k: v for k, v in updates.items() if k in top_level_fields}
        jsonb_data = {k: v for k, v in updates.items() if k not in top_level_fields}

        # Update top-level fields
        if top_level:
            set_clauses = []
            params = [project_id]
            param_idx = 2

            for key, value in top_level.items():
                set_clauses.append(f"{key} = ${param_idx}")
                params.append(value)
                param_idx += 1

            query = f"""
                UPDATE projects
                SET {', '.join(set_clauses)}
                WHERE id = $1
            """
            await db.execute(query, *params)

        # Update JSONB data
        if jsonb_data:
            await db.execute("""
                UPDATE projects
                SET data = data || $1::jsonb
                WHERE id = $2
            """, json.dumps(jsonb_data), project_id)

        return f"Project {project_id} updated successfully"

    except Exception as e:
        return f"Error updating project: {str(e)}"


@tool
async def query_project(project_id: str) -> Dict[str, Any]:
    """
    Get complete project information.

    Args:
        project_id: Project UUID

    Returns:
        Dictionary with all project data

    Examples:
        query_project("123e4567-e89b-12d3-a456-426614174000")
    """
    try:
        db = await get_db()

        result = await db.fetchrow("""
            SELECT * FROM projects WHERE id = $1
        """, project_id)

        if not result:
            return {"error": f"Project {project_id} not found"}

        # Convert to dict
        project = dict(result)

        # Merge data JSONB into main dict for convenience
        if project.get('data'):
            data = project.pop('data')
            if isinstance(data, dict):
                project.update(data)

        # Convert timestamps to ISO format
        for field in ['created_at', 'updated_at', 'deadline', 'last_email_at']:
            if field in project and project[field]:
                if isinstance(project[field], datetime):
                    project[field] = project[field].isoformat()

        return project

    except Exception as e:
        return {"error": f"Error querying project: {str(e)}"}


@tool
async def query_all_active_projects() -> list:
    """
    Get all active projects (not submitted, won, lost, or abandoned).

    Returns:
        List of project dictionaries

    Examples:
        query_all_active_projects()
    """
    try:
        db = await get_db()

        results = await db.fetch("""
            SELECT id, client_name, status, sales_rep_email, project_lead_email,
                   created_at, updated_at, deadline, last_email_at
            FROM projects
            WHERE status NOT IN ('submitted', 'won', 'lost', 'abandoned')
            ORDER BY created_at DESC
        """)

        projects = []
        for row in results:
            project = dict(row)

            # Convert timestamps to ISO format
            for field in ['created_at', 'updated_at', 'deadline', 'last_email_at']:
                if field in project and project[field]:
                    if isinstance(project[field], datetime):
                        project[field] = project[field].isoformat()

            projects.append(project)

        return projects

    except Exception as e:
        return [{"error": f"Error querying active projects: {str(e)}"}]


@tool
async def update_project_status(project_id: str, new_status: str) -> str:
    """
    Update the status of a project.

    Args:
        project_id: Project UUID
        new_status: New status - 'brief_writing', 'brief_complete', 'proposal_writing',
                   'proposal_complete', 'drafting', 'submitted', 'won', 'lost', 'abandoned'

    Returns:
        Confirmation message

    Examples:
        update_project_status("proj_123", "proposal_writing")
    """
    valid_statuses = [
        'brief_writing', 'brief_complete', 'proposal_writing',
        'proposal_complete', 'drafting', 'submitted', 'won', 'lost', 'abandoned'
    ]

    if new_status not in valid_statuses:
        return f"Invalid status. Must be one of: {', '.join(valid_statuses)}"

    return await update_project(project_id, {"status": new_status})
