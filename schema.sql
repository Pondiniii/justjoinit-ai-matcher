-- ============================================================================
-- JustJoinIT AI Job Finder - 3-Phase Pipeline
-- ============================================================================
-- Phase 1: Discovery  → job_links      (just URLs)
-- Phase 2: Fetching   → job_details    (curl each offer)
-- Phase 3: Analysis   → job_analysis   (LLM scoring)
-- ============================================================================

-- ============================================================================
-- PHASE 1: Link Discovery
-- ============================================================================
CREATE TABLE IF NOT EXISTS job_links (
    id SERIAL PRIMARY KEY,
    link TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'discovered' CHECK (status IN ('discovered', 'fetched', 'analyzed')),
    discovered_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_links_status ON job_links(status);

-- ============================================================================
-- PHASE 2: Job Details (from offer page)
-- ============================================================================
CREATE TABLE IF NOT EXISTS job_details (
    id SERIAL PRIMARY KEY,
    link_id INTEGER UNIQUE REFERENCES job_links(id) ON DELETE CASCADE,

    -- Basic info
    title TEXT,
    company TEXT,
    location TEXT,

    -- Work conditions
    remote_type TEXT,
    contract_type TEXT,
    exp_level TEXT,
    employment_type TEXT,

    -- Salary
    salary_min DECIMAL,
    salary_max DECIMAL,
    salary_currency TEXT,
    salary_rate TEXT,  -- hourly, monthly, yearly
    salary_type TEXT,  -- gross, net

    -- Rich content (tech_stack 3rd from end, description 2nd from end)
    tech_stack JSONB,
    description TEXT,
    fetched_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- PHASE 3: LLM Analysis
-- ============================================================================
CREATE TABLE IF NOT EXISTS job_analysis (
    id SERIAL PRIMARY KEY,
    link_id INTEGER UNIQUE REFERENCES job_links(id) ON DELETE CASCADE,

    -- Summary
    language TEXT,
    short_summary TEXT,

    -- Risk scores (0-100, higher = worse)
    cringe_score INTEGER CHECK (cringe_score BETWEEN 0 AND 100),
    januszex_score INTEGER CHECK (januszex_score BETWEEN 0 AND 100),

    -- Quality scores (0-100, higher = better)
    work_culture_score INTEGER CHECK (work_culture_score BETWEEN 0 AND 100),
    stability_score INTEGER CHECK (stability_score BETWEEN 0 AND 100),
    benefit_score INTEGER CHECK (benefit_score BETWEEN 0 AND 100),
    lgbt_score INTEGER CHECK (lgbt_score BETWEEN 0 AND 100),
    corpo_score INTEGER CHECK (corpo_score BETWEEN 0 AND 100),

    -- Fit analysis
    fit_score INTEGER CHECK (fit_score BETWEEN 0 AND 100),
    fit_reasoning TEXT,

    -- Final decision
    decision TEXT CHECK (decision IN ('APPLY', 'WATCH', 'IGNORE')),

    analyzed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_decision ON job_analysis(decision);
CREATE INDEX IF NOT EXISTS idx_analysis_fit_score ON job_analysis(fit_score DESC NULLS LAST);

-- ============================================================================
-- VIEW: Combined offer data
-- ============================================================================
CREATE OR REPLACE VIEW v_offers AS
SELECT
    l.id,
    l.link,
    l.status,
    d.title,
    d.company,
    d.location,
    d.remote_type,
    d.contract_type,
    d.exp_level,
    d.employment_type,
    d.salary_min,
    d.salary_max,
    d.salary_currency,
    d.salary_rate,
    d.salary_type,
    d.tech_stack,
    d.description,
    a.language,
    a.short_summary,
    a.fit_score,
    a.decision,
    a.fit_reasoning,
    a.cringe_score,
    a.januszex_score,
    a.work_culture_score,
    a.stability_score,
    l.discovered_at,
    d.fetched_at,
    a.analyzed_at
FROM job_links l
LEFT JOIN job_details d ON l.id = d.link_id
LEFT JOIN job_analysis a ON l.id = a.link_id;

-- ============================================================================
-- VIEW: Top matches
-- ============================================================================
CREATE OR REPLACE VIEW v_top_matches AS
SELECT
    link,
    title,
    company,
    location,
    remote_type,
    salary_min,
    salary_max,
    salary_currency,
    fit_score,
    decision,
    short_summary,
    fit_reasoning
FROM v_offers
WHERE decision = 'APPLY'
ORDER BY fit_score DESC NULLS LAST;

-- ============================================================================
-- VIEW: Statistics
-- ============================================================================
CREATE OR REPLACE VIEW v_stats AS
SELECT
    COUNT(*) as total_links,
    COUNT(*) FILTER (WHERE status = 'discovered') as discovered,
    COUNT(*) FILTER (WHERE status = 'fetched') as fetched,
    COUNT(*) FILTER (WHERE status = 'analyzed') as analyzed,
    (SELECT COUNT(*) FROM job_analysis WHERE decision = 'APPLY') as apply,
    (SELECT COUNT(*) FROM job_analysis WHERE decision = 'WATCH') as watch,
    (SELECT COUNT(*) FROM job_analysis WHERE decision = 'IGNORE') as ignore
FROM job_links;

-- ============================================================================
-- COMMENTS
-- ============================================================================
COMMENT ON TABLE job_links IS 'Phase 1: Discovered job offer URLs';
COMMENT ON TABLE job_details IS 'Phase 2: Fetched job details from offer pages';
COMMENT ON TABLE job_analysis IS 'Phase 3: LLM analysis and scoring';

COMMENT ON VIEW v_offers IS 'Combined view joining all 3 phases';
COMMENT ON VIEW v_top_matches IS 'APPLY offers sorted by fit score';
COMMENT ON VIEW v_stats IS 'Pipeline statistics';
