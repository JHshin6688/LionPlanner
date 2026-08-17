import { useMemo, useState, type FormEvent } from 'react'
import { useChat } from '../hooks/useChat'
import { formatRelativeTime } from '../utils/chatStorage'
import { MarkdownMessage } from './MarkdownMessage'
import type { Course } from '../types/course'

interface AskLionPlannerProps {
  scheduledCourses: Course[]
}

type View = 'chat' | 'sessions'

export function AskLionPlanner({ scheduledCourses }: AskLionPlannerProps) {
  const { sessions, activeSession, activeSessionId, isLoading, error, sendMessage, createNewSession, switchSession } =
    useChat(scheduledCourses)
  const [draft, setDraft] = useState('')
  const [view, setView] = useState<View>('chat')

  const sortedSessions = useMemo(() => [...sessions].sort((a, b) => b.updatedAt - a.updatedAt), [sessions])

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (isLoading) return
    const query = draft
    setDraft('')
    void sendMessage(query)
  }

  return (
    <div className="hidden h-full w-96 shrink-0 flex-col border-l border-slate-200 bg-slate-50 xl:flex">
      <div className="shrink-0 border-b border-slate-200 px-4 py-2.5">
        <h2 className="text-sm font-semibold text-slate-800">Ask LionPlanner</h2>
        <p className="mt-0.5 text-xs text-slate-500">Ask about courses, workload, or your schedule.</p>
        <div className="mt-2 flex items-center gap-3 text-xs font-medium">
          <button type="button" onClick={createNewSession} className="text-indigo-600 hover:underline">
            + New Chat
          </button>
          <button
            type="button"
            onClick={() => setView((v) => (v === 'chat' ? 'sessions' : 'chat'))}
            className="text-indigo-600 hover:underline"
          >
            {view === 'chat' ? `History (${sessions.length})` : '← Back to chat'}
          </button>
        </div>
      </div>

      {view === 'sessions' ? (
        <div className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
          {sortedSessions.map((session) => (
            <button
              key={session.id}
              type="button"
              onClick={() => {
                switchSession(session.id)
                setView('chat')
              }}
              className={`w-full rounded-lg border px-3 py-2 text-left transition ${
                session.id === activeSessionId
                  ? 'border-indigo-300 bg-indigo-50'
                  : 'border-transparent bg-white hover:border-slate-200'
              }`}
            >
              <p className="truncate text-sm font-medium text-slate-800">{session.title}</p>
              <p className="mt-0.5 text-xs text-slate-500">
                {session.messages.length} message{session.messages.length === 1 ? '' : 's'} ·{' '}
                {formatRelativeTime(session.updatedAt)}
              </p>
            </button>
          ))}
        </div>
      ) : (
        <>
          <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-3">
            {activeSession.messages.length === 0 && (
              <p className="mt-2 text-center text-xs text-slate-400">Start a new conversation.</p>
            )}
            {activeSession.messages.map((message, i) => (
              <div
                key={i}
                className={
                  message.role === 'user'
                    ? 'ml-auto max-w-[85%] rounded-lg bg-indigo-600 px-3 py-2 text-xs whitespace-pre-wrap text-white'
                    : 'mr-auto max-w-[85%] rounded-lg bg-white px-3 py-2 text-xs text-slate-800 shadow-sm'
                }
              >
                {message.role === 'assistant' ? <MarkdownMessage content={message.content} /> : message.content}
              </div>
            ))}
            {isLoading && <div className="mr-auto text-xs text-slate-400">Thinking...</div>}
            {error && <div className="mr-auto text-xs text-red-600">{error}</div>}
          </div>

          <form onSubmit={handleSubmit} className="shrink-0 border-t border-slate-200 p-3">
            <div className="flex gap-2">
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Ask a question..."
                className="min-w-0 flex-1 rounded-md border border-slate-300 px-2.5 py-1.5 text-xs focus:border-indigo-500 focus:outline-none"
              />
              <button
                type="submit"
                disabled={isLoading || !draft.trim()}
                className="shrink-0 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
              >
                Send
              </button>
            </div>
          </form>
        </>
      )}
    </div>
  )
}
