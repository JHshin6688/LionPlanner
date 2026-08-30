import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabaseClient'
import type { Course } from '../types/course'

export function useCourses() {
  const [courses, setCourses] = useState<Course[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setIsLoading(true)
      const { data, error } = await supabase.from('courses_semester_view').select('*').order('course_id')
      if (cancelled) return
      if (error) {
        setError(error.message)
      } else {
        // course_id doubles as `id` - courses_semester_view has no surrogate
        // UUID column (the old `courses` table's `id` is gone in the new schema).
        setCourses(
          (data ?? []).map((course) => ({
            ...course,
            id: course.course_id,
            course_title: course.course_title.toUpperCase(),
          })) as Course[]
        )
      }
      setIsLoading(false)
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  return { courses, isLoading, error }
}
