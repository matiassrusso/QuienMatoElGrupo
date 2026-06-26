function CaseIntro() {
  return (
    <section className="panel-section case-intro">
      <div className="section-heading">
        <span className="section-kicker">Antes de arrancar</span>
        <h2>Que te devuelve este analisis</h2>
      </div>

      <div className="intro-grid">
        <article className="intro-card">
          <strong>Veredicto</strong>
          <p>Quien aparece como principal responsable del enfriamiento y por que.</p>
        </article>
        <article className="intro-card">
          <strong>Playback</strong>
          <p>Como se movio el grupo dia por dia y cuando se empezo a caer.</p>
        </article>
        <article className="intro-card">
          <strong>Autopsia</strong>
          <p>Patron general, fases del periodo y posibles intentos de reactivacion.</p>
        </article>
      </div>
    </section>
  )
}

export default CaseIntro
