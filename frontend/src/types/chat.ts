// Request shape mirrors src/api/schemas.py::ChatRequest. The response is a
// text/event-stream of ChatStreamEvent JSON lines, not a single JSON body —
// see src/api/main.py.

export type ChatRole = 'user' | 'assistant'

export interface ChatMessage {
  role: ChatRole
  content: string
}

export type ChatRoute = 'recommend_course' | 'analyze_workload' | 'general_question'

export interface ScheduledCoursePayload {
  course_id: string
  course_title: string
  workload_analysis: unknown
}

export interface ChatRequestBody {
  session_id: string
  query: string
  chat_history: ChatMessage[]
  scheduled_courses: ScheduledCoursePayload[]
}

// Server-Sent Events emitted by POST /api/chat (src/api/main.py), one JSON
// object per `data: ` line.
export type ChatStreamEvent =
  | { type: 'token'; delta: string }
  | { type: 'restart' }
  | { type: 'done'; route: ChatRoute }
  | { type: 'error'; message: string }

export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
  updatedAt: number
}
