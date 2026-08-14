import type { DayCode } from './course'
import { CALENDAR_END_HOUR, CALENDAR_START_HOUR } from '../utils/schedule'

export const DEPARTMENTS = [
  { code: 'COMS', label: 'COMPUTER SCIENCE' },
  { code: 'ELEN', label: 'ELECTRICAL ENGINEERING' },
  // { code: 'MECE', label: 'MECHANICAL ENGINEERING' },
  { code: 'STAT', label: 'STATISTICS' },
  { code: 'PSYC', label: 'PSYCHOLOGY' }
] as const

export interface Filters {
  departments: string[] // empty = all departments
  levelRange: [number, number]
  days: DayCode[] // empty = all days
  timeRange: [number, number] // minutes since midnight
}

export const LEVEL_MIN = 1000
export const LEVEL_MAX = 9999

export const DEFAULT_FILTERS: Filters = {
  departments: [],
  levelRange: [LEVEL_MIN, LEVEL_MAX],
  days: [],
  timeRange: [CALENDAR_START_HOUR * 60, CALENDAR_END_HOUR * 60],
}
