import type { Course } from '../types/course'
import type { Filters } from '../types/filters'
import { CourseBlock } from './CourseBlock'
import { FilterPanel } from './FilterPanel'

interface CourseListPanelProps {
  courses: Course[]
  filters: Filters
  onFiltersChange: (filters: Filters) => void
  scheduledCourseIds: Set<string>
  hoveredCourseId: string | null
  onHoverCourse: (courseId: string | null) => void
  isLoading: boolean
}

export function CourseListPanel({
  courses,
  filters,
  onFiltersChange,
  scheduledCourseIds,
  hoveredCourseId,
  onHoverCourse,
  isLoading,
}: CourseListPanelProps) {
  return (
    <div className="flex h-full w-80 shrink-0 flex-col border-r border-slate-200 bg-slate-50">
      <FilterPanel filters={filters} onChange={onFiltersChange} />
      <div className="flex-1 overflow-y-auto p-3">
        {isLoading && <p className="p-4 text-center text-sm text-slate-400">Loading courses...</p>}
        {!isLoading && courses.length === 0 && (
          <p className="p-4 text-center text-sm text-slate-400">No courses match the current filters.</p>
        )}
        <div className="space-y-2">
          {courses.map((course) => (
            <CourseBlock
              key={course.id}
              course={course}
              isAdded={scheduledCourseIds.has(course.id)}
              isHovered={hoveredCourseId === course.id}
              onHoverStart={() => onHoverCourse(course.id)}
              onHoverEnd={() => onHoverCourse(null)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
