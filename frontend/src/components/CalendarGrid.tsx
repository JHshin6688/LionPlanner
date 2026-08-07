import { useState } from 'react'
import { DAY_CODES, type Course } from '../types/course'
import {
  CALENDAR_END_HOUR,
  CALENDAR_HEIGHT_PX,
  CALENDAR_START_HOUR,
  formatSessionTimeRange,
  HOUR_HEIGHT_PX,
  sessionToGridStyle,
} from '../utils/schedule'
import { COURSE_DRAG_MIME } from './CourseBlock'

const HOURS = Array.from(
  { length: CALENDAR_END_HOUR - CALENDAR_START_HOUR },
  (_, i) => CALENDAR_START_HOUR + i
)

function formatHourLabel(hour: number): string {
  const period = hour < 12 ? 'AM' : 'PM'
  const h12 = hour % 12 === 0 ? 12 : hour % 12
  return `${h12} ${period}`
}

interface CalendarGridProps {
  scheduledCourses: Course[]
  hoveredCourse: Course | null
  hoveredCourseConflicts: boolean
  onDropCourse: (courseId: string) => void
  onRemoveCourse: (courseId: string) => void
}

export function CalendarGrid({
  scheduledCourses,
  hoveredCourse,
  hoveredCourseConflicts,
  onDropCourse,
  onRemoveCourse,
}: CalendarGridProps) {
  const [hoveredPlacedCourseId, setHoveredPlacedCourseId] = useState<string | null>(null)

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col overflow-hidden">
      {/* Horizontal scroll wraps header + grid together so day columns never get crushed on narrow windows. */}
      <div className="flex min-h-0 flex-1 flex-col overflow-x-auto">
        <div className="flex min-w-[640px] shrink-0 border-b border-slate-200">
          <div className="w-14 shrink-0" />
          {DAY_CODES.map((day) => (
            <div
              key={day}
              className="flex-1 border-l border-slate-100 py-2 text-center text-sm font-semibold text-slate-700"
            >
              {day}
            </div>
          ))}
        </div>

        <div className="flex min-w-[640px] flex-1 overflow-y-auto">
          <div className="w-14 shrink-0" style={{ height: CALENDAR_HEIGHT_PX }}>
            {HOURS.map((hour) => (
              <div key={hour} style={{ height: HOUR_HEIGHT_PX }} className="relative">
                <span className="absolute -top-2 right-2 text-[11px] text-slate-400">
                  {formatHourLabel(hour)}
                </span>
              </div>
            ))}
          </div>

          {DAY_CODES.map((day) => {
            const placedForDay = scheduledCourses.flatMap((course) =>
              course.schedule_time.filter((s) => s.day === day).map((session) => ({ course, session }))
            )
            const previewForDay = hoveredCourse?.schedule_time.filter((s) => s.day === day) ?? []

            return (
              <div
                key={day}
                className="relative flex-1 border-l border-slate-100"
                style={{ height: CALENDAR_HEIGHT_PX }}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault()
                  const courseId = e.dataTransfer.getData(COURSE_DRAG_MIME)
                  if (courseId) onDropCourse(courseId)
                }}
              >
                {HOURS.map((hour, i) => (
                  <div
                    key={hour}
                    className="absolute w-full border-t border-slate-100"
                    style={{ top: i * HOUR_HEIGHT_PX }}
                  />
                ))}

                {previewForDay.map((session, i) => (
                  <div
                    key={`preview-${i}`}
                    style={sessionToGridStyle(session)}
                    className={`absolute inset-x-1 z-10 rounded-md border-2 border-dashed ${
                      hoveredCourseConflicts
                        ? 'border-red-400 bg-red-200/50'
                        : 'border-slate-400 bg-slate-300/60'
                    }`}
                  />
                ))}

                {placedForDay.map(({ course, session }, i) => (
                  <button
                    key={`${course.id}-${i}`}
                    type="button"
                    onClick={() => onRemoveCourse(course.id)}
                    onMouseEnter={() => setHoveredPlacedCourseId(course.id)}
                    onMouseLeave={() => setHoveredPlacedCourseId(null)}
                    title={`${course.course_id} · ${course.course_title} — click to remove`}
                    style={sessionToGridStyle(session)}
                    className={`absolute inset-x-1 z-0 overflow-hidden rounded-md border p-1 text-left text-indigo-900 shadow-sm transition ${
                      hoveredPlacedCourseId === course.id
                        ? 'border-red-300 bg-red-50'
                        : 'border-indigo-300 bg-indigo-100'
                    }`}
                  >
                    <p className="truncate text-[11px] font-semibold">{course.course_id}</p>
                    <p className="line-clamp-1 text-[10px] leading-tight">{course.course_title}</p>
                    <p className="truncate text-[10px] leading-tight text-indigo-700">
                      {formatSessionTimeRange(session)}
                    </p>
                  </button>
                ))}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
