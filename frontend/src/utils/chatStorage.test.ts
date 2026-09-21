import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ChatSession } from '../types/chat'
import {
  createSession,
  deriveTitle,
  formatRelativeTime,
  loadActiveSessionId,
  loadSessions,
  saveActiveSessionId,
  saveSessions,
} from './chatStorage'

beforeEach(() => sessionStorage.clear())
afterEach(() => vi.useRealTimers())

describe('session persistence', () => {
  it('returns an empty list when nothing is stored', () => {
    expect(loadSessions()).toEqual([])
  })

  it('round-trips sessions', () => {
    const sessions: ChatSession[] = [createSession()]
    saveSessions(sessions)
    expect(loadSessions()).toEqual(sessions)
  })

  it('falls back to an empty list on corrupted JSON', () => {
    sessionStorage.setItem('lionplanner:chat-sessions', '{not json')
    expect(loadSessions()).toEqual([])
  })

  it('round-trips the active session id, null when unset', () => {
    expect(loadActiveSessionId()).toBeNull()
    saveActiveSessionId('abc')
    expect(loadActiveSessionId()).toBe('abc')
  })

  it('does not throw when storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    expect(() => saveSessions([])).not.toThrow()
    expect(() => saveActiveSessionId('x')).not.toThrow()
    vi.restoreAllMocks()
  })
})

describe('createSession', () => {
  it('creates an empty "New Chat" session with a unique id', () => {
    const a = createSession()
    const b = createSession()
    expect(a.title).toBe('New Chat')
    expect(a.messages).toEqual([])
    expect(a.id).not.toBe(b.id)
  })
})

describe('deriveTitle', () => {
  it('collapses whitespace and keeps short titles intact', () => {
    expect(deriveTitle('  hello   there \n friend ')).toBe('hello there friend')
  })

  it('truncates long titles to 40 chars with an ellipsis', () => {
    const title = deriveTitle('a'.repeat(100))
    expect(title).toBe(`${'a'.repeat(40)}…`)
  })
})

describe('formatRelativeTime', () => {
  const now = new Date('2026-01-01T12:00:00Z').getTime()

  it.each([
    [20 * 1000, 'just now'],
    [5 * 60 * 1000, '5m ago'],
    [3 * 60 * 60 * 1000, '3h ago'],
    [2 * 24 * 60 * 60 * 1000, '2d ago'],
  ])('%i ms ago -> %s', (offset, expected) => {
    vi.useFakeTimers()
    vi.setSystemTime(now)
    expect(formatRelativeTime(now - offset)).toBe(expected)
  })

  it('falls back to a date string after a week', () => {
    vi.useFakeTimers()
    vi.setSystemTime(now)
    const old = now - 30 * 24 * 60 * 60 * 1000
    expect(formatRelativeTime(old)).toBe(new Date(old).toLocaleDateString())
  })
})
