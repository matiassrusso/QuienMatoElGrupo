import type { AnalysisResult } from "../api"
import type { ToneMode } from "./ToneToggle"
import { formatMembersSentence } from "../utils/format"

interface Props {
  result: AnalysisResult
  tone: ToneMode
}

function getVitalStatus(result: AnalysisResult) {
  const silentShare = result.total_members === 0 ? 0 : result.members.filter((member) => member.messages_in_range === 0).length / result.total_members

  if (result.total_messages_in_range === 0) return "Muerto"
  if (silentShare > 0.6) return "Agonico"
  if (silentShare > 0.35) return "Fragil"
  return "Activo"
}

function getToneHeadline(tone: ToneMode, culprit: string) {
  if (tone === "bardero") return `${culprit} se borro cuando habia que bancar el grupo.`
  if (tone === "neutral") return `${culprit} aparece como el miembro con menor presencia reciente.`
  return `${culprit} figura como principal responsable del enfriamiento del grupo.`
}

function VerdictPanel({ result, tone }: Props) {
  const culprit = result.members[0]
  const topSpeaker = [...result.members].sort((a, b) => b.messages_in_range - a.messages_in_range)[0]
  const silentMembers = result.members.filter((member) => member.messages_in_range === 0).length
  const status = getVitalStatus(result)

  return (
    <section className="verdict-panel">
      <div className="verdict-main">
        <span className="section-kicker">Responsable principal</span>
        <h3>{culprit.author}</h3>
        <p className="verdict-copy">{getToneHeadline(tone, culprit.author)}</p>
        <p className="verdict-cause">{result.probable_cause}</p>
      </div>

      <div className="verdict-grid">
        <article className="summary-card">
          <span className="summary-label">Indice de inactividad</span>
          <strong>{Math.round(culprit.inactivity_score * 100)}%</strong>
          <p>{Math.floor(culprit.days_since_last_message)} dias sin escribir.</p>
        </article>

        <article className="summary-card">
          <span className="summary-label">Estado vital</span>
          <strong>{status}</strong>
          <p>
            {formatMembersSentence(silentMembers, result.total_members, {
              none: "Ninguno quedo en silencio dentro del periodo.",
              all: "Todos quedaron en silencio dentro del periodo.",
              some: (label) => `${label} miembros quedaron en silencio dentro del periodo.`,
            })}
          </p>
        </article>

        <article className="summary-card">
          <span className="summary-label">Patron</span>
          <strong>{result.conversation_pattern}</strong>
          <p>Lectura sintetica del comportamiento general del grupo.</p>
        </article>

        <article className="summary-card">
          <span className="summary-label">Sosten del grupo</span>
          <strong>{topSpeaker?.author ?? "Sin datos"}</strong>
          <p>{topSpeaker?.messages_in_range ?? 0} mensajes dentro del recorte.</p>
        </article>

        <article className="summary-card">
          <span className="summary-label">Volumen</span>
          <strong>{result.total_messages_in_range}</strong>
          <p>Mensajes reales procesados en la ventana elegida.</p>
        </article>

        <article className="summary-card">
          <span className="summary-label">Reactivaciones</span>
          <strong>{result.reactivation_attempts}</strong>
          <p>Intentos de recuperar movimiento despues de una caida o silencio.</p>
        </article>
      </div>
    </section>
  )
}

export default VerdictPanel
