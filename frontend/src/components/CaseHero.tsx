import type { RangeType } from "../api"
import type { ToneMode } from "./ToneToggle"
import FileUploader from "./FileUploader"
import DateRangeSelector from "./DateRangeSelector"
import ToneToggle from "./ToneToggle"
import WordReveal from "./WordReveal"

interface Props {
  pageTitle: string
  eyebrow: string
  subtitle: string
  tone: ToneMode
  onToneChange: (tone: ToneMode) => void
  file: File | null
  onFileSelected: (file: File) => void
  rangeType: RangeType
  rangeValue: number
  onRangeChange: (type: RangeType, value: number) => void
  onAnalyze: () => void
  loading: boolean
  rangeLabel: string
}

const TEASER =
  "Este expediente muestra quien aparece como principal responsable del enfriamiento y por que, como se movio el grupo dia por dia hasta que empezo a caer, y que patron general tuvo el periodo -- incluidos los intentos de reactivacion, si los hubo."

/** Landing previo al analisis: metafora de expediente de caso (pestanas, sello, tipografia monoespaciada). */
function CaseHero({ pageTitle, eyebrow, subtitle, tone, onToneChange, file, onFileSelected, rangeType, rangeValue, onRangeChange, onAnalyze, loading, rangeLabel }: Props) {
  return (
    <div className="case-hero">
      <aside className="case-hero-tabs">
        <div className="case-hero-tab case-hero-tab-active">Tono</div>
        <div className="case-hero-tab">Recorte</div>
        <div className="case-hero-tab">Evidencia</div>
      </aside>

      <div className="case-hero-page">
        <div className="case-hero-stamp">En investigacion</div>

        <span className="case-hero-case">EXP. N.o 004 — {eyebrow.toUpperCase()}</span>
        <h1 className="case-hero-title">{pageTitle}</h1>
        <p className="case-hero-subtitle">{subtitle}</p>

        <div className="case-hero-panel">
          <div className="case-hero-panel-row">
            <span>Tono del peritaje</span>
            <ToneToggle tone={tone} onChange={onToneChange} />
          </div>
          <div className="case-hero-panel-row">
            <span>Recorte temporal</span>
            <DateRangeSelector rangeType={rangeType} rangeValue={rangeValue} onChange={onRangeChange} />
          </div>
          <div className="case-hero-panel-row">
            <span>Evidencia (.zip)</span>
            <FileUploader file={file} onFileSelected={onFileSelected} />
          </div>

          <button className="case-hero-analyze" disabled={!file || loading} onClick={onAnalyze}>
            {loading ? "Procesando expediente..." : `Abrir expediente · ${rangeLabel}`}
          </button>
        </div>

        <div className="case-hero-divider" aria-hidden="true" />

        <span className="case-hero-case">QUE VAS A ENCONTRAR</span>
        <WordReveal text={TEASER} className="case-hero-teaser" />
      </div>
    </div>
  )
}

export default CaseHero
