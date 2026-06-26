import type { HeatmapCell } from "../api"
import { formatWeekdayName } from "../utils/format"

interface Props {
  cells: HeatmapCell[]
}

const HOUR_MARKS = [0, 6, 12, 18, 23]

function ActivityHeatmap({ cells }: Props) {
  const maxCount = Math.max(...cells.map((cell) => cell.count), 0)

  return (
    <div className="heatmap">
      <div className="heatmap-header">
        <span className="heatmap-axis-label">Hora</span>
        <div className="heatmap-hour-scale">
          {HOUR_MARKS.map((hour) => (
            <span key={hour} className="heatmap-hour">
              {String(hour).padStart(2, "0")}
            </span>
          ))}
        </div>
      </div>

      {Array.from({ length: 7 }, (_, weekday) => {
        const day = formatWeekdayName(weekday)

        return (
          <div key={day} className="heatmap-row">
            <span key={`label-${day}`} className="heatmap-day">
              {day}
            </span>
            {Array.from({ length: 24 }, (_, hour) => {
              const cell = cells.find((item) => item.weekday === weekday && item.hour === hour)
              const intensity = !cell || maxCount === 0 ? 0 : cell.count / maxCount

              return (
                <span
                  key={`${weekday}-${hour}`}
                  className="heatmap-cell"
                  title={`${day} ${String(hour).padStart(2, "0")}:00 - ${cell?.count ?? 0} mensajes`}
                  style={{
                    background: `rgba(246, 160, 93, ${0.12 + intensity * 0.88})`,
                    borderColor: intensity > 0 ? "rgba(246, 160, 93, 0.42)" : "rgba(255,255,255,0.08)",
                  }}
                />
              )
            })}
          </div>
        )
      })}

      <div className="heatmap-legend">
        <span className="heatmap-legend-label">Intensidad</span>
        <div className="heatmap-legend-scale">
          <span className="heatmap-legend-cell heatmap-legend-cell-low" />
          <span className="heatmap-legend-cell heatmap-legend-cell-mid" />
          <span className="heatmap-legend-cell heatmap-legend-cell-high" />
        </div>
        <span className="heatmap-legend-label">de baja a alta</span>
      </div>
    </div>
  )
}

export default ActivityHeatmap
