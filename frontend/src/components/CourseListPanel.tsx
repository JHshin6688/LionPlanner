import { useEffect, useRef, useState } from 'react'
import type { Course } from '../types/course'
import type { Filters } from '../types/filters'
import { CourseBlock } from './CourseBlock'
import { CourseHoverCard } from './CourseHoverCard'
import { FilterPanel } from './FilterPanel'
import { TotalCreditsCard } from './TotalCreditsCard'

interface CourseListPanelProps {
  courses: Course[]
  filters: Filters
  onFiltersChange: (filters: Filters) => void
  scheduledCourses: Course[]
  scheduledCourseIds: Set<string>
  hoveredCourseId: string | null
  onHoverCourse: (courseId: string | null) => void
  isLoading: boolean
}

export function CourseListPanel({
  courses,
  filters,
  onFiltersChange,
  scheduledCourses,
  scheduledCourseIds,
  hoveredCourseId,
  onHoverCourse,
  isLoading,
}: CourseListPanelProps) {
  const [hoverAnchor, setHoverAnchor] = useState<{ course: Course; rect: DOMRect } | null>(null)
  const closeTimeoutRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (closeTimeoutRef.current !== null) window.clearTimeout(closeTimeoutRef.current)
    }
  }, [])

  const cancelClose = () => {
    if (closeTimeoutRef.current !== null) {
      window.clearTimeout(closeTimeoutRef.current)
      closeTimeoutRef.current = null
    }
  }

  // Small delay so moving the mouse from the block to the card (across the gap
  // between them) doesn't close the card before the cursor arrives.
  const scheduleClose = () => {
    closeTimeoutRef.current = window.setTimeout(() => {
      onHoverCourse(null)
      setHoverAnchor(null)
    }, 150)
  }

  return (
    <div className="flex h-full w-80 shrink-0 flex-col border-r border-slate-200 bg-slate-50">
      <FilterPanel filters={filters} onChange={onFiltersChange} />
      <TotalCreditsCard scheduledCourses={scheduledCourses} />
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
              onHoverStart={(rect) => {
                cancelClose()
                onHoverCourse(course.id)
                setHoverAnchor({ course, rect })
              }}
              onHoverEnd={scheduleClose}
            />
          ))}
        </div>
      </div>
      {hoverAnchor && (
        <CourseHoverCard
          course={hoverAnchor.course}
          anchorRect={hoverAnchor.rect}
          onMouseEnter={cancelClose}
          onMouseLeave={scheduleClose}
        />
      )}
    </div>
  )
}
