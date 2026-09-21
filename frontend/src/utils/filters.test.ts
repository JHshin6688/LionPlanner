import { describe, expect, it } from 'vitest'
import type { Course } from '../types/course'
import { DEFAULT_FILTERS, type Filters } from '../types/filters'
import { applyFilters } from './filters'

const make = (over: Partial<Course>): Course =>
  ({
    id: 'x',
    course_id: 'COMS W4111',
    course_title: 'Introduction to Databases',
    department: 'COMS',
    course_level: 4000,
    schedule_time: [{ day: 'Tue', start: '10:10', end: '11:25' }],
    ...over,
  }) as Course

const withFilters = (over: Partial<Filters>): Filters => ({ ...DEFAULT_FILTERS, ...over })

const db = make({ id: 'db' })
const ml = make({ id: 'ml', course_title: 'Machine Learning', department: 'COMS', course_level: 4000 })
const stat = make({
  id: 'stat',
  course_title: 'Data Mining',
  department: 'STAT',
  course_level: 5000,
  schedule_time: [{ day: 'Thu', start: '18:15', end: '19:50' }],
})
const unscheduled = make({ id: 'tba', course_title: 'Independent Study', schedule_time: [] })

const ids = (courses: Course[]) => courses.map((c) => c.id)

describe('applyFilters', () => {
  const all = [db, ml, stat, unscheduled]

  it('default filters keep everything', () => {
    expect(ids(applyFilters(all, DEFAULT_FILTERS))).toEqual(['db', 'ml', 'stat', 'tba'])
  })

  it('title query is case-insensitive and trimmed', () => {
    expect(ids(applyFilters(all, withFilters({ titleQuery: '  machine  ' })))).toEqual(['ml'])
  })

  it('filters by department', () => {
    expect(ids(applyFilters(all, withFilters({ departments: ['STAT'] })))).toEqual(['stat'])
  })

  it('filters by level range (inclusive)', () => {
    expect(ids(applyFilters(all, withFilters({ levelRange: [5000, 5000] })))).toEqual(['stat'])
  })

  it('day filter drops courses with no session on that day, including unscheduled ones', () => {
    expect(ids(applyFilters(all, withFilters({ days: ['Thu'] })))).toEqual(['stat'])
  })

  it('time range requires a session to fit fully inside it', () => {
    const morning = withFilters({ timeRange: [8 * 60, 12 * 60] })
    expect(ids(applyFilters(all, morning))).toEqual(['db', 'ml', 'tba'])
  })

  it('unscheduled courses are not hidden by the time range', () => {
    expect(ids(applyFilters([unscheduled], withFilters({ timeRange: [0, 60] })))).toEqual(['tba'])
  })
})
