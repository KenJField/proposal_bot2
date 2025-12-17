-- Proposal Automation System - Database Schema
-- Supabase PostgreSQL with pgvector

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

CREATE TRIGGER update_knowledge_updated_at BEFORE UPDATE ON knowledge
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
