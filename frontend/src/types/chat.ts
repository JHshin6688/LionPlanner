// Mirrors src/api/schemas.py (ChatRequest/ChatResponse) in the backend.

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
  query: string
  chat_history: ChatMessage[]
  scheduled_courses: ScheduledCoursePayload[]
}

export interface ChatResponseBody {
  answer: string
  route: ChatRoute
}
