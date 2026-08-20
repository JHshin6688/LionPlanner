import { useEffect, useRef, useState } from 'react'
import type { Course } from '../types/course'
import type { ChatMessage, ChatSession, ChatStreamEvent } from '../types/chat'
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

  // Streaming updates setSessions once per token, which can be dozens of
  // times a second for a long answer — debounce the sessionStorage write
  // rather than doing it on every single one.
  const saveTimeoutRef = useRef<number | undefined>(undefined)
  useEffect(() => {
    if (saveTimeoutRef.current) window.clearTimeout(saveTimeoutRef.current)
    saveTimeoutRef.current = window.setTimeout(() => saveSessions(sessions), 300)
    return () => {
      if (saveTimeoutRef.current) window.clearTimeout(saveTimeoutRef.current)
    }
  }, [sessions])
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

    // Applies `updater` to the trailing assistant message's content for this
    // session, creating that message on its first call (right after the user
    // message we just pushed, so the trailing message is always 'user' then).
    function updateAssistantMessage(updater: (prev: string) => string) {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== sessionId) return s
          const last = s.messages[s.messages.length - 1]
          if (last?.role === 'assistant') {
            const updated = [...s.messages]
            updated[updated.length - 1] = { ...last, content: updater(last.content) }
            return { ...s, messages: updated, updatedAt: Date.now() }
          }
          return {
            ...s,
            messages: [...s.messages, { role: 'assistant', content: updater('') }],
            updatedAt: Date.now(),
          }
        })
      )
    }

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
            schedule_time: c.schedule_time,
          })),
        }),
      })
      if (!response.ok || !response.body) {
        throw new Error(`Ask LionPlanner request failed (${response.status})`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        let boundary: number
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const rawEvent = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)
          const dataLine = rawEvent.split('\n').find((line) => line.startsWith('data: '))
          if (!dataLine) continue

          const streamEvent = JSON.parse(dataLine.slice('data: '.length)) as ChatStreamEvent
          if (streamEvent.type === 'token') {
            updateAssistantMessage((prev) => prev + streamEvent.delta)
          } else if (streamEvent.type === 'restart') {
            // verify_grounding rejected what we've shown so far and either
            // retried or replaced it with a fallback — clear and start over.
            updateAssistantMessage(() => '')
          } else if (streamEvent.type === 'error') {
            setError(streamEvent.message)
          }
          // 'done' needs no handling — the loop just exits naturally after.
        }
      }
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
