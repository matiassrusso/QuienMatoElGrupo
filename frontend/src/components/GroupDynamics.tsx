import type { AnalysisResult } from "../api"

interface Props {
  result: AnalysisResult
}

function GroupDynamics({ result }: Props) {
  return (
    <section className="panel-section">
      <div className="section-heading">
        <span className="section-kicker">Dinamica</span>
        <h2>Patron del grupo</h2>
      </div>

      <div className="dynamics-grid">
        <article className="summary-card">
          <span className="summary-label">Patron dominante</span>
          <strong>{result.conversation_pattern}</strong>
          <p>Lectura global de como se comporto el grupo dentro del periodo.</p>
        </article>

        <article className="summary-card">
          <span className="summary-label">Reactivadores</span>
          <strong>{result.reactivation_leaders[0]?.author ?? "Sin lider claro"}</strong>
          <p>
            {result.reactivation_leaders.length > 0
              ? `${result.reactivation_leaders.map((leader) => `${leader.author} (${leader.attempts})`).join(", ")}`
              : "No hubo intentos claros de levantar la conversacion."}
          </p>
        </article>
      </div>
    </section>
  )
}

export default GroupDynamics
