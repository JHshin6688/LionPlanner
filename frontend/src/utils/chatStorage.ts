import type { ChatSession } from '../types/chat'

// sessionStorage (not localStorage): survives a refresh but clears when the
// tab/window closes. The full history is also durably saved server-side per
// session (see src/db/supabase_client.py::save_chat_turn) — this is just the
// client-side cache that drives the session list/switcher UI.
const SESSIONS_KEY = 'lionplanner:chat-sessions'
const ACTIVE_SESSION_KEY = 'lionplanner:active-session-id'
const TITLE_MAX_LENGTH = 40

export function loadSessions(): ChatSession[] {
  try {
    const raw = sessionStorage.getItem(SESSIONS_KEY)
    return raw ? (JSON.parse(raw) as ChatSession[]) : []
  } catch {
    return []
  }
}

export function saveSessions(sessions: ChatSession[]): void {
  try {
    sessionStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions))
  } catch {
    // sessionStorage unavailable (private mode, quota, etc.) — chat still works
    // for the current page load, it just won't persist.
  }
}

export function loadActiveSessionId(): string | null {
  try {
    return sessionStorage.getItem(ACTIVE_SESSION_KEY)
  } catch {
    return null
  }
}

export function saveActiveSessionId(id: string): void {
  try {
    sessionStorage.setItem(ACTIVE_SESSION_KEY, id)
  } catch {
    // Ignore — see saveSessions above.
  }
}

export function createSession(): ChatSession {
  const now = Date.now()
  return {
    id: crypto.randomUUID(),
    title: 'New Chat',
    messages: [],
    createdAt: now,
    updatedAt: now,
  }
}

/** Derives a short session title from the first user message, e.g. for the session list. */
export function deriveTitle(firstMessage: string): string {
  const trimmed = firstMessage.trim().replace(/\s+/g, ' ')
  if (trimmed.length <= TITLE_MAX_LENGTH) return trimmed
  return `${trimmed.slice(0, TITLE_MAX_LENGTH).trimEnd()}…`
}

export function formatRelativeTime(timestamp: number): string {
  const diffMs = Date.now() - timestamp
  const diffMin = Math.round(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.round(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.round(diffHr / 24)
  if (diffDay < 7) return `${diffDay}d ago`
  return new Date(timestamp).toLocaleDateString()
}
