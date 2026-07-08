import { Suspense, lazy, useEffect, useMemo, useState } from "react"
import { analizarChat, type AnalysisResult, type RangeType } from "./api"
import FileUploader from "./components/FileUploader"
import DateRangeSelector from "./components/DateRangeSelector"
import Podium from "./components/Podium"
import MembersTable from "./components/MembersTable"
import ToneToggle, { type ToneMode } from "./components/ToneToggle"
import VerdictPanel from "./components/VerdictPanel"
import AIVerdict from "./components/AIVerdict"
import InsightChips from "./components/InsightChips"
import DeathTimeline from "./components/DeathTimeline"
import MemberCompare from "./components/MemberCompare"
import ActivityHeatmap from "./components/ActivityHeatmap"
import AutopsyPanel from "./components/AutopsyPanel"
import PlaybackPanel from "./components/PlaybackPanel"
import ShareCard from "./components/ShareCard"
import SectionNav from "./components/SectionNav"
import CaseHero from "./components/CaseHero"
import GroupDynamics from "./components/GroupDynamics"
import RevealSection from "./components/RevealSection"
import { formatMembersSentence, formatShortDate, formatWeekdayName } from "./utils/format"
import "./App.css"

const ActivityChart = lazy(() => import("./components/ActivityChart"))
const ActivityHeatmap3D = lazy(() => import("./components/ActivityHeatmap3D"))

function getRangeLabel(rangeType: RangeType, rangeValue: number) {
  if (rangeType === "24h") return "Ultimas 24 horas"
  if (rangeType === "days") return `Ultimos ${rangeValue} dias`
  if (rangeType === "weeks") return `Ultimas ${rangeValue} semanas`
  return `Ultimos ${rangeValue} meses`
}

function getToneCopy(tone: ToneMode) {
  if (tone === "bardero") {
    return {
      eyebrow: "Peritaje con sana",
      subtitle: "Sube el export y descubre quien dejo de poner el cuerpo cuando el grupo se venia abajo.",
      verdictTitle: "Los principales responsables",
    }
  }

  if (tone === "neutral") {
    return {
      eyebrow: "Analisis de actividad",
      subtitle: "Carga el export de WhatsApp y revisa actividad, silencios y concentracion de mensajes del grupo.",
      verdictTitle: "Resumen principal",
    }
  }

  return {
    eyebrow: "Analisis forense de grupos",
    subtitle: "Carga el export de WhatsApp y mira, con datos, quien desaparecio, quien sostuvo la charla y como se degrado la actividad del grupo.",
    verdictTitle: "Veredicto del periodo",
  }
}

function buildInsights(result: AnalysisResult) {
  const total = result.total_messages_in_range || 1
  const silentMembers = result.members.filter((member) => member.messages_in_range === 0).length
  const topTwoMessages = result.members.slice().sort((a, b) => b.messages_in_range - a.messages_in_range).slice(0, 2)
  const topTwoShare = topTwoMessages.reduce((sum, member) => sum + member.messages_in_range, 0) / total
  const peakDay = result.activity_by_day.reduce((best, current) => (current.count > best.count ? current : best), result.activity_by_day[0])
  const hottestCell = result.hourly_heatmap.reduce((best, current) => (current.count > best.count ? current : best), result.hourly_heatmap[0])

  const insights = [
    formatMembersSentence(silentMembers, result.total_members, {
      none: "Ninguno dejo de escribir en la ventana analizada.",
      all: "Todos dejaron de escribir en la ventana analizada.",
      some: (label) => `${label} miembros dejaron de escribir en la ventana analizada.`,
    }),
    `${Math.round(topTwoShare * 100)}% de los mensajes estuvo concentrado en ${topTwoMessages.map((member) => member.author).join(" y ")}.`,
    `El pico de actividad fue el ${formatShortDate(peakDay.day)} con ${peakDay.count} mensajes.`,
  ]

  if (hottestCell.count > 0) {
    insights.push(
      `El grupo suele activarse mas los ${formatWeekdayName(hottestCell.weekday)} cerca de las ${String(hottestCell.hour).padStart(2, "0")}:00.`,
    )
  }

  return insights
}

function App() {
  const [file, setFile] = useState<File | null>(null)
  const [rangeType, setRangeType] = useState<RangeType>("days")
  const [rangeValue, setRangeValue] = useState(30)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [tone, setTone] = useState<ToneMode>("forense")
  const [activeSection, setActiveSection] = useState("veredicto")

  const pageTitle = result?.group_name ? `Quien Mato a ${result.group_name}` : "Quien Mato el Grupo"
  const toneCopy = getToneCopy(tone)

  useEffect(() => {
    document.title = pageTitle
  }, [pageTitle])

  const handleAnalyze = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const data = await analizarChat(file, rangeType, rangeType === "24h" ? null : rangeValue)
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Algo salio mal analizando el chat.")
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  const rangeLabel = getRangeLabel(rangeType, rangeValue)
  const insights = useMemo(() => (result ? buildInsights(result) : []), [result])
  const heroHighlights = result
    ? [
        { label: "Patron", value: result.conversation_pattern },
        { label: "Mensajes", value: String(result.total_messages_in_range) },
        { label: "Miembros", value: String(result.total_members) },
      ]
    : [
        { label: "Lectura", value: "Editorial" },
        { label: "Recorrido", value: "Timeline" },
        { label: "Detalle", value: "Heatmap" },
      ]

  useEffect(() => {
    if (!result) return

    const sectionIds = ["veredicto", "playback", "timeline", "comparacion", "detalle"]
    const sections = sectionIds
      .map((id) => document.getElementById(id))
      .filter((element): element is HTMLElement => element !== null)

    if (sections.length === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((left, right) => right.intersectionRatio - left.intersectionRatio)

        if (visible[0]?.target.id) {
          setActiveSection(visible[0].target.id)
        }
      },
      {
        rootMargin: "-18% 0px -58% 0px",
        threshold: [0.2, 0.35, 0.5, 0.75],
      },
    )

    sections.forEach((section) => observer.observe(section))
    return () => observer.disconnect()
  }, [result])

  if (!result) {
    return (
      <div className="app">
        <CaseHero
          pageTitle={pageTitle}
          eyebrow={toneCopy.eyebrow}
          subtitle={toneCopy.subtitle}
          tone={tone}
          onToneChange={setTone}
          file={file}
          onFileSelected={setFile}
          rangeType={rangeType}
          rangeValue={rangeValue}
          onRangeChange={(type, value) => {
            setRangeType(type)
            setRangeValue(value)
          }}
          onAnalyze={handleAnalyze}
          loading={loading}
          rangeLabel={rangeLabel}
        />
        {error && <p className="error-msg">{error}</p>}
      </div>
    )
  }

  return (
    <div className="app">
      <header className="hero">
        <div className="hero-copy">
          <span className="eyebrow">{toneCopy.eyebrow}</span>
          <h1>{pageTitle}</h1>
          <p className="app-subtitle">{toneCopy.subtitle}</p>

          <div className="hero-highlights" aria-label="Senales principales">
            {heroHighlights.map((item) => (
              <div key={item.label} className="hero-highlight">
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
        </div>

        <div className="hero-panel" aria-label="Resumen del analisis">
          <div className="hero-panel-head">
            <span className="section-kicker">Control de escena</span>
            <p>Elige el tono y define el recorte antes de abrir el expediente.</p>
          </div>
          <ToneToggle tone={tone} onChange={setTone} />
          <div className="hero-stat">
            <span className="hero-stat-label">Ventana</span>
            <strong>{rangeLabel}</strong>
          </div>
          <div className="hero-stat">
            <span className="hero-stat-label">Archivo</span>
            <strong>{file ? file.name : "Sin cargar"}</strong>
          </div>
          <div className="hero-stat">
            <span className="hero-stat-label">Privacidad</span>
            <strong>Analisis local en memoria</strong>
          </div>
        </div>
      </header>

      <main className="app-main">
        <section className="intake-panel">
          <div className="section-heading">
            <span className="section-kicker">Entrada</span>
            <h2>Configura el recorte y dispara el analisis</h2>
          </div>

          <div className="controls-grid">
            <FileUploader file={file} onFileSelected={setFile} />

            <div className="controls-side">
              <DateRangeSelector
                rangeType={rangeType}
                rangeValue={rangeValue}
                onChange={(type, value) => {
                  setRangeType(type)
                  setRangeValue(value)
                }}
              />
              <button className="analyze-btn" disabled={!file || loading} onClick={handleAnalyze}>
                {loading ? "Analizando chat..." : "Analizar chat"}
              </button>
            </div>
          </div>
        </section>

        {error && <p className="error-msg">{error}</p>}

        {result && (
          <section className="results">
            <SectionNav
              activeId={activeSection}
              items={[
                { id: "veredicto", label: "Veredicto" },
                { id: "playback", label: "Playback" },
                { id: "timeline", label: "Timeline" },
                { id: "comparacion", label: "Comparacion" },
                { id: "detalle", label: "Detalle" },
              ]}
            />

            <div className="results-top" id="veredicto">
              <div className="section-heading">
                <span className="section-kicker">Veredicto</span>
                <h2>{toneCopy.verdictTitle}</h2>
              </div>
              <p className="results-meta">
                Del {formatShortDate(result.range_start)} al {formatShortDate(result.range_end)}. {result.total_members}{" "}
                participantes y {result.total_messages_in_range} mensajes en el periodo.
              </p>
            </div>

            <VerdictPanel result={result} tone={tone} />
            <AIVerdict result={result} tone={tone} />
            <InsightChips insights={insights} />
            <GroupDynamics result={result} />

            <div className="results-grid two-column-grid">
              <RevealSection className="panel-section" id="playback">
                <div className="section-heading">
                  <span className="section-kicker">Playback</span>
                  <h2>Reproduccion del deterioro</h2>
                </div>
                <PlaybackPanel key={result.reference_date} snapshots={result.daily_snapshots} totalMembers={result.total_members} />
              </RevealSection>

              <RevealSection className="panel-section">
                <div className="section-heading">
                  <span className="section-kicker">Compartir</span>
                  <h2>Placa del veredicto</h2>
                </div>
                <ShareCard result={result} rangeLabel={rangeLabel} />
              </RevealSection>
            </div>

            <div className="results-grid">
              <RevealSection className="panel-section" id="timeline">
                <div className="section-heading">
                  <span className="section-kicker">Caso</span>
                  <h2>Cronologia del deterioro</h2>
                </div>
                <DeathTimeline events={result.timeline_events} />
              </RevealSection>

              <RevealSection className="panel-section">
                <div className="section-heading">
                  <span className="section-kicker">Patron</span>
                  <h2>Heatmap de actividad</h2>
                </div>
                <Suspense fallback={<ActivityHeatmap cells={result.hourly_heatmap} />}>
                  <ActivityHeatmap3D cells={result.hourly_heatmap} />
                </Suspense>
              </RevealSection>
            </div>

            <Podium top3={result.top3} />

            <div className="results-grid two-column-grid">
              <RevealSection className="panel-section" id="comparacion">
                <div className="section-heading">
                  <span className="section-kicker">Comparacion</span>
                  <h2>Miembro contra miembro</h2>
                </div>
                <MemberCompare members={result.members} />
              </RevealSection>

              <RevealSection className="panel-section">
                <div className="section-heading">
                  <span className="section-kicker">Metodologia</span>
                  <h2>Autopsia del calculo</h2>
                </div>
                <AutopsyPanel result={result} rangeLabel={rangeLabel} />
              </RevealSection>
            </div>

            <div className="results-grid two-column-grid">
              <RevealSection className="panel-section">
                <div className="section-heading">
                  <span className="section-kicker">Actividad</span>
                  <h2>Mensajes por persona</h2>
                </div>
                <Suspense fallback={<div className="chart-loading">Cargando grafico...</div>}>
                  <ActivityChart members={result.members} />
                </Suspense>
              </RevealSection>

              <RevealSection className="panel-section" id="detalle">
                <div className="section-heading">
                  <span className="section-kicker">Detalle</span>
                  <h2>Tabla completa de sospechosos</h2>
                </div>
                <MembersTable members={result.members} />
              </RevealSection>
            </div>
          </section>
        )}
      </main>

      <footer className="app-footer">
        <p>El archivo se procesa en memoria. No se persiste contenido del chat.</p>
      </footer>
    </div>
  )
}

export default App
