import { describe, expect, it } from 'vitest'
import type { Course, ScheduleSession } from '../types/course'
import {
  CALENDAR_HEIGHT_PX,
  courseConflictsWithSchedule,
  formatMinutesAsTime,
  formatSessionTimeRange,
  formatSessionTimeRangeFull,
  sessionToGridStyle,
  timeToMinutes,
} from './schedule'

const session = (day: ScheduleSession['day'], start: string, end: string): ScheduleSession => ({ day, start, end })

const course = (id: string, schedule_time: ScheduleSession[]) => ({ id, schedule_time }) as Course

describe('timeToMinutes', () => {
  it('converts HH:MM to minutes since midnight', () => {
    expect(timeToMinutes('00:00')).toBe(0)
    expect(timeToMinutes('10:10')).toBe(610)
    expect(timeToMinutes('23:59')).toBe(1439)
  })
})

describe('time formatting', () => {
  it('formatMinutesAsTime handles midnight, noon and PM', () => {
    expect(formatMinutesAsTime(0)).toBe('12:00 AM')
    expect(formatMinutesAsTime(720)).toBe('12:00 PM')
    expect(formatMinutesAsTime(13 * 60 + 5)).toBe('1:05 PM')
  })

  it('formatSessionTimeRange drops minutes on the hour', () => {
    expect(formatSessionTimeRange(session('Mon', '11:00', '14:00'))).toBe('11am - 2pm')
    expect(formatSessionTimeRange(session('Mon', '10:10', '11:25'))).toBe('10:10am - 11:25am')
  })

  it('formatSessionTimeRangeFull always shows minutes', () => {
    expect(formatSessionTimeRangeFull(session('Mon', '11:00', '12:45'))).toBe('11:00am - 12:45pm')
  })
})

describe('sessionToGridStyle', () => {
  it('places a session at the calendar start at top 0', () => {
    const style = sessionToGridStyle(session('Mon', '07:00', '08:00'))
    expect(style.top).toBe('0px')
    expect(parseFloat(style.height)).toBeCloseTo(64)
  })

  it('clamps sessions that extend beyond the visible calendar', () => {
    const style = sessionToGridStyle(session('Mon', '05:00', '23:00'))
    expect(style.top).toBe('0px')
    expect(parseFloat(style.height)).toBeCloseTo(CALENDAR_HEIGHT_PX)
  })

  it('never returns a negative height', () => {
    const style = sessionToGridStyle(session('Mon', '22:00', '23:00'))
    expect(parseFloat(style.height)).toBeGreaterThanOrEqual(0)
  })
})

describe('courseConflictsWithSchedule', () => {
  const placed = course('a', [session('Tue', '08:40', '09:55')])

  it('detects overlap on the same day', () => {
    expect(courseConflictsWithSchedule(course('b', [session('Tue', '09:00', '10:15')]), [placed])).toBe(true)
  })

  it('treats back-to-back sessions as non-conflicting', () => {
    expect(courseConflictsWithSchedule(course('b', [session('Tue', '09:55', '11:00')]), [placed])).toBe(false)
  })

  it('ignores the same time on a different day', () => {
    expect(courseConflictsWithSchedule(course('b', [session('Wed', '08:40', '09:55')]), [placed])).toBe(false)
  })

  it('does not conflict a course with itself', () => {
    expect(courseConflictsWithSchedule(placed, [placed])).toBe(false)
  })

  it('returns false for an empty schedule', () => {
    expect(courseConflictsWithSchedule(placed, [])).toBe(false)
  })
})
