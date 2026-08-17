import { useEffect, useState } from 'react'
import type { Course } from '../types/course'
import type { ChatMessage, ChatResponseBody, ChatSession } from '../types/chat'
import {
  createSession,
  deriveTitle,
  loadActiveSessionId,
  loadSessions,
  saveActiveSessionId,
  saveSessions,
} from '../utils/chatStorage'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string | undefined

function initSessions(): ChatSession[] {
  const stored = loadSessions()
  return stored.length > 0 ? stored : [createSession()]
}

function initActiveSessionId(sessions: ChatSession[]): string {
  const stored = loadActiveSessionId()
  return stored && sessions.some((s) => s.id === stored) ? stored : sessions[0].id
}

export function useChat(scheduledCourses: Course[]) {
  const [sessions, setSessions] = useState<ChatSession[]>(initSessions)
  const [activeSessionId, setActiveSessionId] = useState(() => initActiveSessionId(sessions))
  const [loadingSessionIds, setLoadingSessionIds] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)

  useEffect(() => saveSessions(sessions), [sessions])
  useEffect(() => saveActiveSessionId(activeSessionId), [activeSessionId])

  const activeSession = sessions.find((s) => s.id === activeSessionId) ?? sessions[0]
  const isLoading = loadingSessionIds.has(activeSessionId)

  function createNewSession() {
    const session = createSession()
    setSessions((prev) => [session, ...prev])
    setActiveSessionId(session.id)
    setError(null)
  }

  function switchSession(id: string) {
    setActiveSessionId(id)
    setError(null)
  }

  async function sendMessage(query: string) {
    const trimmed = query.trim()
    if (!trimmed) return
    if (!API_BASE_URL) {
      setError('Missing VITE_API_BASE_URL — set it to the Ask LionPlanner API URL.')
      return
    }

    const sessionId = activeSessionId
    const priorMessages = sessions.find((s) => s.id === sessionId)?.messages ?? []
    const nextMessages: ChatMessage[] = [...priorMessages, { role: 'user', content: trimmed }]

    setSessions((prev) =>
      prev.map((s) =>
        s.id === sessionId
          ? {
              ...s,
              messages: nextMessages,
              title: s.messages.length === 0 ? deriveTitle(trimmed) : s.title,
              updatedAt: Date.now(),
            }
          : s
      )
    )
    setLoadingSessionIds((prev) => new Set(prev).add(sessionId))
    setError(null)

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          query: trimmed,
          chat_history: nextMessages,
          scheduled_courses: scheduledCourses.map((c) => ({
            course_id: c.course_id,
            course_title: c.course_title,
            workload_analysis: c.workload_analysis,
          })),
        }),
      })
      if (!response.ok) throw new Error(`Ask LionPlanner request failed (${response.status})`)
      const data = (await response.json()) as ChatResponseBody
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sessionId
            ? { ...s, messages: [...s.messages, { role: 'assistant', content: data.answer }], updatedAt: Date.now() }
            : s
        )
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reach Ask LionPlanner.')
    } finally {
      setLoadingSessionIds((prev) => {
        const next = new Set(prev)
        next.delete(sessionId)
        return next
      })
    }
  }

  return {
    sessions,
    activeSession,
    activeSessionId,
    isLoading,
    error,
    sendMessage,
    createNewSession,
    switchSession,
  }
}
