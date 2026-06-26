import type { RangeType } from "../api"

interface Props {
  rangeType: RangeType
  rangeValue: number
  onChange: (rangeType: RangeType, rangeValue: number) => void
}

const OPTIONS: { type: RangeType; label: string; unit: string }[] = [
  { type: "24h", label: "Ultimas 24 horas", unit: "" },
  { type: "days", label: "Ultimos", unit: "dias" },
  { type: "weeks", label: "Ultimas", unit: "semanas" },
  { type: "months", label: "Ultimos", unit: "meses" },
]

function DateRangeSelector({ rangeType, rangeValue, onChange }: Props) {
  return (
    <div className="range-selector" role="group" aria-label="Rango de analisis">
      {OPTIONS.map((opt) => (
        <button
          type="button"
          key={opt.type}
          className={`range-btn ${rangeType === opt.type ? "range-btn-active" : ""}`}
          onClick={() => onChange(opt.type, rangeValue)}
        >
          {opt.type === "24h" ? (
            opt.label
          ) : (
            <>
              <span>{opt.label}</span>
              <span>
                {rangeType === opt.type ? (
                  <input
                    type="number"
                    min={1}
                    value={rangeValue}
                    aria-label={`Cantidad de ${opt.unit}`}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => onChange(opt.type, Math.max(1, Number(e.target.value) || 1))}
                    className="range-input"
                  />
                ) : (
                  rangeValue
                )}{" "}
                {opt.unit}
              </span>
            </>
          )}
        </button>
      ))}
    </div>
  )
}

export default DateRangeSelector
