-- One-time migration: moves data from the old monolithic `courses` table
-- into review / courses_total / courses_semester (v2). The old `courses`
-- table is left in place under its original name (not renamed) - drop it
-- yourself once you've verified the new tables, if/when you're ready.
--
-- Run AFTER sql/schema_v2.sql. Safe to re-run - every INSERT uses
-- ON CONFLICT DO NOTHING, so re-running just no-ops on rows already migrated.
--
-- Does not touch `chats` or `degree_path`.

BEGIN;

-- 1) review: one row per distinct instructor_name. If the same instructor
--    appears on multiple old rows (taught >1 course), their review data
--    should already be identical (scraped by instructor, not by course) -
--    take the most recently updated row as the source, arbitrarily but
--    deterministically.
INSERT INTO review (instructor_name, review_url, raw_reviews, review_hash, updated_at)
SELECT DISTINCT ON (instructor_name)
    instructor_name,
    review_url,
    raw_reviews,
    review_hash,
    updated_at
FROM courses
WHERE instructor_name IS NOT NULL
ORDER BY instructor_name, updated_at DESC
ON CONFLICT (instructor_name) DO NOTHING;

-- 2) courses_total: one row per (course_id, instructor_name) - exactly one
--    per old row, since the old table only ever stored one instructor per
--    course_id.
INSERT INTO courses_total (
    course_id, instructor_name, course_title, department, credits, course_level,
    syllabus_url, raw_syllabus, syllabus_hash, syllabus_summary,
    syllabus_summary_embedding, workload_analysis, updated_at
)
SELECT
    course_id, instructor_name, course_title, department, credits, course_level,
    syllabus_url, raw_syllabus, syllabus_hash, syllabus_summary,
    syllabus_summary_embedding, workload_analysis, updated_at
FROM courses
ON CONFLICT (course_id, instructor_name) DO NOTHING;

-- 3) courses_semester: every old row is, by definition, an offering from
--    "this semester" - that's all the old table ever held.
INSERT INTO courses_semester (course_id, instructor_name, schedule_time, updated_at)
SELECT course_id, instructor_name, schedule_time, updated_at
FROM courses
ON CONFLICT (course_id, instructor_name) DO NOTHING;

COMMIT;

-- ---------------------------------------------------------------------------
-- Verification queries - run these and compare counts before dropping the
-- old `courses` table. (2) and (3) should each match courses's row count;
-- (1) should match the number of distinct instructor_name values.
-- ---------------------------------------------------------------------------
-- SELECT count(*) FROM courses;
-- SELECT count(*) FROM courses_total;
-- SELECT count(*) FROM courses_semester;
-- SELECT count(DISTINCT instructor_name) FROM courses;
-- SELECT count(*) FROM review;
-- SELECT * FROM courses_semester_view LIMIT 5;

-- Once you've verified the row counts and spot-checked a few courses via
-- courses_semester_view, drop the old table (only once you're sure nothing
-- still reads from it directly):
-- DROP TABLE courses;
