import { DAY_CODES } from '../types/course'
import { DEFAULT_FILTERS, DEPARTMENTS, LEVEL_MAX, LEVEL_MIN, type Filters } from '../types/filters'
import { CALENDAR_END_HOUR, CALENDAR_START_HOUR, formatMinutesAsTime } from '../utils/schedule'
import { DualRangeSlider } from './DualRangeSlider'

interface FilterPanelProps {
  filters: Filters
  onChange: (filters: Filters) => void
}

export function FilterPanel({ filters, onChange }: FilterPanelProps) {
  const toggleDepartment = (code: string) => {
    const next = filters.departments.includes(code)
      ? filters.departments.filter((d) => d !== code)
      : [...filters.departments, code]
    onChange({ ...filters, departments: next })
  }

  const toggleDay = (day: (typeof DAY_CODES)[number]) => {
    onChange({ ...filters, day: filters.day === day ? null : day })
  }

  return (
    <div className="space-y-4 border-b border-slate-200 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-800">Filters</h2>
        <button
          type="button"
          onClick={() => onChange(DEFAULT_FILTERS)}
          className="text-xs font-medium text-indigo-600 hover:underline"
        >
          Reset
        </button>
      </div>

      <div>
        <p className="mb-1.5 text-xs font-medium text-slate-500">Department</p>
        <div className="flex flex-wrap gap-1.5">
          {DEPARTMENTS.map(({ code, label }) => (
            <button
              key={code}
              type="button"
              title={label}
              onClick={() => toggleDepartment(code)}
              className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                filters.departments.includes(code)
                  ? 'border-indigo-600 bg-indigo-600 text-white'
                  : 'border-slate-300 bg-white text-slate-600 hover:border-indigo-400'
              }`}
            >
              {code}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="mb-1.5 text-xs font-medium text-slate-500">Course Level</p>
        <DualRangeSlider
          min={LEVEL_MIN}
          max={LEVEL_MAX}
          step={1000}
          values={filters.levelRange}
          onChange={(levelRange) => onChange({ ...filters, levelRange })}
        />
      </div>

      <div>
        <p className="mb-1.5 text-xs font-medium text-slate-500">Day</p>
        <div className="flex flex-wrap gap-1.5">
          {DAY_CODES.map((day) => (
            <button
              key={day}
              type="button"
              onClick={() => toggleDay(day)}
              className={`w-10 rounded-full border py-1 text-xs font-medium transition ${
                filters.day === day
                  ? 'border-indigo-600 bg-indigo-600 text-white'
                  : 'border-slate-300 bg-white text-slate-600 hover:border-indigo-400'
              }`}
            >
              {day}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="mb-1.5 text-xs font-medium text-slate-500">Time</p>
        <DualRangeSlider
          min={CALENDAR_START_HOUR * 60}
          max={CALENDAR_END_HOUR * 60}
          step={5}
          values={filters.timeRange}
          onChange={(timeRange) => onChange({ ...filters, timeRange })}
          formatLabel={formatMinutesAsTime}
        />
      </div>
    </div>
  )
}
