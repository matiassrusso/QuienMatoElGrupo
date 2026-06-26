interface Props {
  insights: string[]
}

function InsightChips({ insights }: Props) {
  return (
    <section className="panel-section">
      <div className="section-heading">
        <span className="section-kicker">Hallazgos</span>
        <h2>Lecturas rapidas del caso</h2>
      </div>
      <div className="insight-grid">
        {insights.map((insight) => (
          <article key={insight} className="insight-chip">
            <p>{insight}</p>
          </article>
        ))}
      </div>
    </section>
  )
}

export default InsightChips
