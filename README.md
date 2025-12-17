# Proposal Automation System - Complete Architectural Specification

**Version:** 1.0  
**Date:** December 2025  
**Purpose:** Multi-agent AI system for automating market research proposal workflows

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Data Layer (Supabase)](#data-layer-supabase)
4. [Agent Specifications](#agent-specifications)
5. [Tool Specifications](#tool-specifications)
6. [Workflow Patterns](#workflow-patterns)
7. [Implementation Guide](#implementation-guide)
8. [Testing Strategy](#testing-strategy)

---

## System Overview

### Purpose
Automate the market research proposal process from initial RFP email through final document delivery using intelligent AI agents that:
- Process incoming email requests
- Create research briefs with client collaboration
- Generate proposals with resource validation
- Produce professional proposal documents
- Track project status
- Learn and update company knowledge

### Core Principles
1. **Simple, atomic tools** - Agents compose tools intelligently
2. **Leverage LLM reasoning** - Avoid over-engineering business logic
3. **Human-in-the-loop** - Critical decisions require approval
4. **Unified data store** - Supabase for everything (vector KB + projects DB)
5. **Email-driven workflow** - Primary interface for human interaction

### Technology Stack
- **Framework:** LangChain (Python) with Deep Agents
- **Deployment:** LangSmith Deployment
- **Database:** Supabase (PostgreSQL + pgvector)
- **Email:** Gmail API via LangChain toolkit
- **Models:** Claude Sonnet 4.5 (primary), Claude Haiku 4.5 (triage/tracking)
- **Embeddings:** OpenAI text-embedding-3-large

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                  GMAIL INBOX (proposals@company.com)             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Email Triage    │ (React Agent - Haiku)
                    │ Agent           │ Classification & Routing
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Supervisor     │ (React Agent - Sonnet)
                    │  Agent          │ Workflow Orchestration
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
 ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
 │Research Brief│   │  Proposal    │   │  Drafting    │
 │Agent         │   │  Agent       │   │  Agent       │
 │(Deep-Sonnet) │   │(Deep-Sonnet) │   │(Deep-Sonnet) │
 └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
        │                  │                   │
        │      ┌───────────┴─────────┐        │
        │      │                     │        │
        ▼      ▼                     ▼        ▼
   ┌────────────────────────────────────────────────┐
   │         Email Communication Subagent            │
   │         (spawned by each Deep Agent)           │
   │         Handles all email send/receive         │
   └────────────────────────────────────────────────┘

Cron-Triggered Agents:
┌──────────────────┐         ┌──────────────────┐
│  Project         │         │  Knowledge       │
│  Tracking Agent  │         │  Agent           │
│  (React-Haiku)   │         │  (Deep-Sonnet)   │
│  Daily 9 AM      │         │  Nightly 2 AM    │
└──────────────────┘         └──────────────────┘

Shared Data Layer (Supabase):
┌──────────────────────────────────────────────────┐
│  Knowledge Table (pgvector)                      │
│  - Capabilities, Suppliers, Team, Past Work      │
├──────────────────────────────────────────────────┤
│  Projects Table                                  │
│  - Project state, status, participants           │
├──────────────────────────────────────────────────┤
│  Validation Requests Table                       │
│  - Resource validation tracking                  │
├──────────────────────────────────────────────────┤
│  Email Tracking Table                            │
│  - Maps emails to projects/agents                │
└──────────────────────────────────────────────────┘
```

### Agent Types

**React Agents:** Simple routing/classification (Triage, Supervisor, Tracking)  
**Deep Agents:** Complex multi-step work (Brief, Proposal, Drafting, Knowledge)  
**Subagents:** Spawned for context isolation (Email communication)

---

## Data Layer (Supabase)

### Database Schema

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Knowledge Base Table
CREATE TABLE knowledge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id TEXT DEFAULT 'default',
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    embedding VECTOR(1536),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'deprecated', 'archived'))
);

CREATE INDEX idx_knowledge_embedding ON knowledge 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_knowledge_metadata ON knowledge USING gin (metadata);
CREATE INDEX idx_knowledge_company ON knowledge (company_id, status);

-- Example metadata structures:
-- Capability: {"knowledge_type": "capability", "service": "qualitative", "methodologies": ["IDI", "focus_groups"]}
-- Supplier: {"knowledge_type": "supplier", "supplier_name": "X", "services": ["panel"], "typical_cpi": 8.5}
-- Team: {"knowledge_type": "team_member", "name": "Jane", "skills": ["conjoint", "R"], "email": "jane@"}
-- Past work: {"knowledge_type": "past_proposal", "project_type": "brand_study", "methodologies": ["survey"]}
-- Pricing: {"knowledge_type": "pricing", "service": "programming", "base_rate": 150}

-- 2. Projects Table
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id TEXT DEFAULT 'default',
    status TEXT NOT NULL DEFAULT 'brief_writing' 
        CHECK (status IN ('brief_writing', 'brief_complete', 'proposal_writing', 
                         'proposal_complete', 'drafting', 'submitted', 'won', 'lost', 'abandoned')),
    
    -- Core data
    client_name TEXT,
    sales_rep_email TEXT NOT NULL,
    project_lead_email TEXT,
    
    -- Flexible JSONB for all other data
    data JSONB NOT NULL DEFAULT '{}',
    -- data structure:
    -- {
    --   "rfp_content": "...",
    --   "research_brief": "...",
    --   "proposal_text": "...",
    --   "methodologies": ["survey", "conjoint"],
    --   "estimated_cost": 50000,
    --   "timeline_weeks": 8,
    --   "requirements": {...},
    --   "team_assigned": ["jane@", "bob@"],
    --   "suppliers": ["supplier1@"],
    --   "notes": "..."
    -- }
    
    -- Thread IDs for agent continuation
    supervisor_thread_id UUID,
    brief_agent_thread_id UUID,
    proposal_agent_thread_id UUID,
    drafting_agent_thread_id UUID,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deadline TIMESTAMP,
    
    -- Email tracking
    initial_email_id TEXT,
    last_email_at TIMESTAMP
);

CREATE INDEX idx_projects_status ON projects (company_id, status);
CREATE INDEX idx_projects_lead ON projects (project_lead_email);
CREATE INDEX idx_projects_data ON projects USING gin (data);

-- 3. Validation Requests Table
CREATE TABLE validation_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    
    resource_identifier TEXT NOT NULL,  -- Email or name
    validation_question TEXT NOT NULL,
    
    status TEXT DEFAULT 'pending' 
        CHECK (status IN ('pending', 'responded', 'timeout', 'cancelled')),
    
    request_email_id TEXT,
    response_email_id TEXT,
    response_text TEXT,
    
    sent_at TIMESTAMP DEFAULT NOW(),
    responded_at TIMESTAMP,
    timeout_at TIMESTAMP,
    
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_validation_project ON validation_requests (project_id, status);
CREATE INDEX idx_validation_resource ON validation_requests (resource_identifier);

-- 4. Email Tracking Table
CREATE TABLE email_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id TEXT UNIQUE NOT NULL,  -- Gmail message ID
    thread_id TEXT,                  -- Gmail thread ID
    
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    email_type TEXT,  -- 'new_rfp', 'brief_response', 'validation_request', etc.
    
    from_email TEXT,
    to_email TEXT[],
    subject TEXT,
    
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_email_thread ON email_tracking (thread_id);
CREATE INDEX idx_email_project ON email_tracking (project_id);
CREATE INDEX idx_email_processed ON email_tracking (processed, created_at);

-- 5. System State Table (for cron agents, etc.)
CREATE TABLE system_state (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert initial states
INSERT INTO system_state (key, value) VALUES 
    ('knowledge_agent_last_run', '{"last_run_time": null}'),
    ('project_tracking_last_run', '{"last_run_time": null}');

-- 6. Audit Log (optional but recommended)
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL,
    action TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_project ON audit_log (project_id, created_at DESC);

-- Helper function for updating timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### Supabase Connection

```python
# .env file
SUPABASE_URL=https://yourproject.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
SUPABASE_DB_URL=postgresql://postgres:your_password@db.yourproject.supabase.co:5432/postgres

# Connection setup
import os
from langchain_postgres import PGVector
from langchain_openai import OpenAIEmbeddings
import asyncpg

# Vector store
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
vector_store = PGVector(
    embeddings=embeddings,
    collection_name="knowledge",
    connection_string=os.getenv("SUPABASE_DB_URL")
)

# Database pool for projects/tracking
db_pool = await asyncpg.create_pool(os.getenv("SUPABASE_DB_URL"))
```

---

## Agent Specifications

### 1. Email Triage Agent

**Type:** React Agent  
**Model:** Claude Haiku 4.5 (cost-effective for simple classification)  
**Trigger:** Gmail webhook or polling (every 2 minutes)

**Purpose:** Classify and route incoming emails

**Tools:**
- `read_email(email_id)` - Gmail tool
- `update_email_tracking(email_id, data)` - DB update
- `create_supervisor_task(task_data)` - Queue task for supervisor

**System Prompt:**
```
You classify incoming emails to proposals@company.com.

For each email, determine:
1. Type: 'new_rfp', 'brief_response', 'proposal_response', 'validation_response', 
   'status_inquiry', 'general', 'spam'
2. Related project (if any) - check email thread, subject line, or body references
3. Priority: 'urgent', 'normal', 'low'

CLASSIFICATION LOGIC:
- New RFP: Contains RFP, proposal request, or formal procurement language
- Brief response: Reply to email about research brief questions
- Proposal response: Reply about proposal or decision
- Validation response: From resource (check validation_requests table)
- Status inquiry: Asking about project status
- General: Questions, requests not tied to specific project
- Spam: Marketing, unrelated content

After classification:
1. Update email_tracking table
2. If validation_response: update validation_requests table
3. Create task for Supervisor with structured data

Be decisive and fast. If uncertain, default to 'general' and let Supervisor handle it.
```

**Output Format:**
```python
{
    "email_id": "msg_123",
    "classification": "new_rfp",
    "project_id": None,  # or UUID if found
    "priority": "normal",
    "extracted_data": {
        "client_name": "Acme Corp",
        "deadline": "2025-02-15",
        "key_requirements": ["brand study", "n=1000"]
    }
}
```

---

### 2. Supervisor Agent

**Type:** React Agent  
**Model:** Claude Sonnet 4.5  
**Trigger:** Tasks from Email Triage or cron schedule

**Purpose:** Orchestrate workflow, manage project lifecycle

**Tools:**
- `start_research_brief(project_data)` - Invoke Brief Agent
- `continue_to_proposal(project_id)` - Invoke Proposal Agent
- `continue_to_drafting(project_id)` - Invoke Drafting Agent
- `check_project_status(project_id)` - Query DB
- `update_project(project_id, updates)` - Update DB
- `send_email(to, subject, body, project_id)` - Gmail
- `escalate_to_manager(project_id, reason)` - Alert system manager

**System Prompt:**
```
You coordinate proposal workflows from RFP to delivery.

STANDARD WORKFLOW:
1. New RFP → Start Research Brief Agent
2. Brief complete → Continue to Proposal Agent
3. Proposal complete → Continue to Drafting Agent
4. Drafting complete → Mark submitted, wait for decision
5. Decision received → Update status (won/lost)

NON-LINEAR FLOWS:
- Brief needs clarification → Brief Agent handles, may return multiple times
- Proposal needs design changes → Proposal Agent handles
- Validation delays → Proposal Agent decides (wait/assume/escalate)
- Stuck projects (>7 days no activity) → Escalate to manager

PROJECT STATUS MANAGEMENT:
- Keep projects table updated with current status
- Track which agent is currently working on each project
- Resume agents when responses arrive (using thread IDs)

ROUTING DECISIONS:
- Email classified as 'brief_response' → Resume Brief Agent thread
- Email classified as 'proposal_response' → Resume Proposal Agent thread  
- Email classified as 'validation_response' → Update validation table, notify relevant agent
- Email classified as 'status_inquiry' → Query status and respond directly

You are the orchestrator. Agents do the work. You route and track.
```

---

### 3. Research Brief Agent

**Type:** Deep Agent  
**Model:** Claude Sonnet 4.5  
**Invocation:** Supervisor starts for new projects

**Purpose:** Create clear research brief from RFP with client collaboration

**Main Agent Tools:**
- `search_knowledge(query, type, filters)`
- `update_project(project_id, updates)`
- `query_project(project_id)`

**Subagent:** Email Communication Subagent
- **Purpose:** Handle all email send/receive to avoid context overflow
- **Tools:** `send_email()`, `read_email()`
- **Pattern:** Main agent delegates "send email asking X" to subagent

**System Prompt:**
```
You create research briefs from RFPs through collaboration with the sales representative.

WORKFLOW:
1. Read RFP content from project data
2. Search knowledge base for similar past projects, methodologies, capabilities
3. Draft initial research brief with:
   - Client objectives
   - Research questions
   - Recommended approach (high-level)
   - Sample size and timeline guidance
   - Key deliverables
4. Identify information gaps - what's unclear or missing
5. Use Email Communication Subagent to send questions to sales rep
6. Wait for responses (you'll be resumed when they arrive)
7. Incorporate answers, refine brief
8. Use Email Communication Subagent to send final brief for approval
9. Wait for approval (human-in-the-loop interrupt)
10. Update project with completed brief, return to Supervisor

USE EMAIL SUBAGENT:
- Spawn subagent with: "Send email to {sales_rep} asking: {questions}"
- Subagent handles email composition and sending
- You focus on brief content and logic
- This prevents email details from cluttering your context

KNOWLEDGE BASE USAGE:
- Search for similar project types to learn from past approaches
- Find capability descriptions relevant to requirements
- Check methodology guidance for specific techniques mentioned
- Look for team members with relevant expertise

Be thorough but don't wait indefinitely. If sales rep doesn't respond in 3 days, 
make reasonable assumptions and note them in the brief.
```

**Filesystem Usage:**
```
/brief_draft.md - Current draft of research brief
/questions_for_client.md - Outstanding questions
/information_gaps.json - Structured list of what's missing
/knowledge_gathered.md - Relevant findings from KB
```

---

### 4. Proposal Agent

**Type:** Deep Agent  
**Model:** Claude Sonnet 4.5  
**Invocation:** Supervisor starts when brief is complete

**Purpose:** Generate full proposal with validated resources and pricing

**Main Agent Tools:**
- `search_knowledge(query, type, filters)`
- `validate_resource(resource, question, project_id)`
- `check_validation_responses(project_id)`
- `update_project(project_id, updates)`
- `query_project(project_id)`

**Subagents:**
1. **Email Communication Subagent** - All email operations
2. **Pricing Calculation Subagent** (optional) - Complex pricing logic

**System Prompt:**
```
You generate comprehensive proposals for market research projects.

WORKFLOW - 4 PHASES:

PHASE 1: PROJECT LEAD ASSIGNMENT
1. Load research brief from project data
2. Check if sales rep wants to be project lead
   → Use Email Subagent to ask
   → Wait for response
3. If declined, recommend alternative based on:
   → Project type, methodologies needed
   → Search knowledge base for team expertise
   → Use Email Subagent to propose alternative to sales rep
   → Wait for confirmation (HITL approval)
4. Update project.project_lead_email

PHASE 2: PROJECT DESIGN  
5. Design project approach based on brief:
   → Specific methodologies and why
   → Sample design and specifications
   → Timeline with key milestones
   → Deliverables list
   → High-level team structure
6. Search knowledge base for:
   → Past similar projects (learn from approaches)
   → Methodology best practices
   → Capability descriptions to reference
7. Use Email Subagent to send design to project lead for review
8. Wait for approval (HITL interrupt)
9. Incorporate any feedback

PHASE 3: RESOURCING & VALIDATION
10. Based on approved design, identify ALL resources needed:
    → Internal: analysts, programmers, project managers, etc.
    → External: suppliers (panel, translation, facilities, etc.)
11. For EACH resource, use validate_resource() with specific questions:
    Examples:
    - "Jane, are you available June 1-15 for 40hrs segmentation analysis? Rate?"
    - "Supplier X, can you provide n=500 US consumers, 10min survey, by June 5? CPI?"
    - "Bob, available May 1-10 for MaxDiff programming? Estimated hours?"
12. Send all validations in parallel (don't wait for each)
13. Check responses periodically with check_validation_responses()
14. After 48 hours OR when all critical validations received:
    → If missing responses: make reasonable assumptions, note in proposal
    → If validations reveal issues: revise design, loop back to project lead
15. Document all validated resources in project data

PHASE 4: PRICING & FINALIZATION
16. Calculate pricing based on validated inputs:
    → Labor hours × rates
    → Supplier costs
    → Apply margin rules (search knowledge base for pricing guidance)
    → Add contingency buffer if needed
17. Draft complete proposal text:
    → Executive summary
    → Objectives and approach
    → Detailed methodology
    → Timeline and deliverables
    → Team and capabilities
    → Investment and terms
18. Use Email Subagent to send to project lead for final approval
19. Wait for approval (HITL interrupt)
20. Update project with completed proposal, return to Supervisor

KEY PRINCIPLES:
- Use search_knowledge() extensively - don't invent capabilities
- Be specific in validation questions - avoid vague "are you available?"
- Parallel validation is efficient - don't wait sequentially
- If stuck waiting, make reasonable assumptions and document them
- The Email Subagent keeps your context clean - use it for all email work
- Project lead approves major decisions (design, final proposal)

INTELLIGENCE:
You decide:
- WHO needs to be validated
- WHAT specific questions to ask each person
- WHEN to stop waiting and proceed with assumptions
- HOW to structure the proposal for maximum clarity
```

**Filesystem Usage:**
```
/project_design.md - Approved project approach
/validated_resources.json - Structured data on all resources
/validation_status.md - Tracking validation requests
/pricing_calculations.json - Detailed cost breakdown
/proposal_draft.md - Current proposal text
/assumptions.md - Assumptions made due to incomplete validation
```

---

### 5. Drafting Agent

**Type:** Deep Agent  
**Model:** Claude Sonnet 4.5  
**Invocation:** Supervisor starts when proposal is approved

**Purpose:** Convert proposal to professional documents (PowerPoint, Word, PDF)

**Main Agent Tools:**
- `search_knowledge(query, type, filters)` - Find assets
- `update_project(project_id, updates)`
- `query_project(project_id)`

**Subagents:**
1. **Email Communication Subagent** - For review/approval emails
2. **Document Generation Subagents** - Use Claude Skills
   - PowerPoint Subagent (reads `/mnt/skills/public/pptx/SKILL.md`)
   - Word Doc Subagent (reads `/mnt/skills/public/docx/SKILL.md`)
   - PDF Subagent (reads `/mnt/skills/public/pdf/SKILL.md`)

**System Prompt:**
```
You convert approved proposals into professional presentation documents.

WORKFLOW:
1. Load proposal text and submission requirements from project data
2. Create document production plan:
   → Format needed (PowerPoint, Word, PDF, or combination)
   → Slide/page structure
   → Visual elements needed (charts, images, etc.)
   → Brand assets to include (logo, templates)
3. Use Email Subagent to send plan to project lead for approval
4. Wait for approval (HITL interrupt)

5. Search knowledge base for standard assets:
   → Company templates
   → Standard slides (capabilities, team bios)
   → Marketing boilerplate
   → Past proposal examples in similar format
   
6. Spawn Document Generation Subagents:
   → Read appropriate SKILL.md file first (pptx, docx, or pdf)
   → Each subagent creates one document type
   → Subagents use Claude skills for document creation
   → Save to /mnt/user-data/outputs/

7. Use Email Subagent to send drafts to project lead
8. Wait for feedback
9. Iterate on revisions (spawn new document subagents as needed)
10. When approved, finalize and return to Supervisor

DOCUMENT QUALITY:
- Follow best practices from SKILL.md files
- Use corporate templates if available in knowledge base
- Ensure consistent branding throughout
- Professional formatting and layout
- Clear structure with logical flow

SUBAGENT USAGE:
- Email Subagent: All communication with project lead
- Document Subagents: One per document type, reads relevant SKILL.md
- This keeps your context focused on coordination, not document details
```

**Filesystem Usage:**
```
/document_plan.md - Production plan
/assets/ - Downloaded templates, logos, standard content
/drafts/ - Versioned document drafts
/feedback.md - Collected feedback from reviews
```

---

### 6. Project Tracking Agent

**Type:** React Agent  
**Model:** Claude Haiku 4.5  
**Trigger:** Cron (daily at 9 AM)

**Purpose:** Monitor all active projects, follow up on stalled work

**Tools:**
- `query_all_active_projects()` - DB query
- `send_email(to, subject, body, project_id)` - Gmail
- `update_project(project_id, updates)` - DB update
- `escalate_to_supervisor(project_id, reason)` - Create supervisor task

**System Prompt:**
```
You monitor all active projects and ensure nothing falls through the cracks.

DAILY WORKFLOW:
1. Query all projects NOT in 'submitted', 'won', 'lost', 'abandoned'
2. For each project, check:
   - Days since last_email_at
   - Current status
   - Deadline proximity
   
3. ACTION RULES:
   - >3 days no activity, status = 'brief_writing' → Email sales rep
   - >3 days no activity, status = 'proposal_writing' → Email project lead
   - >5 days no activity, any status → Escalate to supervisor
   - <7 days to deadline, not 'submitted' → Alert project lead + supervisor
   - >14 days no activity → Suggest marking 'abandoned'

4. For 'submitted' projects >30 days old:
   - Email project lead: "Any decision from client on Project X?"
   - Based on response, update status to 'won', 'lost', or keep 'submitted'

5. Generate daily status report:
   - Active projects by status
   - Projects needing attention
   - Projects near deadline
   - Recent wins/losses

TONE:
- Friendly but professional
- "Just checking in on Project X..." 
- Offer help: "Do you need any support to move this forward?"
- Don't be pushy, be helpful

OUTPUT:
After run, update system_state.project_tracking_last_run
```

---

### 7. Knowledge Agent

**Type:** Deep Agent  
**Model:** Claude Sonnet 4.5  
**Trigger:** Cron (nightly at 2 AM)

**Purpose:** Extract knowledge from email communications, propose updates

**Tools:**
- `query_recent_emails(since_timestamp)` - DB query
- `read_email(email_id)` - Gmail
- `generate_embedding(text)` - Embeddings API
- `create_knowledge_review_sheet(updates)` - Generate Excel
- `send_email(to, subject, body, attachments)` - Gmail

**System Prompt:**
```
You identify valuable knowledge in email communications and propose additions 
to the knowledge base.

NIGHTLY WORKFLOW:
1. Query email_tracking table for emails since last run
2. For each email, analyze content for knowledge:
   
   LOOK FOR:
   - New capabilities or services mentioned
   - Supplier updates (contact changes, new services, pricing)
   - Team member updates (new skills, certifications, availability)
   - Methodology descriptions or new approaches
   - Pricing changes or rate adjustments
   - Past project results and outcomes
   - Client feedback on deliverables
   
   IGNORE:
   - Routine project updates
   - Scheduling/logistics
   - Personal conversations
   - Spam/marketing

3. For each knowledge item found:
   - Extract content (summarize clearly)
   - Generate appropriate metadata
   - Create embedding
   - Determine knowledge_type
   - Note source email for traceability

4. Create Excel review sheet with columns:
   - ID (auto-generated)
   - Knowledge Type
   - Content (the knowledge text)
   - Metadata (JSON)
   - Embedding (base64)
   - Source Email ID
   - Suggested Action (add/update/archive)
   - Approve? (Y/N - for manager)
   - Notes (for manager comments)

5. Email Excel to system manager:
   Subject: "Knowledge Base Updates for Review (X items)"
   Body: Instructions for review and approval
   Attachment: Review spreadsheet

6. Check for previously approved sheets in designated folder
7. For approved items, insert into Supabase knowledge table
8. Update system_state.knowledge_agent_last_run

QUALITY STANDARDS:
- Content should be clear, concise, actionable
- Avoid duplicate knowledge (check existing KB first)
- Metadata should enable effective filtering
- Only propose high-value knowledge, not minutiae
```

**Excel Sheet Format:**
```
| ID | Type | Content | Metadata (JSON) | Embedding | Source | Action | Approve? | Notes |
|----|------|---------|----------------|-----------|--------|--------|----------|-------|
| 1  | supplier | "Supplier X now offers German panel..." | {...} | [base64] | email_123 | add | Y | |
| 2  | team_member | "Jane completed conjoint certification..." | {...} | [base64] | email_456 | update | Y | |
```

---

## Tool Specifications

### Email Tools

```python
from langchain.tools import tool
from langchain_google_community import GmailToolkit

gmail = GmailToolkit()

@tool
def send_email(
    to: str,
    subject: str,
    body: str,
    project_id: str = None,
    attachments: list[str] = None
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
    """
    # Use Gmail API to send
    message_id = gmail.send_message(
        to=to,
        subject=subject,
        message=body,
        attachments=attachments
    )
    
    # Track in database
    await db.execute("""
        INSERT INTO email_tracking 
        (email_id, project_id, direction, from_email, to_email, subject)
        VALUES ($1, $2, 'outbound', 'proposals@company.com', $3, $4)
    """, message_id, project_id, [to], subject)
    
    # Update project last_email_at
    if project_id:
        await db.execute("""
            UPDATE projects 
            SET last_email_at = NOW()
            WHERE id = $1
        """, project_id)
    
    return f"Email sent successfully. ID: {message_id}"

@tool
def read_email(email_id: str) -> dict:
    """
    Read an email by ID from Gmail.
    
    Args:
        email_id: Gmail message ID
        
    Returns:
        Dictionary with email details
    """
    message = gmail.get_message(email_id)
    
    return {
        "id": email_id,
        "from": message.get("from"),
        "to": message.get("to"),
        "subject": message.get("subject"),
        "body": message.get("body"),
        "date": message.get("date"),
        "thread_id": message.get("thread_id"),
        "attachments": message.get("attachments", [])
    }
```

### Knowledge Base Tool

```python
@tool
async def search_knowledge(
    query: str,
    knowledge_type: str = None,
    filters: dict = None,
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
    # Build filter dict
    filter_dict = {"status": "active"}
    if knowledge_type:
        filter_dict["metadata.knowledge_type"] = knowledge_type
    if filters:
        for key, value in filters.items():
            filter_dict[f"metadata.{key}"] = value
    
    # Semantic search with metadata filtering
    results = vector_store.similarity_search(
        query,
        k=limit,
        filter=filter_dict
    )
    
    if not results:
        return f"No knowledge found matching: {query}"
    
    # Format results
    formatted = []
    for doc in results:
        metadata = doc.metadata
        source = metadata.get('knowledge_type', 'unknown')
        
        formatted.append(f"""
Source: {source}
{doc.page_content}

Metadata: {json.dumps({k: v for k, v in metadata.items() if k != 'knowledge_type'}, indent=2)}
---
        """)
    
    return "\n".join(formatted)
```

### Resource Validation Tool

```python
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
            "Are you available June 1-15 for 40 hours of segmentation analysis work? Rate?",
            "proj_123"
        )
        
        validate_resource(
            "supplier@panel.com",
            "Can you provide n=500 US consumers for 10-min survey, fielded June 5-7? CPI quote?",
            "proj_123"
        )
    """
    # Send email
    email_id = await send_email(
        to=resource_identifier,
        subject=f"Project Validation Request - {project_id}",
        body=validation_question,
        project_id=project_id
    )
    
    # Track validation request
    timeout_timestamp = datetime.now() + timedelta(hours=timeout_hours)
    
    await db.execute("""
        INSERT INTO validation_requests 
        (project_id, resource_identifier, validation_question, 
         request_email_id, timeout_at, status)
        VALUES ($1, $2, $3, $4, $5, 'pending')
    """, project_id, resource_identifier, validation_question, 
        email_id, timeout_timestamp)
    
    return f"Validation request sent to {resource_identifier}. Response will be tracked."

@tool
async def check_validation_responses(project_id: str) -> list[dict]:
    """
    Check status of all validation requests for a project.
    
    Args:
        project_id: Project UUID
        
    Returns:
        List of validation request statuses
    """
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
    
    return [
        {
            "resource": r["resource_identifier"],
            "question": r["validation_question"],
            "status": r["status"],
            "response": r["response_text"],
            "sent": r["sent_at"].isoformat() if r["sent_at"] else None,
            "responded": r["responded_at"].isoformat() if r["responded_at"] else None,
            "timeout": r["timeout_at"].isoformat() if r["timeout_at"] else None
        }
        for r in results
    ]
```

### Project Management Tools

```python
@tool
async def update_project(project_id: str, updates: dict) -> str:
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
    # Separate top-level vs JSONB fields
    top_level_fields = ['status', 'client_name', 'project_lead_email', 'deadline']
    top_level = {k: v for k, v in updates.items() if k in top_level_fields}
    jsonb_data = {k: v for k, v in updates.items() if k not in top_level_fields}
    
    # Build update query
    if top_level:
        set_clauses = [f"{k} = ${i+2}" for i, k in enumerate(top_level.keys())]
        query = f"""
            UPDATE projects 
            SET {', '.join(set_clauses)}
            WHERE id = $1
        """
        await db.execute(query, project_id, *top_level.values())
    
    # Update JSONB
    if jsonb_data:
        await db.execute("""
            UPDATE projects 
            SET data = data || $1::jsonb
            WHERE id = $2
        """, json.dumps(jsonb_data), project_id)
    
    return f"Project {project_id} updated successfully"

@tool
async def query_project(project_id: str) -> dict:
    """
    Get complete project information.
    
    Args:
        project_id: Project UUID
        
    Returns:
        Dictionary with all project data
    """
    result = await db.fetchrow("""
        SELECT * FROM projects WHERE id = $1
    """, project_id)
    
    if not result:
        return {"error": f"Project {project_id} not found"}
    
    project = dict(result)
    # Merge data JSONB into main dict for convenience
    if project.get('data'):
        project.update(project['data'])
    
    return project

@tool
async def create_project(
    client_name: str,
    sales_rep_email: str,
    rfp_content: str,
    initial_email_id: str = None
) -> str:
    """
    Create new project in database.
    
    Returns:
        Project UUID
    """
    project_id = await db.fetchval("""
        INSERT INTO projects 
        (client_name, sales_rep_email, initial_email_id, data, status)
        VALUES ($1, $2, $3, $4, 'brief_writing')
        RETURNING id
    """, client_name, sales_rep_email, initial_email_id,
        json.dumps({"rfp_content": rfp_content}))
    
    return str(project_id)
```

---

## Workflow Patterns

### Email Response Handling (Critical Pattern)

**Problem:** When agent sends email and waits for response, how does system resume?

**Solution:**

```python
# 1. Agent sends email and interrupts
research_brief_agent.invoke({...})
# Agent uses Email Subagent to send questions, then returns:
return {
    "status": "awaiting_response",
    "waiting_for": "sales_rep_clarification",
    "sent_email_id": "email_123",
    "thread_id": agent_thread_id
}

# 2. Email Triage classifies incoming response
email_triage_agent.invoke({
    "email_id": "email_456"  # Response arrives
})
# Output:
{
    "classification": "brief_response",
    "project_id": "proj_123"
}

# 3. Supervisor resumes appropriate agent
supervisor_agent.invoke({
    "action": "resume_agent",
    "project_id": "proj_123",
    "agent_type": "research_brief",  # Determined from project.status
    "new_data": {
        "response_email_id": "email_456",
        "response_content": "..."
    }
})

# 4. LangGraph resumes from checkpoint
config = {
    "configurable": {
        "thread_id": project["brief_agent_thread_id"]
    }
}
research_brief_agent.invoke(
    {"new_email_response": response_content},
    config=config  # Resumes from last checkpoint
)
```

### Human-in-the-Loop Approvals

```python
from langchain.agents.middleware import HumanInTheLoopMiddleware

agent = create_deep_agent(
    tools=[...],
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                "send_email": {
                    "allowed_decisions": ["approve", "edit", "reject"]
                }
            }
        )
    ],
    checkpointer=PostgresSaver(...)
)

# When tool call triggers interrupt:
# 1. Agent pauses, saves state
# 2. Email sent to approver with proposed action
# 3. System waits for approval
# 4. Agent resumes with approval decision
```

### Subagent Usage for Context Management

```python
# In Deep Agent system prompt:
"""
For all email operations, spawn an Email Communication Subagent:

Instead of calling send_email() directly, use:
  task("email_communication", "Send email to jane@company.com asking: ...")
  
The subagent will:
1. Compose the email professionally
2. Send it
3. Return confirmation
4. Your context stays clean

Example:
  task("email_communication", '''
    Send email to sales rep asking:
    1. What is the client's budget range?
    2. Are there any specific methodologies they prefer?
    3. When do they need the proposal by?
  ''')
"""

# Subagent definition
email_subagent = {
    "name": "email_communication",
    "description": "Handles all email sending and reading",
    "system_prompt": """
        You send and read emails professionally. 
        Format emails clearly with proper greetings and signatures.
        Track email IDs in project data.
    """,
    "tools": [send_email, read_email]
}
```

---

## Implementation Guide

### Phase 1: Foundation (Week 1)

**Infrastructure:**
```bash
# 1. Set up Supabase project
- Create account at supabase.com
- Create new project
- Enable pgvector extension
- Run schema SQL (from Data Layer section)

# 2. Set up environment
pip install langchain langchain-anthropic langchain-postgres langchain-openai \
            langchain-google-community asyncpg python-dotenv

# 3. Configure .env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://...
SUPABASE_SERVICE_KEY=...
SUPABASE_DB_URL=postgresql://...
GMAIL_CREDENTIALS=...
LANGSMITH_API_KEY=...
LANGSMITH_TRACING=true
```

**Core Tools Implementation:**
```python
# tools/email_tools.py
# tools/knowledge_tools.py
# tools/project_tools.py
# tools/validation_tools.py

# Implement all tools from Tool Specifications section
```

**Basic Agents:**
```python
# agents/email_triage.py
# agents/supervisor.py

# Start with just these two to test workflow
```

### Phase 2: Core Workflow (Week 2-3)

**Implement Main Agents:**
```python
# agents/research_brief_agent.py
# agents/proposal_agent.py
# agents/drafting_agent.py

# With Email Communication Subagents
```

**Testing:**
```python
# tests/test_workflow.py
# Use LLMToolEmulatorMiddleware for simulated humans
# Test full workflow: RFP → Brief → Proposal → Documents
```

### Phase 3: Automation (Week 4)

**Cron Agents:**
```python
# agents/project_tracking.py
# agents/knowledge_agent.py

# Schedule via LangSmith Deployment cron features
```

**Knowledge Base Population:**
```python
# scripts/seed_knowledge.py
# Populate with initial company info:
# - Capabilities
# - Team members
# - Suppliers
# - Pricing guidelines
# - Past project summaries
```

### Phase 4: Production (Week 5)

**Deployment:**
```python
# Deploy to LangSmith Deployment
# Configure Gmail webhooks
# Set up monitoring and alerts
# Train users on approval workflows
```

### Sample Project Structure

```
proposal_automation/
├── .env
├── requirements.txt
├── README.md
├── agents/
│   ├── __init__.py
│   ├── email_triage.py
│   ├── supervisor.py
│   ├── research_brief.py
│   ├── proposal.py
│   ├── drafting.py
│   ├── project_tracking.py
│   └── knowledge.py
├── tools/
│   ├── __init__.py
│   ├── email.py
│   ├── knowledge.py
│   ├── project.py
│   └── validation.py
├── database/
│   ├── schema.sql
│   ├── connection.py
│   └── seed_knowledge.py
├── tests/
│   ├── test_tools.py
│   ├── test_agents.py
│   └── test_workflow.py
├── config/
│   ├── prompts.py
│   └── settings.py
└── main.py
```

---

## Testing Strategy

### Unit Tests

```python
# Test individual tools
def test_search_knowledge():
    result = search_knowledge("panel suppliers")
    assert "supplier" in result.lower()
    
def test_validate_resource():
    result = validate_resource(
        "test@test.com",
        "Test question?",
        "test_project_id"
    )
    assert "sent" in result.lower()
```

### Agent Tests with Mocks

```python
from langchain.agents.middleware import LLMToolEmulatorMiddleware

# Mock human responses
def test_research_brief_agent():
    agent = create_research_brief_agent(
        middleware=[
            LLMToolEmulatorMiddleware(
                tools_to_emulate=["send_email"]
            )
        ]
    )
    
    result = agent.invoke({
        "project_id": "test_123",
        "rfp_content": "Need brand study..."
    })
    
    assert result["status"] == "brief_complete"
```

### Integration Tests

```python
# Test full workflow with real Supabase
async def test_full_proposal_workflow():
    # 1. Create project
    project_id = await create_project(
        client_name="Test Client",
        sales_rep_email="sales@company.com",
        rfp_content="Test RFP content"
    )
    
    # 2. Run through agents
    # ... (simulate email responses)
    
    # 3. Verify final state
    project = await query_project(project_id)
    assert project["status"] == "submitted"
    assert project["data"]["proposal_text"] is not None
```

### Trajectory Evaluation

```python
from langchain.agentevals import create_trajectory_match_evaluator

# Define expected tool call sequence
expected_trajectory = [
    {"type": "tool_call", "name": "search_knowledge"},
    {"type": "tool_call", "name": "send_email"},
    {"type": "tool_call", "name": "update_project"}
]

evaluator = create_trajectory_match_evaluator(
    expected_trajectory,
    mode="subset"  # Tools can be called in any order
)

# Run agent and evaluate
result = agent.invoke({...})
evaluation = evaluator.evaluate(result)
assert evaluation["passed"]
```

---

## Monitoring & Observability

### LangSmith Tracing

All agents automatically traced via LangSmith:
- View agent decisions in real-time
- Debug tool calls and failures
- Analyze token usage and costs
- Track end-to-end latency

### Custom Metrics

```python
# Log to audit table
await db.execute("""
    INSERT INTO audit_log (project_id, agent_name, action, details)
    VALUES ($1, $2, $3, $4)
""", project_id, "proposal_agent", "design_approved", {
    "estimated_cost": 50000,
    "timeline_weeks": 8
})
```

### Alerts

```python
# Set up alerts for:
# - Projects stuck >7 days
# - Validation timeouts
# - Agent errors
# - High token usage
# - Email delivery failures
```

---

## Appendix: Key Design Decisions

### Why Email Subagents?

Deep Agents can accumulate large contexts when handling multiple emails. By spawning Email Communication Subagents:
- Main agent context stays focused on logic
- Email details (headers, formatting, etc.) isolated
- Parallel email operations don't bloat context
- Failed email operations don't corrupt main agent state

### Why Supabase?

- Native pgvector support
- Built-in UI for data viewing/editing
- Easy auth if multi-tenancy needed later
- LangChain integration exists
- Can migrate to self-hosted Postgres if needed
- Lower operational overhead

### Why Single Knowledge Table?

- Agents are smart enough to filter metadata
- Eliminates need for complex joins
- Easy to extend with new knowledge types
- Simpler to maintain and backup
- Vector search + metadata filtering handles all use cases

### Why Atomic Tools?

- Agents compose tools intelligently based on context
- Easy to extend (new resource types work with existing tools)
- Simpler codebase (fewer tools to maintain)
- Flexible (tools work across multiple scenarios)
- Testable (mock simple interfaces)

---

## Getting Started Checklist

- [ ] Create Supabase project
- [ ] Run database schema SQL
- [ ] Set up environment variables
- [ ] Install Python dependencies
- [ ] Implement core tools (email, knowledge, project)
- [ ] Build Email Triage agent
- [ ] Build Supervisor agent
- [ ] Test basic email routing
- [ ] Build Research Brief agent with Email Subagent
- [ ] Populate knowledge base with initial data
- [ ] Test full brief workflow
- [ ] Build Proposal agent
- [ ] Build Drafting agent
- [ ] Test complete workflow
- [ ] Implement cron agents
- [ ] Deploy to LangSmith
- [ ] Configure monitoring
- [ ] Train users

---

**Document Version:** 1.0  
**Last Updated:** December 2025  
**Status:** Ready for Implementation

This specification provides everything needed to build the proposal automation system. All architectural decisions are documented, all tools are specified, and implementation guidance is provided.
