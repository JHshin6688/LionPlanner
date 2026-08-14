import type { Course } from '../types/course'
import { DEPARTMENTS } from '../types/filters'

const SIZE = 76
const STROKE = 10
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
const GAP = 3 // small visual gap between ring segments

// Categorical slots 1-3 (blue/orange/aqua) from the app's validated palette —
// the only ordering that clears all-pairs CVD separation for 3 simultaneous segments.
const DEPARTMENT_COLORS: Record<string, string> = {
  COMS: '#2a78d6',
  ELEN: '#eb6834',
  // MECE: '#1baf7a',
  STAT: '#f5a623',
  PSYC: '#9b51e0',
}
const OTHER_COLOR = '#94a3b8' // slate-400, neutral fallback for any other department
const TRACK_COLOR = '#e2e8f0' // slate-200

interface TotalCreditsCardProps {
  scheduledCourses: Course[]
}

export function TotalCreditsCard({ scheduledCourses }: TotalCreditsCardProps) {
  const creditsByDept = new Map<string, number>()
  for (const course of scheduledCourses) {
    const dept = course.department.toUpperCase()
    const key = dept in DEPARTMENT_COLORS ? dept : 'Other'
    creditsByDept.set(key, (creditsByDept.get(key) ?? 0) + course.credits)
  }

  const orderedKeys = [...DEPARTMENTS.map((d) => d.code), 'Other']
  const segments = orderedKeys
    .map((key) => ({ key, credits: creditsByDept.get(key) ?? 0, color: DEPARTMENT_COLORS[key] ?? OTHER_COLOR }))
    .filter((s) => s.credits > 0)

  const totalCredits = segments.reduce((sum, s) => sum + s.credits, 0)

  let cumulative = 0
  const arcs = segments.map((s) => {
    const rawLength = (s.credits / totalCredits) * CIRCUMFERENCE
    const drawnLength = segments.length > 1 ? Math.max(0, rawLength - GAP) : rawLength
    const offset = cumulative
    cumulative += rawLength
    return { ...s, offset, drawnLength }
  })

  return (
    <div className="border-b border-slate-200 p-4">
      <h2 className="text-sm font-semibold text-slate-800">Total Credits</h2>

      <div className="mt-3 flex items-center gap-4">
        <div className="relative shrink-0" style={{ width: SIZE, height: SIZE }}>
          <svg width={SIZE} height={SIZE} className="-rotate-90">
            <circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} stroke={TRACK_COLOR} strokeWidth={STROKE} fill="none" />
            {arcs.map((arc) => (
              <circle
                key={arc.key}
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={RADIUS}
                stroke={arc.color}
                strokeWidth={STROKE}
                fill="none"
                strokeDasharray={`${arc.drawnLength} ${CIRCUMFERENCE - arc.drawnLength}`}
                strokeDashoffset={-arc.offset}
              />
            ))}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-lg font-bold leading-none text-slate-900">{totalCredits}</span>
            <span className="text-[10px] text-slate-500">{pluralizeCredit(totalCredits)}</span>
          </div>
        </div>

        <div className="flex-1 space-y-1">
          {arcs.map((arc) => (
            <div key={arc.key} className="flex items-center justify-between gap-2 text-xs">
              <span className="flex items-center gap-1.5 text-slate-600">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: arc.color }} />
                {arc.key}
              </span>
              <span className="font-medium text-slate-800">
                {arc.credits} {pluralizeCredit(arc.credits)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function pluralizeCredit(count: number): string {
  return count <= 1 ? 'credit' : 'credits'
}
