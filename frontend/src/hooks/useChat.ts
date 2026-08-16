import { useEffect, useState } from 'react'
import type { Course } from '../types/course'
import type { ChatMessage, ChatResponseBody } from '../types/chat'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string | undefined

// sessionStorage (not localStorage): survives a refresh but clears when the
// tab/window closes, which is the behavior we want for chat history here.
const STORAGE_KEY = 'lionplanner:ask-messages'

function loadStoredMessages(): ChatMessage[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as ChatMessage[]) : []
  } catch {
    return []
  }
}

export function useChat(scheduledCourses: Course[]) {
  const [messages, setMessages] = useState<ChatMessage[]>(loadStoredMessages)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
    } catch {
      // sessionStorage unavailable (private mode, quota, etc.) — chat still
      // works for the current page load, it just won't survive a refresh.
    }
  }, [messages])

  async function sendMessage(query: string) {
    const trimmed = query.trim()
    if (!trimmed) return
    if (!API_BASE_URL) {
      setError('Missing VITE_API_BASE_URL — set it to the Ask LionPlanner API URL.')
      return
    }

    const nextMessages: ChatMessage[] = [...messages, { role: 'user', content: trimmed }]
    setMessages(nextMessages)
    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
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
      setMessages((prev) => [...prev, { role: 'assistant', content: data.answer }])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reach Ask LionPlanner.')
    } finally {
      setIsLoading(false)
    }
  }

  return { messages, isLoading, error, sendMessage }
}
