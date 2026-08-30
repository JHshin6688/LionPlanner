-- v2 course schema: three tables instead of one monolithic `courses` table.
--
-- - review: one row per instructor - their scraped review page.
-- - courses_total: durable, semester-independent cache of every (course,
--   instructor) pairing ever analyzed. The ONLY table the analysis pipeline
--   writes workload_analysis/syllabus_summary/embeddings to.
-- - courses_semester: thin - just the (course_id, instructor_name) pairing
--   offered *this* semester, plus schedule_time.
--
-- Everything else the app needs is read through courses_semester_view (a
-- join of courses_semester + courses_total + review), so there is exactly
-- one stored copy of every value - no refresh/sync step required.
--
-- Does not touch `chats` or `degree_path` - those stay as-is.
-- Safe to run multiple times (CREATE TABLE IF NOT EXISTS + guarded policies).

create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- review: professor roster + their scraped review page. Created first since
-- courses_total references it.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS review (
    instructor_name VARCHAR(255) PRIMARY KEY,
    review_url VARCHAR(255),
    raw_reviews TEXT,
    review_hash VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- courses_total: one row per (course, instructor) pairing that has ever been
-- analyzed. Durable across semesters - a recurring course+instructor combo
-- whose syllabus_hash/review_hash haven't changed can skip re-scraping and
-- re-analysis entirely by reusing this row.
--
-- Note: course_title/department/credits/course_level depend only on
-- course_id, not instructor_name, so they're duplicated across every
-- instructor row for the same course - a deliberate trade-off of this key
-- (a title change has to be applied to each of that course's rows).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS courses_total (
    course_id VARCHAR(50) NOT NULL,
    instructor_name VARCHAR(255) NOT NULL REFERENCES review(instructor_name),
    course_title VARCHAR(255) NOT NULL,
    department VARCHAR(100) NOT NULL,
    credits INT NOT NULL DEFAULT 3,
    course_level INT NOT NULL DEFAULT 4000,
    syllabus_url VARCHAR(255),
    raw_syllabus TEXT,
    syllabus_hash VARCHAR(64),
    syllabus_summary TEXT,
    syllabus_summary_embedding vector(1024),
    workload_analysis JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (course_id, instructor_name)
);

CREATE INDEX IF NOT EXISTS idx_courses_total_course_level ON courses_total(course_level);
-- course_id alone is an efficient lookup (leftmost prefix of the PK index
-- above); instructor_name alone is not, so index it separately for
-- "what has this instructor taught" lookups.
CREATE INDEX IF NOT EXISTS idx_courses_total_instructor_name ON courses_total(instructor_name);

-- ---------------------------------------------------------------------------
-- courses_semester: this semester's offerings only - just the roster and
-- schedule. Everything else is read through courses_semester_view below.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS courses_semester (
    course_id VARCHAR(50) NOT NULL,
    instructor_name VARCHAR(255) NOT NULL,
    schedule_time JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (course_id, instructor_name),
    FOREIGN KEY (course_id, instructor_name) REFERENCES courses_total(course_id, instructor_name)
);

-- ---------------------------------------------------------------------------
-- Row Level Security: same policy as before - frontend uses the public anon
-- key (read-only), writes go through the pipeline with the service role key
-- (bypasses RLS entirely).
-- ---------------------------------------------------------------------------
ALTER TABLE review ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses_total ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses_semester ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'review' AND policyname = 'Allow public read'
  ) THEN
    CREATE POLICY "Allow public read" ON public.review FOR SELECT TO PUBLIC USING (true);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'courses_total' AND policyname = 'Allow public read'
  ) THEN
    CREATE POLICY "Allow public read" ON public.courses_total FOR SELECT TO PUBLIC USING (true);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'courses_semester' AND policyname = 'Allow public read'
  ) THEN
    CREATE POLICY "Allow public read" ON public.courses_semester FOR SELECT TO PUBLIC USING (true);
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- courses_semester_view: what the app actually reads - this semester's
-- offerings joined against courses_total (course/analysis facts) and review
-- (review data). No duplicated storage; always reflects whatever is
-- currently in courses_total/review (which only changes when a syllabus_hash/
-- review_hash actually changes, per the pipeline's diff engine).
-- ---------------------------------------------------------------------------
-- syllabus_summary/syllabus_summary_embedding/raw_reviews/created_at/updated_at
-- are deliberately left out - unused by the hovercard or Ask LionPlanner
-- (confirmed against frontend/backend usage), and vector search reads
-- syllabus_summary_embedding straight from courses_total via match_courses,
-- not through this view.
CREATE OR REPLACE VIEW courses_semester_view AS
SELECT
    cs.course_id,
    cs.instructor_name,
    cs.schedule_time,
    ct.course_title,
    ct.department,
    ct.credits,
    ct.course_level,
    ct.syllabus_url,
    ct.workload_analysis,
    r.review_url
FROM courses_semester cs
JOIN courses_total ct ON ct.course_id = cs.course_id AND ct.instructor_name = cs.instructor_name
JOIN review r ON r.instructor_name = cs.instructor_name;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    GRANT SELECT ON courses_semester_view TO anon;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    GRANT SELECT ON courses_semester_view TO authenticated;
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- match_courses RPC: vector search is scoped to courses_semester (a student
-- can't take a course that isn't offered this semester), joined to
-- courses_total for the embedding and descriptive fields. Same external
-- signature as before, so src/db/supabase_client.py::search_courses_by_embedding
-- is unaffected.
-- ---------------------------------------------------------------------------
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
    cs.course_id,
    ct.course_title,
    ct.department,
    ct.course_level,
    ct.syllabus_summary,
    cs.schedule_time,
    1 - (ct.syllabus_summary_embedding <=> query_embedding) as similarity
  from courses_semester cs
  join courses_total ct on ct.course_id = cs.course_id and ct.instructor_name = cs.instructor_name
  where ct.syllabus_summary_embedding is not null
  order by ct.syllabus_summary_embedding <=> query_embedding
  limit match_count;
$$;
