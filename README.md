# LionPlanner

A course-planning app that helps Columbia students build a schedule around actual workload and time, not just catalog listings.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Node](https://img.shields.io/badge/node-20%2B-339933)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-1C3C3C)
![Supabase](https://img.shields.io/badge/Supabase-Postgres%20%2B%20pgvector-3ECF8E?logo=supabase&logoColor=white)

## Overview & Motivation

Most course-registration tools focus on the basics — filtering by department, showing meeting times, listing prerequisites. But when students actually plan a semester, what they need is more layered: how demanding is this course in terms of workload, what does the whole schedule add up to once every course is stacked together, and does a course that fits time-wise also fit the degree path they're following. Mostly, answering "how much work is this course" meant leaving the registration site entirely — reading the syllabus, digging through review sites, and cross-checking degree requirements by hand.

**LionPlanner pulls all of that into one place: a scheduling tool where syllabus content, instructor reviews, workload analysis, schedule conflicts, and degree-path fit are all one chat message away**

## Key Features

- Built on real Columbia data — course syllabi and reviews sourced from CULPA, the review site Columbia students actually use.
- A DB construction pipeline that turns raw syllabus and review text into a structured, multi-dimension workload analysis using LLMs.
- Filtering by course title, department, course level, and day/time.
- **Ask LionPlanner**, a chat assistant that recommends courses and analyzes schedule workload, grounded in the course database, the degree-path database, and whatever is currently on the student's calendar.

## Demo

Live app: **https://lionplanner-front.vercel.app/**

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, LangGraph, LangChain, LangSmith |
| LLMs | Claude (Sonnet & Haiku, via `langchain-anthropic`) |
| Embeddings | Voyage AI (`voyage-3.5`) |
| Scraping | Firecrawl, with a Jina Reader fallback |
| Database | Supabase (Postgres + `pgvector`) |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS |
| Infra / CI | Docker, Fly.io (backend), Vercel (frontend), GitHub Actions |

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- A [Supabase](https://supabase.com) project (Postgres + `pgvector`)
- API keys: **Anthropic**, **Voyage AI**, **Firecrawl** (or **Jina**) for scraping, and (optional) **LangSmith** for visualizing agentic workflow

### Installation

**1. Clone and set up the database**

```bash
git clone https://github.com/<your-org>/lionplanner.git
cd lionplanner
```

Run the SQL migrations in your Supabase project's SQL editor, in order:

- [`sql/schema.sql`](sql/schema.sql) — creates `degree_path` and `chats` (plus a legacy monolithic `courses` table, unused from here on).
- [`sql/schema_v2.sql`](sql/schema_v2.sql) — creates the current course schema: `review` (one row per instructor), `courses_total` (a durable, semester-independent cache of every course/instructor pairing ever analyzed), `courses_semester` (just this semester's offerings + `schedule_time`), the `courses_semester_view` the frontend and Ask LionPlanner actually read from, and the `match_courses` RPC for semantic search.

Migrating an existing deployment that still has data in the old `courses` table? Run [`sql/migrate_to_v2.sql`](sql/migrate_to_v2.sql) after `schema_v2.sql` to copy it into the new tables, then drop `courses` once you've verified the counts match.

**2. Backend**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in SUPABASE_*, ANTHROPIC_API_KEY, VOYAGE_API_KEY, etc.
```

**3. Frontend**

```bash
cd frontend
npm install
cp .env.example .env.local   # VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_BASE_URL
```

### Usage

Build the course database (scrapes syllabi/reviews, runs workload analysis, upserts to Supabase — see [Architecture](#architecture--pipeline) below). This needs `src/data/courses_total.csv`, `src/data/courses_semester.csv`, `src/data/professors.csv`, `src/data/professors_semester.csv`, and `src/data/degree_path.json` to be populated first — every instructor referenced in a courses CSV must also appear in the matching professors CSV, or the pipeline fails fast before scraping anything.

```bash
# One-time: bulk-analyze every (course, instructor) pairing in courses_total.csv
# against an empty courses_total/review — only ever needed once, or after a
# full catalog refresh.
python -m src.main --backfill

# Every semester: sync courses_semester.csv against the current roster. Only
# scrapes + re-analyzes a (course, instructor) pairing if it's new or its
# syllabus/review content changed; everything else reuses the courses_total
# cache. Always upserts courses_semester either way, since that's the only
# record of "offered this semester."
python -m src.main

# Same as the semester sync, but bypasses the diff check and re-analyzes
# every course in courses_semester.csv unconditionally.
python -m src.main --force-refresh
```

Run the Ask LionPlanner API:

```bash
uvicorn src.api.main:app --reload
```

Run the frontend:

```bash
cd frontend
npm run dev
```

## Architecture & Pipeline

### Data pipeline

The course database is split into three tables instead of one monolithic `courses` table, so that re-running the pipeline every semester doesn't mean re-scraping and re-analyzing the entire catalog from scratch:

- **`review`** — one row per instructor: their scraped review page.
- **`courses_total`** — a durable, semester-independent cache of every `(course_id, instructor_name)` pairing ever analyzed. The only table the analysis pipeline writes `workload_analysis` / `syllabus_summary` / embeddings to — a recurring course+instructor combo whose content hasn't changed skips re-analysis entirely and just reuses this row.
- **`courses_semester`** — thin: just this semester's `(course_id, instructor_name)` roster plus `schedule_time`. Everything else the app needs is read through `courses_semester_view`, a join of all three tables, so there's exactly one stored copy of every value.

```mermaid
flowchart LR
    A["courses_total.csv\n(full catalog)"] -->|"--backfill (one-time)"| S
    B["courses_semester.csv\n(this semester's roster)"] -->|"default run (every semester)"| S["Scrape syllabus + reviews\n(Firecrawl → Jina fallback)"]
    S --> D{"New pairing, or\nhash changed?"}
    D -->|no| CACHE["Reuse cached analysis"]
    D -->|yes| F["Filter + digest (Haiku)"]
    F --> AN["Per-category analysis\n(Sonnet + one-shot example)"]
    AN --> CT[("courses_total\n+ review")]
    CACHE --> CT
    CT --> CS[("courses_semester\n(schedule_time)")]
```

- **Scraping**: [`src/web_functions/scrape.py`](src/web_functions/scrape.py) tries Firecrawl first (handles JS-rendered pages), falling back to the Jina Reader API.
- **Noise filtering**: [`src/pipeline/content_filters.py`](src/pipeline/content_filters.py) strips boilerplate (honesty policy, office hours, images) from syllabi before any LLM sees them, and keeps only the "AI-Generated Summary" / "Most Agreed Review" sections from CULPA pages.
- **Digest**: [`src/pipeline/digest.py`](src/pipeline/digest.py) uses a lightweight model (Haiku) to compress the filtered text down to whatever carries workload signal, preserving direct quotes verbatim so later steps can cite them.
- **Category analysis**: [`src/pipeline/analyzer_pipeline.py`](src/pipeline/analyzer_pipeline.py) scores five workload dimensions — **Exam, Coding, Team Project, Reading/Essay, Lab/Experiment** — in parallel with Sonnet. Each category prompt includes a **fabricated one-shot example** (a realistic but invented course, syllabus excerpt, review excerpt, and scored output) to calibrate the model against a fixed anchor point, so scores stay comparable across very different courses.
- A SHA-256 diff check ([`src/pipeline/diff_engine.py`](src/pipeline/diff_engine.py)) is what decides "new pairing, or hash changed?" above — it skips re-scraping/re-analysis for a `(course, instructor)` pairing already in `courses_total` whose syllabus/review content hasn't changed, unless `--force-refresh` is passed.
- The syllabus is also summarized and embedded (Voyage AI) for semantic search. `courses_semester` is always upserted at the end regardless of whether analysis ran or was skipped — it's the only record of "this course is offered this semester."
- **Two entry points** (`src/main.py`): `python -m src.main --backfill` runs the one-time, unconditional bulk analysis of the full catalog (`courses_total.csv`) into an initially-empty database; the default `python -m src.main` is the recurring per-semester sync against `courses_semester.csv`, diff-checked as above. Before either runs, `validate_instructor_coverage` fails fast if a courses CSV references an instructor missing from its matching professors CSV.

### Backend: Ask LionPlanner

The chat feature is a LangGraph state machine ([`src/agents/graph.py`](src/agents/graph.py)) with a routing node, three specialist nodes, and a shared grounding-verification step:

```mermaid
flowchart TD
    Q["Student query"] --> R{"Router\n(Haiku)"}

    R -->|general question| GQ["general_question\n(Sonnet, direct answer)"]
    GQ --> END1(("done"))

    R -->|workload analysis of\ncourses on the schedule| WA["analyze_workload\n(Sonnet, reasons over\nscheduled courses' workload data)"]
    WA --> V

    R -->|recommend a course /\ndegree-path / conflict check| RC["recommend_course agent (Sonnet)\ntools: search_courses (embedding search),\ncheck_degree_path, check_schedule_conflict"]
    RC --> V

    V{"verify_grounding\ncited course_ids ⊆ retrieved course_ids?"}
    V -->|ungrounded, 1 retry left| WA
    V -->|ungrounded, 1 retry left| RC
    V -->|grounded, or retries exhausted| END2(("done, streamed to client"))
```

- **Router** (`src/agents/router.py`): a single Haiku call classifies the query into `recommend_course`, `analyze_workload`, or `general_question` — nothing else happens here.
- **`analyze_workload`**: **a fixed workflow** (no retrieval needed) that reasons directly over the `workload_analysis` JSON of whatever courses are on the student's calendar.
- **`recommend_course`**: **the one true agent node** (`langchain.agents.create_agent`), free to call its tools as many times as needed:
  - `search_courses` — semantic search over syllabus embeddings.
  - `check_degree_path` — looks up required/elective courses for a track from the curated `degree_path` table, more authoritative than a topic guess when a student names a concentration.
  - `check_schedule_conflict` — deterministic day/time overlap check in code, since LLMs are unreliable at interval arithmetic.
- **`verify_grounding`**: not another LLM call — a plain set-membership check that every course the answer cites was actually retrieved or provided this turn. On a failure it routes back to the originating node once with corrective feedback; if it fails again, it gives up with a fixed fallback message instead of looping.
- Answers stream token-by-token over Server-Sent Events (`src/api/main.py`) directly to the frontend chat panel.  

![Ask LionPlanner LangSmith trace](docs/langsmith-trace.png)
*A real `recommend_course` run: the router picks `recommend_course`, the agent calls `check_degree_path` → `search_courses` → `check_schedule_conflict` in sequence, and `verify_grounding` passes it through with no retry needed. [View the full interactive trace on LangSmith →](https://smith.langchain.com/public/776094f5-44b4-4cab-a239-3b157c2a89f1/r/01a02263-5b00-7243-ac30-b8f7f28a3fe6?start_time=2026-08-21T03%3A35%3A31.840646Z)*

### Frontend

React 19 + Vite + Tailwind, talking to Supabase directly (read-only, anon key) for course data and to the FastAPI backend for chat:

- `CourseListPanel` / `FilterPanel` / `DualRangeSlider` — course search and filtering (title, department, level, day/time).
- `CalendarGrid` / `CourseBlock` / `CourseHoverCard` / `TotalCreditsCard` — the drag-and-drop weekly schedule view, with live conflict detection.
- `AskLionPlanner` / `MarkdownMessage` — the chat panel, consuming the backend's SSE stream and rendering Markdown as it arrives.
- `hooks/useCourses.ts`, `hooks/useChat.ts` — data fetching and chat-streaming state; `utils/appStorage.ts`, `utils/chatStorage.ts` persist filters, schedule, and chat sessions to `localStorage`.

### Project structure

```
src/
  agents/        # LangGraph nodes: router, recommend_course, analyze_workload,
                  # general_question, verify_grounding, graph wiring
  api/           # FastAPI app (SSE chat endpoint)
  pipeline/      # scrape → filter → digest → analyze course-DB pipeline
  db/            # Supabase client (reads + writes)
  web_functions/ # Firecrawl / Jina scraping
  schemas/       # Pydantic models (Course, WorkloadAnalysis)
  data/          # curated course/professor/degree-path source data
  main.py        # pipeline entrypoint (python -m src.main)

frontend/
  src/
    components/  # calendar, filters, course list, Ask LionPlanner chat
    hooks/       # useCourses, useChat
    lib/         # Supabase client
    utils/       # filters, schedule conflict logic, localStorage persistence

sql/
  schema.sql          # degree_path, chats, and the legacy monolithic courses table
  schema_v2.sql        # current course schema: review / courses_total / courses_semester,
                        # courses_semester_view, match_courses RPC
  migrate_to_v2.sql    # one-time data migration from the legacy courses table into v2
```

## Future Work

1. **Broader course coverage** — currently centered on courses in the MS CS program; extending to more departments would make the tool useful to a wider set of students.
2. **Automated syllabus/review discovery** — syllabus formats vary wildly by professor and aren't always published at all. The current course DB is built from a manually curated list of syllabus/review URLs; a follow-up agent that discovers and crawls these automatically would remove that bottleneck.
3. **Verification on the DB-construction side** — Ask LionPlanner already self-corrects via `verify_grounding`, but the pipeline that generates the workload analysis in the first place has no equivalent second-pass verification of its own AI-generated output.

## Contributing & License

Contributions are welcome — feel free to open an issue or a pull request.

Licensed under the [MIT License](LICENSE).
