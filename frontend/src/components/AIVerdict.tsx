import { useState } from "react"
import type { AnalysisResult } from "../api"
import { generarVeredictoIA } from "../api"
import { loadAISettings, saveAISettings, type AIProvider, type AISettings } from "../aiSettings"
import type { ToneMode } from "./ToneToggle"

const PROVIDER_INFO: Record<AIProvider, { label: string; keyPlaceholder: string; modelPlaceholder: string }> = {
  anthropic: { label: "Anthropic (Claude)", keyPlaceholder: "sk-ant-...", modelPlaceholder: "claude-haiku-4-5-20251001" },
  openai: { label: "OpenAI (GPT)", keyPlaceholder: "sk-...", modelPlaceholder: "gpt-4o-mini" },
  gemini: { label: "Google Gemini (gratis)", keyPlaceholder: "AIza...", modelPlaceholder: "gemini-2.5-flash-lite" },
  groq: { label: "Groq (gratis)", keyPlaceholder: "gsk_...", modelPlaceholder: "llama-3.3-70b-versatile" },
}

interface Props {
  result: AnalysisResult
  tone: ToneMode
}

function AIVerdict({ result, tone }: Props) {
  const [settings, setSettings] = useState<AISettings | null>(() => loadAISettings())
  const [editing, setEditing] = useState(!settings)
  const [provider, setProvider] = useState<AIProvider>(settings?.provider ?? "anthropic")
  const [apiKey, setApiKey] = useState(settings?.apiKey ?? "")
  const [model, setModel] = useState(settings?.model ?? "")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [verdict, setVerdict] = useState<string | null>(null)

  const handleSaveAndGenerate = async () => {
    if (!apiKey.trim()) return

    const nextSettings: AISettings = { provider, apiKey: apiKey.trim(), model: model.trim() || undefined }
    saveAISettings(nextSettings)
    setSettings(nextSettings)
    setEditing(false)

    await generate(nextSettings)
  }

  const generate = async (activeSettings: AISettings) => {
    setLoading(true)
    setError(null)
    try {
      const text = await generarVeredictoIA(activeSettings, result, tone)
      setVerdict(text)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Algo salio mal generando el veredicto con IA.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="ai-verdict">
      <span className="section-kicker">Veredicto con IA</span>
      <h3>Redaccion asistida</h3>

      {editing || !settings ? (
        <div className="ai-verdict-form">
          <p className="ai-verdict-disclaimer">
            Tu API key se guarda solo en este navegador (localStorage) y se envia a nuestro backend unicamente para
            reenviarla directo a tu proveedor de IA en el momento del pedido. Nunca la guardamos en el servidor.
          </p>

          <label className="ai-verdict-field">
            <span>Proveedor</span>
            <select value={provider} onChange={(event) => setProvider(event.target.value as AIProvider)}>
              {Object.entries(PROVIDER_INFO).map(([value, info]) => (
                <option key={value} value={value}>
                  {info.label}
                </option>
              ))}
            </select>
          </label>

          <label className="ai-verdict-field">
            <span>API key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={PROVIDER_INFO[provider].keyPlaceholder}
              autoComplete="off"
            />
          </label>

          <label className="ai-verdict-field">
            <span>Modelo (opcional)</span>
            <input
              type="text"
              value={model}
              onChange={(event) => setModel(event.target.value)}
              placeholder={PROVIDER_INFO[provider].modelPlaceholder}
              autoComplete="off"
            />
          </label>

          <button type="button" className="ai-verdict-btn" onClick={handleSaveAndGenerate} disabled={!apiKey.trim() || loading}>
            {loading ? "Generando..." : "Guardar y generar veredicto"}
          </button>
        </div>
      ) : (
        <div className="ai-verdict-actions">
          <button type="button" className="ai-verdict-btn" onClick={() => generate(settings)} disabled={loading}>
            {loading ? "Generando..." : "Generar veredicto con IA"}
          </button>
          <button type="button" className="ai-verdict-link" onClick={() => setEditing(true)}>
            Cambiar configuracion
          </button>
        </div>
      )}

      {error && <p className="ai-verdict-error">{error}</p>}
      {verdict && !error && <p className="ai-verdict-result">{verdict}</p>}
    </section>
  )
}

export default AIVerdict
