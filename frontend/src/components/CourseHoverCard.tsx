import { createPortal } from 'react-dom'
import { DAY_CODES, WORKLOAD_DIMENSIONS, type Course } from '../types/course'
import { formatSessionTimeRangeFull } from '../utils/schedule'
import { CircularScore } from './CircularScore'

const CARD_WIDTH = 300
const GAP = 10

const SHORT_LABELS: Record<string, string> = {
  exam: 'Exam',
  coding: 'Coding',
  team_project: 'Team',
  reading_essay: 'Essay',
  lab_experiment: 'Lab',
}

interface CourseHoverCardProps {
  course: Course
  anchorRect: DOMRect
}

export function CourseHoverCard({ course, anchorRect }: CourseHoverCardProps) {
  const overflowsRight = anchorRect.right + GAP + CARD_WIDTH > window.innerWidth
  const left = overflowsRight ? anchorRect.left - GAP - CARD_WIDTH : anchorRect.right + GAP
  const top = Math.max(8, Math.min(anchorRect.top, window.innerHeight - 220))

  const timeLabel = course.schedule_time[0] ? formatSessionTimeRangeFull(course.schedule_time[0]) : null
  const daysLabel = [...new Set(course.schedule_time.map((s) => s.day))]
    .sort((a, b) => DAY_CODES.indexOf(a) - DAY_CODES.indexOf(b))
    .join(' ')

  const detailParts = [`${course.credits} credit${course.credits === 1 ? '' : 's'}`, daysLabel, timeLabel].filter(
    Boolean
  )

  return createPortal(
    <div
      className="pointer-events-none fixed z-50 rounded-xl border border-slate-200 bg-white p-4 shadow-lg"
      style={{ top, left, width: CARD_WIDTH }}
    >
      <p className="text-sm font-semibold text-slate-900">{course.course_title}</p>
      <p className="mt-0.5 text-xs text-slate-500">{detailParts.join(' • ')}</p>
      <div className="mt-3 flex justify-between">
        {WORKLOAD_DIMENSIONS.map(({ key }) => (
          <CircularScore
            key={key}
            label={SHORT_LABELS[key]}
            score={course.workload_analysis.workload_scores[key].score}
          />
        ))}
      </div>
    </div>,
    document.body
  )
}
