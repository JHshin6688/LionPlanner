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
    syllabus_url VARCHAR(255),
    review_url VARCHAR(255),
    raw_syllabus TEXT,
    raw_reviews TEXT,
    syllabus_hash VARCHAR(64),                  -- SHA-256 hash
    review_hash VARCHAR(64),                    -- SHA-256 hash

    -- Processed LLM Outputs
    syllabus_summary TEXT,
    workload_analysis JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS degree_path (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    degree_name VARCHAR(255) UNIQUE NOT NULL,          -- e.g., 'Computer Science'
    required_courses JSONB NOT NULL DEFAULT '[]'::jsonb,  -- List of course_ids required for the degree
    elective_courses JSONB NOT NULL DEFAULT '[]'::jsonb,  -- List of course_ids that can be taken as electives
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ask LionPlanner chat history. One row per frontend chat session (session_id
-- is the same uuid the frontend already generates for each session in
-- localStorage). `turns` accumulates as the conversation goes:
-- [{"user": "...", "ai": "..."}, ...]
CREATE TABLE IF NOT EXISTS chats (
    session_id UUID PRIMARY KEY,
    title VARCHAR(255) NOT NULL DEFAULT 'New Chat',
    turns JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_courses_course_id ON courses(course_id);
CREATE INDEX IF NOT EXISTS idx_courses_course_level ON courses(course_level);
CREATE INDEX IF NOT EXISTS idx_degree_path_degree_name ON degree_path(degree_name);

create extension if not exists vector;
alter table courses add column if not exists syllabus_summary_embedding vector(1024);

-- Row Level Security: the frontend uses the public anon key, so it must be
-- read-only. Writes (insert/update/delete) go through the data pipeline,
-- which uses SUPABASE_SERVICE_ROLE_KEY and bypasses RLS entirely.
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE degree_path ENABLE ROW LEVEL SECURITY;

-- chats has no read/write policy at all: only the backend (SUPABASE_SERVICE_ROLE_KEY,
-- which bypasses RLS) ever touches it. The frontend never talks to Supabase directly
-- for chat — it goes through /api/chat, same as it always has.
ALTER TABLE chats ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'courses'
      AND policyname = 'Allow public read'
  ) THEN
    CREATE POLICY "Allow public read"
      ON public.courses
      FOR SELECT
      TO PUBLIC
      USING (true);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'degree_path'
      AND policyname = 'Allow public read'
  ) THEN
    CREATE POLICY "Allow public read"
      ON public.degree_path
      FOR SELECT
      TO PUBLIC
      USING (true);
  END IF;
END $$;

-- Vector search backing recommend_course's search_courses tool
-- (src/agents/recommend_course.py / src/db/supabase_client.py::search_courses_by_embedding).
-- Exposed as an RPC because supabase-py's query builder can't express pgvector's
-- <=> distance operator directly.
create or replace function match_courses (
  query_embedding vector(1024),
  match_count int default 5
)
returns table (
  course_id varchar,
  course_title varchar,
  department varchar,
  course_level int,
  syllabus_summary text,
  schedule_time jsonb,
  similarity float
)
language sql stable
as $$
  select
    course_id,
    course_title,
    department,
    course_level,
    syllabus_summary,
    schedule_time,
    1 - (syllabus_summary_embedding <=> query_embedding) as similarity
  from courses
  where syllabus_summary_embedding is not null
  order by syllabus_summary_embedding <=> query_embedding
  limit match_count;
$$;