import { useState } from "react"
import { CloneSessionExpiredError, enviarMensajeClon, iniciarClonChat, type CloneSession } from "../api"
import { loadAISettings, saveAISettings, type AIProvider, type AISettings } from "../aiSettings"

const PROVIDER_INFO: Record<AIProvider, { label: string; keyPlaceholder: string; modelPlaceholder: string }> = {
  anthropic: { label: "Anthropic (Claude)", keyPlaceholder: "sk-ant-...", modelPlaceholder: "claude-haiku-4-5-20251001" },
  openai: { label: "OpenAI (GPT)", keyPlaceholder: "sk-...", modelPlaceholder: "gpt-4o-mini" },
  gemini: { label: "Google Gemini (gratis)", keyPlaceholder: "AIza...", modelPlaceholder: "gemini-2.5-flash-lite" },
  groq: { label: "Groq (gratis)", keyPlaceholder: "gsk_...", modelPlaceholder: "llama-3.3-70b-versatile" },
}

interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

interface Props {
  file: File | null
}

// Mismos valores que backend/clone.py (SESSION_TTL_MINUTES, MAX_MESSAGES_PER_SESSION) -- solo para la copy del disclaimer.
const SESSION_TTL_MINUTES = 45
const MAX_MESSAGES_PER_SESSION = 30

function GroupClone({ file }: Props) {
  const [session, setSession] = useState<CloneSession | null>(null)
  const [starting, setStarting] = useState(false)
  const [mode, setMode] = useState<"general" | "member">("general")
  const [selectedMember, setSelectedMember] = useState<string | null>(null)

  const [settings, setSettings] = useState<AISettings | null>(() => loadAISettings())
  const [editingSettings, setEditingSettings] = useState(!settings)
  const [provider, setProvider] = useState<AIProvider>(settings?.provider ?? "anthropic")
  const [apiKey, setApiKey] = useState(settings?.apiKey ?? "")
  const [model, setModel] = useState(settings?.model ?? "")

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streamingText, setStreamingText] = useState<string | null>(null)
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionExpired, setSessionExpired] = useState(false)

  const handleStart = async () => {
    if (!file) return
    setStarting(true)
    setError(null)
    setSessionExpired(false)
    try {
      const nextSession = await iniciarClonChat(file)
      setSession(nextSession)
      setMessages([])
      setSelectedMember(nextSession.authors[0] ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar la sesion del clon.")
    } finally {
      setStarting(false)
    }
  }

  const handleExport = () => {
    const groupLabel = session?.group_name ?? "el grupo"
    const header = `Conversacion con el clon de "${groupLabel}" -- exportado el ${new Date().toLocaleString("es-AR")}\n\n`
    const body = messages.map((message) => `${message.role === "user" ? "Vos" : "Clon"}: ${message.content}`).join("\n\n")
    const blob = new Blob([header + body], { type: "text/plain;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const slug = groupLabel.replace(/[^a-z0-9]+/gi, "-").toLowerCase().replace(/(^-|-$)/g, "") || "grupo"
    const link = document.createElement("a")
    link.href = url
    link.download = `clon-${slug}.txt`
    link.click()
    URL.revokeObjectURL(url)
  }

  const handleSaveSettings = () => {
    if (!apiKey.trim()) return
    const nextSettings: AISettings = { provider, apiKey: apiKey.trim(), model: model.trim() || undefined }
    saveAISettings(nextSettings)
    setSettings(nextSettings)
    setEditingSettings(false)
  }

  const handleSend = async () => {
    if (!session || !settings || !input.trim() || sending) return
    const userText = input.trim()
    const hablarComo = mode === "member" ? selectedMember : null

    setMessages((prev) => [...prev, { role: "user", content: userText }])
    setInput("")
    setSending(true)
    setError(null)
    setStreamingText("")

    let acc = ""
    try {
      await enviarMensajeClon({ token: session.token, mensaje: userText, settings, hablarComo }, (chunk) => {
        acc += chunk
        setStreamingText(acc)
      })
      setMessages((prev) => [...prev, { role: "assistant", content: acc }])
      setStreamingText(null)
    } catch (err) {
      if (err instanceof CloneSessionExpiredError) {
        setSession(null)
        setSessionExpired(true)
        setStreamingText(null)
      } else {
        setError(err instanceof Error ? err.message : "Algo salio mal hablando con el clon.")
        setStreamingText(null)
      }
    } finally {
      setSending(false)
    }
  }

  if (!session) {
    return (
      <div className="group-clone">
        <p className="group-clone-disclaimer">
          Esta funcion es distinta al resto de la app: para que el clon suene como el grupo, tu chat se guarda
          temporalmente en la memoria del servidor (nunca en disco) por {SESSION_TTL_MINUTES} minutos y se borra
          automaticamente. A diferencia del resto del analisis, aca si se procesa el texto real de los mensajes.
        </p>
        {sessionExpired && <p className="group-clone-error">Tu sesion expiro. Volve a iniciar el clon para seguir charlando.</p>}
        {error && <p className="group-clone-error">{error}</p>}
        <button type="button" className="ai-verdict-btn" onClick={handleStart} disabled={!file || starting}>
          {starting ? "Iniciando..." : "Iniciar clon del grupo"}
        </button>
      </div>
    )
  }

  return (
    <div className="group-clone">
      <p className="group-clone-disclaimer">
        Tu chat esta en memoria del servidor por {SESSION_TTL_MINUTES} minutos y se borra solo. Limite de{" "}
        {MAX_MESSAGES_PER_SESSION} mensajes por sesion.
      </p>

      <div className="group-clone-mode">
        <label className="ai-verdict-field">
          <span>Como habla el clon</span>
          <select value={mode} onChange={(event) => setMode(event.target.value as "general" | "member")}>
            <option value="general">Tono general del grupo</option>
            <option value="member">Un miembro especifico</option>
          </select>
        </label>

        {mode === "member" && (
          <label className="ai-verdict-field">
            <span>Miembro</span>
            <select value={selectedMember ?? ""} onChange={(event) => setSelectedMember(event.target.value)}>
              {session.authors.map((author) => (
                <option key={author} value={author}>
                  {author}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {editingSettings || !settings ? (
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

          <button type="button" className="ai-verdict-btn" onClick={handleSaveSettings} disabled={!apiKey.trim()}>
            Guardar configuracion
          </button>
        </div>
      ) : (
        <button type="button" className="ai-verdict-link" onClick={() => setEditingSettings(true)}>
          Cambiar configuracion de IA
        </button>
      )}

      {messages.length > 0 && (
        <div className="group-clone-chat-toolbar">
          <button type="button" className="ai-verdict-link" onClick={handleExport}>
            Exportar conversacion
          </button>
        </div>
      )}

      <div className="group-clone-chat">
        {messages.length === 0 && streamingText === null && (
          <p className="group-clone-empty">Escribile algo al clon para arrancar la charla.</p>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`group-clone-bubble group-clone-bubble-${message.role}`}>
            <span className="group-clone-bubble-role">{message.role === "user" ? "Vos" : "Clon"}</span>
            <p>{message.content}</p>
          </div>
        ))}

        {streamingText !== null && (
          <div className="group-clone-bubble group-clone-bubble-assistant">
            <span className="group-clone-bubble-role">Clon</span>
            {streamingText === "" ? <p className="group-clone-typing">escribiendo…</p> : <p>{streamingText}</p>}
          </div>
        )}
      </div>

      {error && <p className="group-clone-error">{error}</p>}
      {sessionExpired && (
        <div className="group-clone-expired">
          <p className="group-clone-error">Tu sesion expiro. Volve a iniciar el clon para seguir charlando.</p>
          <button type="button" className="ai-verdict-btn" onClick={handleStart} disabled={!file || starting}>
            {starting ? "Iniciando..." : "Volver a iniciar el clon"}
          </button>
        </div>
      )}

      {!sessionExpired && (
        <div className="group-clone-input-row">
          <input
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault()
                void handleSend()
              }
            }}
            placeholder={settings ? "Escribile algo al clon..." : "Configura tu API key para poder charlar"}
            disabled={!settings || sending}
          />
          <button type="button" className="ai-verdict-btn" onClick={handleSend} disabled={!settings || !input.trim() || sending}>
            {sending ? "..." : "Enviar"}
          </button>
        </div>
      )}
    </div>
  )
}

export default GroupClone
