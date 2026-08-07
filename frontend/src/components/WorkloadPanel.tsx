import { WORKLOAD_DIMENSIONS, type Course } from '../types/course'

interface WorkloadPanelProps {
  scheduledCourses: Course[]
}

function average(values: number[]): number {
  if (values.length === 0) return 0
  return values.reduce((sum, v) => sum + v, 0) / values.length
}

export function WorkloadPanel({ scheduledCourses }: WorkloadPanelProps) {
  const averages = WORKLOAD_DIMENSIONS.map(({ key, label }) => ({
    key,
    label,
    score: average(scheduledCourses.map((c) => c.workload_analysis.workload_scores[key].score)),
  }))

  return (
    <div className="flex h-full w-80 shrink-0 flex-col border-l border-slate-200 bg-slate-50 p-4">
      <h2 className="text-sm font-semibold text-slate-800">Workload Analysis</h2>
      <p className="mt-0.5 text-xs text-slate-500">
        {scheduledCourses.length === 0
          ? 'Add courses to the calendar to see workload.'
          : `Average across ${scheduledCourses.length} course${scheduledCourses.length > 1 ? 's' : ''}`}
      </p>

      <div className="mt-5 space-y-4">
        {averages.map(({ key, label, score }) => (
          <div key={key}>
            <div className="mb-1 flex items-baseline justify-between">
              <span className="text-xs font-medium text-slate-600">{label}</span>
              <span className="text-xs font-semibold text-slate-800">{Math.round(score)}</span>
            </div>
            <div className="h-2 w-full rounded-full bg-slate-200">
              <div
                className="h-2 rounded-full bg-indigo-600 transition-all"
                style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
