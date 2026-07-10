export type AIProvider = "anthropic" | "openai" | "gemini" | "groq" | "nvidia"

export interface AISettings {
  provider: AIProvider
  apiKey: string
  model?: string
}

const STORAGE_KEY = "qmeg_ai_settings"

export function loadAISettings(): AISettings | null {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return null

  try {
    return JSON.parse(raw) as AISettings
  } catch {
    return null
  }
}

export function saveAISettings(settings: AISettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
}

export function clearAISettings() {
  localStorage.removeItem(STORAGE_KEY)
}
