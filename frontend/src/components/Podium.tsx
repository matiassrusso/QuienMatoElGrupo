import type { MemberStats } from "../api"

interface Props {
  top3: MemberStats[]
}

const RANKS = ["01", "02", "03"]
const TITLES = ["Responsable principal", "Complice necesario", "Sospechoso de interes"]

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("es-AR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })
}

function Podium({ top3 }: Props) {
  if (top3.length === 0) return null

  return (
    <div className="podium">
      {top3.map((m, i) => (
        <div key={m.author} className={`podium-card podium-card-${i + 1}`}>
          <div className="podium-medal">{RANKS[i]}</div>
          <div className="podium-title">{TITLES[i]}</div>
          <div className="podium-name">{m.author}</div>
          <div className="podium-stats">
            <span>{m.messages_in_range} mensajes en el periodo</span>
            <span>Ultimo mensaje: {formatDate(m.last_message_at)}</span>
            <span className="podium-score">Indice de inactividad: {Math.round(m.inactivity_score * 100)}%</span>
          </div>
        </div>
      ))}
    </div>
  )
}

export default Podium
