import { beforeEach, describe, expect, it } from 'vitest'
import { DEFAULT_FILTERS } from '../types/filters'
import { loadFilters, loadScheduledCourseIds, saveFilters, saveScheduledCourseIds } from './appStorage'

beforeEach(() => sessionStorage.clear())

describe('filters persistence', () => {
  it('returns defaults when nothing is stored', () => {
    expect(loadFilters()).toEqual(DEFAULT_FILTERS)
  })

  it('round-trips saved filters', () => {
    const filters = { ...DEFAULT_FILTERS, titleQuery: 'ml', departments: ['COMS'] }
    saveFilters(filters)
    expect(loadFilters()).toEqual(filters)
  })

  it('fills fields missing from an older saved blob with defaults', () => {
    sessionStorage.setItem('lionplanner:filters', JSON.stringify({ titleQuery: 'old' }))
    expect(loadFilters()).toEqual({ ...DEFAULT_FILTERS, titleQuery: 'old' })
  })

  it('falls back to defaults on corrupted JSON', () => {
    sessionStorage.setItem('lionplanner:filters', 'oops')
    expect(loadFilters()).toEqual(DEFAULT_FILTERS)
  })
})

describe('scheduled course ids persistence', () => {
  it('defaults to an empty list', () => {
    expect(loadScheduledCourseIds()).toEqual([])
  })

  it('round-trips ids', () => {
    saveScheduledCourseIds(['a', 'b'])
    expect(loadScheduledCourseIds()).toEqual(['a', 'b'])
  })

  it('falls back to an empty list on corrupted JSON', () => {
    sessionStorage.setItem('lionplanner:scheduled-course-ids', '{')
    expect(loadScheduledCourseIds()).toEqual([])
  })
})
