import { DEFAULT_FILTERS, type Filters } from '../types/filters'

// sessionStorage (not localStorage): survives a refresh but clears when the
// tab/window closes — filters and the in-progress schedule shouldn't outlive
// the browsing session any more than chat history does.
const FILTERS_KEY = 'lionplanner:filters'
const SCHEDULED_IDS_KEY = 'lionplanner:scheduled-course-ids'

export function loadFilters(): Filters {
  try {
    const raw = sessionStorage.getItem(FILTERS_KEY)
    if (!raw) return DEFAULT_FILTERS
    // Spread over the defaults so a filter field added later (not present in
    // an older saved blob) falls back cleanly instead of being undefined.
    return { ...DEFAULT_FILTERS, ...(JSON.parse(raw) as Partial<Filters>) }
  } catch {
    return DEFAULT_FILTERS
  }
}

export function saveFilters(filters: Filters): void {
  try {
    sessionStorage.setItem(FILTERS_KEY, JSON.stringify(filters))
  } catch {
    // sessionStorage unavailable (private mode, quota, etc.) — filters still
    // work for the current page load, they just won't persist.
  }
}

export function loadScheduledCourseIds(): string[] {
  try {
    const raw = sessionStorage.getItem(SCHEDULED_IDS_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

export function saveScheduledCourseIds(ids: string[]): void {
  try {
    sessionStorage.setItem(SCHEDULED_IDS_KEY, JSON.stringify(ids))
  } catch {
    // Ignore — see saveFilters above.
  }
}
