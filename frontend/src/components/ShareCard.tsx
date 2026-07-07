import { useMemo, useState } from "react"
import type { AnalysisResult } from "../api"

interface Props {
  result: AnalysisResult
  rangeLabel: string
}

async function copyToClipboard(text: string) {
  await navigator.clipboard.writeText(text)
}

function escapeXml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;")
}

function wrapText(value: string, maxChars: number) {
  const words = value.split(/\s+/)
  const lines: string[] = []
  let current = ""

  for (const word of words) {
    const next = current ? `${current} ${word}` : word
    if (next.length > maxChars && current) {
      lines.push(current)
      current = word
    } else {
      current = next
    }
  }

  if (current) lines.push(current)
  return lines
}

function downloadSvg(filename: string, content: string) {
  const blob = new Blob([content], { type: "image/svg+xml;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

async function downloadPng(filename: string, content: string) {
  const blob = new Blob([content], { type: "image/svg+xml;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const image = new Image()

  await new Promise<void>((resolve, reject) => {
    image.onload = () => resolve()
    image.onerror = () => reject(new Error("No se pudo renderizar la placa"))
    image.src = url
  })

  const canvas = document.createElement("canvas")
  canvas.width = 1200
  canvas.height = 628
  const context = canvas.getContext("2d")
  if (!context) {
    URL.revokeObjectURL(url)
    throw new Error("No se pudo crear el canvas para exportar")
  }

  context.drawImage(image, 0, 0)
  URL.revokeObjectURL(url)

  const pngUrl = canvas.toDataURL("image/png")
  const link = document.createElement("a")
  link.href = pngUrl
  link.download = filename
  link.click()
}

function buildShareSvg(result: AnalysisResult, rangeLabel: string) {
  const culprit = result.members[0]
  const score = Math.round(culprit.inactivity_score * 100)
  const safeGroupName = escapeXml(result.group_name ?? "Grupo sin nombre")
  const safeCulprit = escapeXml(culprit.author)
  const safePattern = escapeXml(result.conversation_pattern)
  const safeCauseLines = wrapText(result.probable_cause, 52).slice(0, 3).map(escapeXml)
  const lastMessage = new Date(culprit.last_message_at).toLocaleDateString("es-AR")
  const reactivators =
    result.reactivation_leaders.length > 0
      ? result.reactivation_leaders.map((leader) => `${leader.author} (${leader.attempts})`).join(", ")
      : "Sin reactivadores claros"
  const safeReactivators = escapeXml(reactivators)
  const safeRangeLabel = escapeXml(rangeLabel)

  const causeText = safeCauseLines
    .map((line, index) => `<text x="670" y="${434 + index * 28}" fill="#c9c0b3" font-family="Georgia, 'Times New Roman', serif" font-size="22">${line}</text>`)
    .join("")

  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="628" viewBox="0 0 1200 628" fill="none">
  <rect width="1200" height="628" rx="6" fill="#151312"/>
  <rect x="24" y="24" width="1152" height="580" rx="4" fill="#1c1815" stroke="rgba(216,210,200,0.12)"/>
  <rect x="56" y="56" width="474" height="516" rx="4" fill="#201b17" stroke="rgba(154,44,44,0.35)"/>
  <rect x="562" y="56" width="582" height="244" rx="4" fill="#201b17" stroke="rgba(216,210,200,0.12)"/>
  <rect x="562" y="324" width="582" height="248" rx="4" fill="#201b17" stroke="rgba(216,210,200,0.12)"/>
  <text x="88" y="102" fill="#c23a3a" font-family="Space Mono, monospace" font-size="22" letter-spacing="2">QUIEN MATO EL GRUPO</text>
  <text x="88" y="158" fill="#f1ede4" font-family="Georgia, 'Times New Roman', serif" font-size="48" font-weight="700">${safeGroupName}</text>
  <text x="88" y="204" fill="#a29c92" font-family="Arial, Helvetica, sans-serif" font-size="24">Veredicto generado para ${safeRangeLabel.toLowerCase()}</text>
  <text x="88" y="294" fill="#f1ede4" font-family="Georgia, 'Times New Roman', serif" font-size="66" font-weight="700">${safeCulprit}</text>
  <text x="88" y="334" fill="#c23a3a" font-family="Arial, Helvetica, sans-serif" font-size="22">Responsable principal detectado</text>
  <rect x="88" y="382" width="170" height="112" rx="3" fill="#1c1815" stroke="rgba(154,44,44,0.4)"/>
  <text x="112" y="420" fill="#c23a3a" font-family="Space Mono, monospace" font-size="18">INACTIVIDAD</text>
  <text x="112" y="468" fill="#f1ede4" font-family="Georgia, 'Times New Roman', serif" font-size="46" font-weight="700">${score}%</text>
  <rect x="278" y="382" width="220" height="112" rx="3" fill="#1c1815" stroke="rgba(216,210,200,0.12)"/>
  <text x="302" y="420" fill="#c23a3a" font-family="Space Mono, monospace" font-size="18">DIAS SIN ESCRIBIR</text>
  <text x="302" y="468" fill="#f1ede4" font-family="Georgia, 'Times New Roman', serif" font-size="46" font-weight="700">${Math.floor(culprit.days_since_last_message)}</text>
  <text x="88" y="530" fill="#a29c92" font-family="Arial, Helvetica, sans-serif" font-size="20">Ultimo mensaje: ${escapeXml(lastMessage)}</text>

  <text x="594" y="104" fill="#c23a3a" font-family="Space Mono, monospace" font-size="20">LECTURA DEL CASO</text>
  <text x="594" y="154" fill="#f1ede4" font-family="Georgia, 'Times New Roman', serif" font-size="28" font-weight="700">Patron: ${safePattern}</text>
  <text x="594" y="208" fill="#c9c0b3" font-family="Arial, Helvetica, sans-serif" font-size="24">Miembros analizados: ${result.total_members}</text>
  <text x="594" y="244" fill="#c9c0b3" font-family="Arial, Helvetica, sans-serif" font-size="24">Mensajes en periodo: ${result.total_messages_in_range}</text>
  <text x="594" y="280" fill="#c9c0b3" font-family="Arial, Helvetica, sans-serif" font-size="24">Reactivaciones: ${result.reactivation_attempts}</text>

  <text x="594" y="372" fill="#c23a3a" font-family="Space Mono, monospace" font-size="20">CAUSA PROBABLE</text>
  ${causeText}
  <text x="594" y="524" fill="#c23a3a" font-family="Space Mono, monospace" font-size="18">REACTIVADORES</text>
  <text x="594" y="554" fill="#c9c0b3" font-family="Arial, Helvetica, sans-serif" font-size="20">${safeReactivators}</text>
  <text x="88" y="606" fill="#6b6660" font-family="Arial, Helvetica, sans-serif" font-size="18">Generado por Quien Mato el Grupo</text>
</svg>`
}

function ShareCard({ result, rangeLabel }: Props) {
  const [copied, setCopied] = useState(false)
  const [downloadedSvg, setDownloadedSvg] = useState(false)
  const [downloadedPng, setDownloadedPng] = useState(false)
  const culprit = result.members[0]
  const score = Math.round(culprit.inactivity_score * 100)
  const groupName = result.group_name ?? "Grupo sin nombre"
  const summary = `${groupName}: ${culprit.author} aparece como principal responsable. ${score}% de inactividad, ${Math.floor(
    culprit.days_since_last_message,
  )} dias sin escribir, patron ${result.conversation_pattern.toLowerCase()} y ${result.reactivation_attempts} reactivaciones detectadas.`
  const leadersText = useMemo(
    () =>
      result.reactivation_leaders.length > 0
        ? result.reactivation_leaders.map((leader) => `${leader.author} (${leader.attempts})`).join(", ")
        : "Sin reactivadores claros",
    [result.reactivation_leaders],
  )

  return (
    <div className="share-card">
      <div className="share-card-art share-card-art-rich">
        <span className="share-card-kicker">Quien Mato el Grupo</span>
        <strong>{groupName}</strong>
        <p>{culprit.author} encabeza el ranking de abandono.</p>
      </div>

      <div className="share-card-stats share-card-stats-rich">
        <div>
          <span className="summary-label">Responsable</span>
          <strong>{culprit.author}</strong>
        </div>
        <div>
          <span className="summary-label">Indice</span>
          <strong>{score}%</strong>
        </div>
        <div>
          <span className="summary-label">Dias fuera</span>
          <strong>{Math.floor(culprit.days_since_last_message)}</strong>
        </div>
        <div>
          <span className="summary-label">Patron</span>
          <strong>{result.conversation_pattern}</strong>
        </div>
      </div>

      <div className="share-card-details">
        <p className="share-card-copy">{summary}</p>
        <p className="share-card-meta">
          Ultimo mensaje: {new Date(culprit.last_message_at).toLocaleDateString("es-AR")} · Reactivadores: {leadersText}
        </p>
        <p className="share-card-cause">{result.probable_cause}</p>
      </div>

      <div className="share-card-actions">
        <button
          type="button"
          className="share-btn"
          onClick={async () => {
            await copyToClipboard(summary)
            setCopied(true)
            window.setTimeout(() => setCopied(false), 1800)
          }}
        >
          {copied ? "Texto copiado" : "Copiar veredicto"}
        </button>

        <button
          type="button"
          className="share-btn share-btn-secondary"
          onClick={() => {
            const svg = buildShareSvg(result, rangeLabel)
            downloadSvg("veredicto-grupo.svg", svg)
            setDownloadedSvg(true)
            window.setTimeout(() => setDownloadedSvg(false), 1800)
          }}
        >
          {downloadedSvg ? "SVG descargado" : "Descargar SVG"}
        </button>

        <button
          type="button"
          className="share-btn share-btn-secondary"
          onClick={async () => {
            const svg = buildShareSvg(result, rangeLabel)
            await downloadPng("veredicto-grupo.png", svg)
            setDownloadedPng(true)
            window.setTimeout(() => setDownloadedPng(false), 1800)
          }}
        >
          {downloadedPng ? "PNG descargado" : "Descargar PNG"}
        </button>
      </div>
    </div>
  )
}

export default ShareCard
