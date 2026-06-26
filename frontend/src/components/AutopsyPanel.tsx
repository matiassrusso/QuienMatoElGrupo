import type { AnalysisResult } from "../api"

interface Props {
  result: AnalysisResult
  rangeLabel: string
}

function AutopsyPanel({ result, rangeLabel }: Props) {
  return (
    <div className="autopsy-panel">
      <details open>
        <summary>Causa probable</summary>
        <p>{result.probable_cause}</p>
      </details>
      <details open>
        <summary>Como se calcula el ranking</summary>
        <p>El score mezcla recencia y volumen: cuanto menos escribio alguien y hace mas tiempo que no aparece, mas sube.</p>
      </details>
      <details>
        <summary>Ventana usada</summary>
        <p>{rangeLabel}. Se tomo como fecha de referencia el ultimo mensaje real detectado en el export.</p>
      </details>
      <details>
        <summary>Patron detectado</summary>
        <p>{result.conversation_pattern}. Reactivadores detectados: {result.reactivation_leaders.map((leader) => `${leader.author} (${leader.attempts})`).join(", ") || "ninguno"}.</p>
      </details>
      <details>
        <summary>Que entra y que no entra</summary>
        <p>Se filtran mensajes del sistema y bots. Solo cuentan mensajes reales atribuidos a personas.</p>
      </details>
      <details>
        <summary>Limitaciones</summary>
        <p>Este analisis no interpreta contexto, ironia ni calidad de los mensajes. Solo actividad observable.</p>
      </details>
      <div className="phase-list">
        {result.phase_summary.map((phase) => (
          <article key={`${phase.label}-${phase.start_day}`} className="phase-card">
            <span className="summary-label">{phase.label}</span>
            <strong>
              {new Date(phase.start_day).toLocaleDateString("es-AR")} - {new Date(phase.end_day).toLocaleDateString("es-AR")}
            </strong>
            <p>{phase.description}</p>
          </article>
        ))}
      </div>
      <p className="autopsy-footnote">
        Miembros evaluados: {result.total_members}. Mensajes reales en periodo: {result.total_messages_in_range}. Reactivaciones detectadas:{" "}
        {result.reactivation_attempts}.
      </p>
    </div>
  )
}

export default AutopsyPanel
