import type { Course } from '../types/course'
import type { Filters } from '../types/filters'
import { getDepartment, timeToMinutes } from './schedule'

export function applyFilters(courses: Course[], filters: Filters): Course[] {
  return courses.filter((course) => {
    if (filters.departments.length > 0 && !filters.departments.includes(getDepartment(course.course_id))) {
      return false
    }

    if (course.course_level < filters.levelRange[0] || course.course_level > filters.levelRange[1]) {
      return false
    }

    const relevantSessions = filters.day
      ? course.schedule_time.filter((s) => s.day === filters.day)
      : course.schedule_time

    if (filters.day && relevantSessions.length === 0) {
      return false
    }

    if (relevantSessions.length === 0) {
      // No schedule info at all: don't hide it based on time range.
      return true
    }

    const [rangeStart, rangeEnd] = filters.timeRange
    return relevantSessions.some(
      (s) => timeToMinutes(s.start) < rangeEnd && rangeStart < timeToMinutes(s.end)
    )
  })
}
