CREATE TABLE IF NOT EXISTS courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id VARCHAR(50) UNIQUE NOT NULL,      -- e.g., 'COMS-W3157'
    course_title VARCHAR(255) NOT NULL,         -- e.g., 'Advanced Programming'
    instructor_name VARCHAR(255) NOT NULL,      -- e.g., 'Jae Woo Lee'
    department VARCHAR(100) NOT NULL,           -- e.g., 'COMS'
    credits INT NOT NULL DEFAULT 3,
    course_level INT NOT NULL DEFAULT 4000,     -- e.g., 1000, 3000, 4000
    schedule_time JSONB DEFAULT '{}'::jsonb,    -- Days and hours

    -- Raw Data & Diffing Hashes
    raw_syllabus TEXT,
    raw_reviews TEXT,
    syllabus_hash VARCHAR(64),                  -- SHA-256 hash
    review_hash VARCHAR(64),                    -- SHA-256 hash

    -- Processed LLM Outputs
    review_summary TEXT,
    workload_analysis JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_courses_course_id ON courses(course_id);
CREATE INDEX IF NOT EXISTS idx_courses_course_level ON courses(course_level);

-- Row Level Security: the frontend uses the public anon key, so it must be
-- read-only. Writes (insert/update/delete) go through the data pipeline,
-- which uses SUPABASE_SERVICE_ROLE_KEY and bypasses RLS entirely.
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read" ON courses
    FOR SELECT
    USING (true);
-- No insert/update/delete policy is defined, so those commands are denied
-- by default for the anon and authenticated roles.