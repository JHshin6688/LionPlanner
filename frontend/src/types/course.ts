// Mirrors src/schemas/workload.py (WorkloadAnalysis) and the `courses` table schema in README.md.

export interface DimensionScore {
  score: number // 0-100
  evidence_quotes: string[]
}

export interface WorkloadScores {
  exam: DimensionScore
  coding: DimensionScore
  team_project: DimensionScore
  reading_essay: DimensionScore
  lab_experiment: DimensionScore
}

export interface WorkloadAnalysis {
  workload_scores: WorkloadScores
  burnout_risk_tags: string[]
  weekly_hours_estimated: number
  review_summary_3lines: string
}

// One meeting block, e.g. { day: "Mon", start: "10:10", end: "11:25" }.
export interface ScheduleSession {
  day: DayCode
  start: string // "HH:MM", 24h
  end: string // "HH:MM", 24h
}

export const DAY_CODES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as const
export type DayCode = (typeof DAY_CODES)[number]

export interface Course {
  id: string
  course_id: string
  course_title: string
  instructor_name: string
  credits: number
  course_level: number
  schedule_time: ScheduleSession[]
  raw_syllabus: string | null
  raw_reviews: string | null
  syllabus_hash: string | null
  review_hash: string | null
  review_summary: string | null
  workload_analysis: WorkloadAnalysis
  created_at: string
  updated_at: string
}

export const WORKLOAD_DIMENSIONS = [
  { key: 'exam', label: 'Exam' },
  { key: 'coding', label: 'Coding' },
  { key: 'team_project', label: 'Team Project' },
  { key: 'reading_essay', label: 'Reading / Essay' },
  { key: 'lab_experiment', label: 'Lab / Experiment' },
] as const satisfies readonly { key: keyof WorkloadScores; label: string }[]
