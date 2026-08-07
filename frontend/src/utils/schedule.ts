import type { Course, ScheduleSession } from '../types/course'

export const CALENDAR_START_HOUR = 7 // 7am
export const CALENDAR_END_HOUR = 21 // 9pm
export const HOUR_HEIGHT_PX = 64
export const CALENDAR_HEIGHT_PX = (CALENDAR_END_HOUR - CALENDAR_START_HOUR) * HOUR_HEIGHT_PX
const CALENDAR_SPAN_MINUTES = (CALENDAR_END_HOUR - CALENDAR_START_HOUR) * 60

/** "10:10" -> 610 (minutes since midnight) */
export function timeToMinutes(time: string): number {
  const [h, m] = time.split(':').map(Number)
  return h * 60 + m
}

export function formatMinutesAsTime(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  const period = h < 12 ? 'AM' : 'PM'
  const h12 = h % 12 === 0 ? 12 : h % 12
  return `${h12}:${String(m).padStart(2, '0')} ${period}`
}

/** Vertical position (top px, height px) of a session within the 8am-6pm grid. */
export function sessionToGridStyle(session: ScheduleSession) {
  const start = Math.max(timeToMinutes(session.start), CALENDAR_START_HOUR * 60)
  const end = Math.min(timeToMinutes(session.end), CALENDAR_END_HOUR * 60)
  const top = ((start - CALENDAR_START_HOUR * 60) / CALENDAR_SPAN_MINUTES) * CALENDAR_HEIGHT_PX
  const height = ((end - start) / CALENDAR_SPAN_MINUTES) * CALENDAR_HEIGHT_PX
  return { top: `${top}px`, height: `${Math.max(height, 0)}px` }
}

function sessionsOverlap(a: ScheduleSession, b: ScheduleSession): boolean {
  if (a.day !== b.day) return false
  return timeToMinutes(a.start) < timeToMinutes(b.end) && timeToMinutes(b.start) < timeToMinutes(a.end)
}

/** True if `course` has any session that overlaps any session of any course already in `scheduled`. */
export function courseConflictsWithSchedule(course: Course, scheduled: Course[]): boolean {
  return scheduled.some(
    (placed) =>
      placed.id !== course.id &&
      course.schedule_time.some((s1) => placed.schedule_time.some((s2) => sessionsOverlap(s1, s2)))
  )
}

/** e.g. "COMS4118W" -> "COMS", "COMS-W3157" -> "COMS" */
export function getDepartment(courseId: string): string {
  return courseId.match(/^[A-Za-z]+/)?.[0]?.toUpperCase() ?? ''
}
