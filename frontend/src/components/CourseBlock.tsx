import type { Course } from '../types/course'

export const COURSE_DRAG_MIME = 'application/x-lionplanner-course-id'

interface CourseBlockProps {
  course: Course
  isAdded: boolean
  isHovered: boolean
  onHoverStart: () => void
  onHoverEnd: () => void
}

export function CourseBlock({ course, isAdded, isHovered, onHoverStart, onHoverEnd }: CourseBlockProps) {
  return (
    <div
      draggable={!isAdded}
      onDragStart={(e) => {
        e.dataTransfer.setData(COURSE_DRAG_MIME, course.id)
        e.dataTransfer.effectAllowed = 'copy'
      }}
      onMouseEnter={onHoverStart}
      onMouseLeave={onHoverEnd}
      className={`rounded-lg border p-3 transition ${
        isAdded
          ? 'cursor-not-allowed border-slate-200 bg-slate-100 opacity-60'
          : `cursor-grab border-slate-200 bg-white hover:border-indigo-400 hover:shadow-sm active:cursor-grabbing ${
              isHovered ? 'border-indigo-400 shadow-sm' : ''
            }`
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold tracking-wide text-indigo-600">{course.course_id}</span>
        {isAdded && (
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
            Added
          </span>
        )}
      </div>
      <p className="mt-1 truncate text-sm font-medium text-slate-900">{course.course_title}</p>
      <p className="truncate text-xs text-slate-500">{course.instructor_name}</p>
    </div>
  )
}
