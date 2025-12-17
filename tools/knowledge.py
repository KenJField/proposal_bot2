"""Knowledge base tools for vector search and retrieval."""

import json
from typing import Optional, Dict, Any
from langchain.tools import tool
from database import get_vector_store


@tool
async def search_knowledge(
    query: str,
    knowledge_type: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 5
) -> str:
    """
    Search company knowledge base using hybrid semantic + metadata search.

    Args:
        query: Natural language search query
        knowledge_type: Optional filter - 'capability', 'supplier', 'team_member',
                       'past_proposal', 'pricing', 'methodology'
        filters: Optional metadata filters, e.g., {"industry": "CPG", "methodology": "conjoint"}
        limit: Number of results to return (default 5)

    Returns:
        Formatted string with relevant knowledge

    Examples:
        search_knowledge("conjoint analysis pricing")
        search_knowledge("panel suppliers Germany", knowledge_type="supplier")
        search_knowledge("past brand studies", filters={"project_type": "brand_tracking"})
    """
    try:
        # Get vector store
        vector_store = await get_vector_store()

        # Build filter dictionary
        filter_dict = {"status": "active"}

        if knowledge_type:
            filter_dict["metadata.knowledge_type"] = knowledge_type

        if filters:
            for key, value in filters.items():
                filter_dict[f"metadata.{key}"] = value

        # Perform semantic search with metadata filtering
        results = vector_store.similarity_search(
            query,
            k=limit,
            filter=filter_dict
        )

        if not results:
            return f"No knowledge found matching: {query}"

        # Format results
        formatted = []
        for i, doc in enumerate(results, 1):
            metadata = doc.metadata
            source = metadata.get('knowledge_type', 'unknown')

            # Extract relevant metadata (excluding internal fields)
            relevant_metadata = {
                k: v for k, v in metadata.items()
                if k not in ['knowledge_type', 'company_id', 'created_at', 'updated_at']
            }

            formatted.append(f"""
Result {i}:
Source Type: {source}
Content: {doc.page_content}

Additional Details: {json.dumps(relevant_metadata, indent=2)}
---
            """.strip())

        return "\n\n".join(formatted)

    except Exception as e:
        return f"Error searching knowledge base: {str(e)}"


@tool
async def add_knowledge(
    content: str,
    knowledge_type: str,
    metadata: Dict[str, Any]
) -> str:
    """
    Add new knowledge to the knowledge base.

    Args:
        content: The knowledge content (text)
        knowledge_type: Type of knowledge - 'capability', 'supplier', 'team_member',
                       'past_proposal', 'pricing', 'methodology'
        metadata: Additional metadata as dictionary

    Returns:
        Confirmation message with knowledge ID

    Examples:
        add_knowledge(
            "We offer advanced conjoint analysis with 20+ years experience",
            "capability",
            {"service": "conjoint", "methodologies": ["CBC", "ACBC"]}
        )
    """
    try:
        from database import get_db
        from langchain_openai import OpenAIEmbeddings
        import os

        # Generate embedding
        embeddings = OpenAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
        )
        embedding = embeddings.embed_query(content)

        # Add knowledge_type to metadata
        full_metadata = {**metadata, "knowledge_type": knowledge_type}

        # Insert into database
        db = await get_db()
        knowledge_id = await db.fetchval("""
            INSERT INTO knowledge (content, metadata, embedding)
            VALUES ($1, $2, $3)
            RETURNING id
        """, content, json.dumps(full_metadata), embedding)

        return f"Knowledge added successfully. ID: {knowledge_id}"

    except Exception as e:
        return f"Error adding knowledge: {str(e)}"


@tool
async def update_knowledge(
    knowledge_id: str,
    content: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    status: Optional[str] = None
) -> str:
    """
    Update existing knowledge in the knowledge base.

    Args:
        knowledge_id: UUID of the knowledge entry
        content: Optional new content (will regenerate embedding)
        metadata: Optional metadata updates (merged with existing)
        status: Optional status change ('active', 'deprecated', 'archived')

    Returns:
        Confirmation message

    Examples:
        update_knowledge("123e4567-e89b-12d3-a456-426614174000", status="deprecated")
        update_knowledge("123e4567-e89b-12d3-a456-426614174000", metadata={"updated": true})
    """
    try:
        from database import get_db
        from langchain_openai import OpenAIEmbeddings
        import os

        db = await get_db()

        # Build update query parts
        updates = []
        params = [knowledge_id]
        param_idx = 2

        if content:
            # Generate new embedding
            embeddings = OpenAIEmbeddings(
                model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
            )
            embedding = embeddings.embed_query(content)

            updates.append(f"content = ${param_idx}")
            params.append(content)
            param_idx += 1

            updates.append(f"embedding = ${param_idx}")
            params.append(embedding)
            param_idx += 1

        if metadata:
            # Merge with existing metadata
            updates.append(f"metadata = metadata || ${param_idx}::jsonb")
            params.append(json.dumps(metadata))
            param_idx += 1

        if status:
            updates.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1

        if not updates:
            return "No updates specified"

        query = f"""
            UPDATE knowledge
            SET {', '.join(updates)}
            WHERE id = $1
        """

        await db.execute(query, *params)

        return f"Knowledge {knowledge_id} updated successfully"

    except Exception as e:
        return f"Error updating knowledge: {str(e)}"
