import { useMemo, useState } from 'react'
import { AskLionPlanner } from './components/AskLionPlanner'
import { CalendarGrid } from './components/CalendarGrid'
import { CourseListPanel } from './components/CourseListPanel'
import { useCourses } from './hooks/useCourses'
import type { Course } from './types/course'
import { DEFAULT_FILTERS, type Filters } from './types/filters'
import { applyFilters } from './utils/filters'
import { courseConflictsWithSchedule } from './utils/schedule'

function App() {
  const { courses, isLoading, error } = useCourses()
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [hoveredCourseId, setHoveredCourseId] = useState<string | null>(null)
  const [scheduledCourses, setScheduledCourses] = useState<Course[]>([])

  const scheduledCourseIds = useMemo(() => new Set(scheduledCourses.map((c) => c.id)), [scheduledCourses])
  const filteredCourses = useMemo(() => {
    const filtered = applyFilters(courses, filters)
    // Added courses are pinned to the top of the scrollable list.
    return [...filtered].sort((a, b) => Number(scheduledCourseIds.has(b.id)) - Number(scheduledCourseIds.has(a.id)))
  }, [courses, filters, scheduledCourseIds])
  const hoveredCourse = useMemo(
    () => courses.find((c) => c.id === hoveredCourseId) ?? null,
    [courses, hoveredCourseId]
  )
  const hoveredCourseConflicts = useMemo(
    () => (hoveredCourse ? courseConflictsWithSchedule(hoveredCourse, scheduledCourses) : false),
    [hoveredCourse, scheduledCourses]
  )

  const handleDropCourse = (courseId: string) => {
    const course = courses.find((c) => c.id === courseId)
    if (!course) return
    if (scheduledCourseIds.has(course.id)) return
    if (courseConflictsWithSchedule(course, scheduledCourses)) return
    setScheduledCourses((prev) => [...prev, course])
  }

  const handleRemoveCourse = (courseId: string) => {
    setScheduledCourses((prev) => prev.filter((c) => c.id !== courseId))
  }

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-white">
      <header className="flex shrink-0 items-center border-b border-slate-200 px-4 py-2.5">
        <h1 className="text-base font-bold text-slate-900">LionPlanner</h1>
        {error && <span className="ml-4 text-xs text-red-600">Failed to load courses: {error}</span>}
      </header>
      <div className="flex min-h-0 flex-1">
        <CourseListPanel
          courses={filteredCourses}
          filters={filters}
          onFiltersChange={setFilters}
          scheduledCourses={scheduledCourses}
          scheduledCourseIds={scheduledCourseIds}
          hoveredCourseId={hoveredCourseId}
          onHoverCourse={setHoveredCourseId}
          isLoading={isLoading}
        />
        <CalendarGrid
          scheduledCourses={scheduledCourses}
          hoveredCourse={hoveredCourse}
          hoveredCourseConflicts={hoveredCourseConflicts}
          onDropCourse={handleDropCourse}
          onRemoveCourse={handleRemoveCourse}
        />
        <AskLionPlanner scheduledCourses={scheduledCourses} />
      </div>
    </div>
  )
}

export default App
