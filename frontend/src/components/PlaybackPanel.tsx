import { useEffect, useMemo, useState } from "react"
import type { DailySnapshot } from "../api"
import { capitalize, formatMemberCoverage, formatMembersSentence } from "../utils/format"

interface Props {
  snapshots: DailySnapshot[]
  totalMembers: number
}

function getPhase(snapshot: DailySnapshot) {
  if (snapshot.message_count === 0) return "Silencio"
  if (snapshot.message_count <= 5) return "Fragil"
  if (snapshot.message_count <= 15) return "Inestable"
  return "Activo"
}

function describeTransition(previous: DailySnapshot | undefined, current: DailySnapshot) {
  if (!previous) return "Primer punto del periodo analizado."

  const previousPhase = getPhase(previous)
  const currentPhase = getPhase(current)

  if (previousPhase !== currentPhase) {
    return `El grupo paso de ${previousPhase.toLowerCase()} a ${currentPhase.toLowerCase()}.`
  }

  if (current.message_count > previous.message_count) {
    return `Subio de ${previous.message_count} a ${current.message_count} mensajes frente al punto anterior.`
  }

  if (current.message_count < previous.message_count) {
    return `Cayo de ${previous.message_count} a ${current.message_count} mensajes frente al punto anterior.`
  }

  return "No hubo variacion de volumen frente al punto anterior."
}

const SPEEDS = [
  { value: 1250, label: "Lento" },
  { value: 850, label: "Normal" },
  { value: 500, label: "Rapido" },
]

function PlaybackPanel({ snapshots, totalMembers }: Props) {
  const [index, setIndex] = useState(() => snapshots.length - 1)
  const [isPlaying, setIsPlaying] = useState(false)
  const [speed, setSpeed] = useState(850)
  const snapshot = snapshots[index]
  const previousSnapshot = snapshots[index - 1]
  const maxMessages = useMemo(() => Math.max(...snapshots.map((item) => item.message_count), 1), [snapshots])

  useEffect(() => {
    if (!isPlaying || snapshots.length <= 1) return

    const timer = window.setInterval(() => {
      setIndex((current) => {
        if (current >= snapshots.length - 1) {
          setIsPlaying(false)
          return current
        }
        return current + 1
      })
    }, speed)

    return () => window.clearInterval(timer)
  }, [isPlaying, snapshots.length, speed])

  if (!snapshot) return null

  return (
    <div className="playback-panel">
      <div className="playback-head">
        <div>
          <span className="summary-label">Dia observado</span>
          <strong>{new Date(snapshot.day).toLocaleDateString("es-AR")}</strong>
        </div>
        <div>
          <span className="summary-label">Estado</span>
          <strong>{getPhase(snapshot)}</strong>
        </div>
      </div>

      <div className="playback-controls">
        <label className="playback-speed">
          <span>Velocidad</span>
          <select value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>
            {SPEEDS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="playback-control-btn"
          onClick={() => {
            setIsPlaying(false)
            setIndex(0)
          }}
        >
          Reiniciar
        </button>
        <button
          type="button"
          className="playback-control-btn playback-control-btn-primary"
          onClick={() => {
            if (index >= snapshots.length - 1) {
              setIndex(0)
            }
            setIsPlaying((current) => !current)
          }}
        >
          {isPlaying ? "Pausar" : "Reproducir"}
        </button>
        <span className="playback-position">
          {index + 1} / {snapshots.length}
        </span>
      </div>

      <p className="playback-note">{describeTransition(previousSnapshot, snapshot)}</p>

      <input
        className="playback-slider"
        type="range"
        min={0}
        max={Math.max(snapshots.length - 1, 0)}
        value={index}
        onChange={(event) => {
          setIsPlaying(false)
          setIndex(Number(event.target.value))
        }}
      />

      <div className="playback-track">
        {snapshots.map((item, itemIndex) => (
          <button
            key={item.day}
            type="button"
            className={`playback-bar ${itemIndex === index ? "playback-bar-active" : ""}`}
            style={{ height: `${Math.max(16, (item.message_count / maxMessages) * 100)}%` }}
            title={`${new Date(item.day).toLocaleDateString("es-AR")}: ${item.message_count} mensajes`}
            onClick={() => {
              setIsPlaying(false)
              setIndex(itemIndex)
            }}
          />
        ))}
      </div>

      <div className="playback-grid">
        <article className="summary-card">
          <span className="summary-label">Mensajes</span>
          <strong>{snapshot.message_count}</strong>
          <p>Volumen total detectado ese dia.</p>
        </article>
        <article className="summary-card">
          <span className="summary-label">Miembros activos</span>
          <strong>{capitalize(formatMemberCoverage(snapshot.active_members, totalMembers))}</strong>
          <p>
            {formatMembersSentence(snapshot.active_members, totalMembers, {
              none: "Ninguno participo al menos una vez en esa fecha.",
              all: "Todos participaron al menos una vez en esa fecha.",
              some: (label) => `${label} miembros participaron al menos una vez en esa fecha.`,
            })}
          </p>
        </article>
        <article className="summary-card">
          <span className="summary-label">Figura dominante</span>
          <strong>{snapshot.top_author ?? "Nadie"}</strong>
          <p>
            {snapshot.top_author ? `${snapshot.top_author_messages} mensajes en el dia.` : "No hubo mensajes en ese punto del playback."}
          </p>
        </article>
      </div>
    </div>
  )
}

export default PlaybackPanel
