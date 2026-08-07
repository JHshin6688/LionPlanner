import { Range, getTrackBackground } from 'react-range'

interface DualRangeSliderProps {
  min: number
  max: number
  step: number
  values: [number, number]
  onChange: (values: [number, number]) => void
  formatLabel?: (value: number) => string
}

export function DualRangeSlider({ min, max, step, values, onChange, formatLabel }: DualRangeSliderProps) {
  const format = formatLabel ?? ((v: number) => String(v))

  return (
    <div className="w-full px-1">
      <div className="mb-1.5 flex justify-between text-xs font-medium text-slate-600">
        <span>{format(values[0])}</span>
        <span>{format(values[1])}</span>
      </div>
      <Range
        min={min}
        max={max}
        step={step}
        values={values}
        onChange={(next) => onChange([next[0], next[1]])}
        renderTrack={({ props, children }) => (
          <div
            {...props}
            className="h-1.5 w-full rounded-full"
            style={{
              ...props.style,
              background: getTrackBackground({
                values,
                colors: ['#e2e8f0', '#4f46e5', '#e2e8f0'],
                min,
                max,
              }),
            }}
          >
            {children}
          </div>
        )}
        renderThumb={({ props }) => {
          const { key, ...thumbProps } = props as typeof props & { key?: string }
          return (
            <div
              key={key}
              {...thumbProps}
              className="h-4 w-4 rounded-full border-2 border-indigo-600 bg-white shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
            />
          )
        }}
      />
    </div>
  )
}
