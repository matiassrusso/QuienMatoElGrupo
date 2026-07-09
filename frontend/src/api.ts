import type { AISettings } from "./aiSettings"
import type { ToneMode } from "./components/ToneToggle"

const configuredApiUrl = import.meta.env.VITE_API_URL?.trim()

export const API_URL = configuredApiUrl ? configuredApiUrl.replace(/\/+$/, "") : "http://localhost:8000"

export type RangeType = "24h" | "days" | "weeks" | "months"

export interface MemberStats {
  author: string
  messages_in_range: number
  last_message_at: string
  days_since_last_message: number
  inactivity_score: number
}

export interface DailyActivity {
  day: string
  count: number
}

export interface DailySnapshot {
  day: string
  message_count: number
  active_members: number
  top_author: string | null
  top_author_messages: number
}

export interface HeatmapCell {
  weekday: number
  hour: number
  count: number
}

export interface TimelineEvent {
  kind: string
  at: string
  title: string
  description: string
}

export interface PhaseSummary {
  label: string
  start_day: string
  end_day: string
  description: string
}

export interface ReactivationLeader {
  author: string
  attempts: number
}

export interface InteractionEdge {
  source: string
  target: string
  weight: number
  avg_latency_seconds: number
}

export interface InteractionGraphData {
  nodes: string[]
  edges: InteractionEdge[]
  centrality: Record<string, number>
  communities: string[][]
}

export interface AnalysisResult {
  group_name: string | null
  reference_date: string
  range_start: string
  range_end: string
  total_members: number
  total_messages_in_range: number
  members: MemberStats[]
  top3: MemberStats[]
  activity_by_day: DailyActivity[]
  daily_snapshots: DailySnapshot[]
  hourly_heatmap: HeatmapCell[]
  timeline_events: TimelineEvent[]
  probable_cause: string
  conversation_pattern: string
  reactivation_attempts: number
  reactivation_leaders: ReactivationLeader[]
  phase_summary: PhaseSummary[]
  interaction_graph: InteractionGraphData
}

export async function analizarChat(
  file: File,
  rangeType: RangeType,
  rangeValue: number | null,
): Promise<AnalysisResult> {
  const formData = new FormData()
  formData.append("file", file)
  formData.append("range_type", rangeType)
  if (rangeValue !== null) {
    formData.append("range_value", String(rangeValue))
  }

  const res = await fetch(`${API_URL}/analizar`, {
    method: "POST",
    body: formData,
  })

  if (!res.ok) {
    const error = await res.json().catch(() => null)
    throw new Error(error?.detail ?? `Error ${res.status} al analizar el chat`)
  }

  return res.json()
}

export async function generarVeredictoIA(settings: AISettings, result: AnalysisResult, tone: ToneMode): Promise<string> {
  const res = await fetch(`${API_URL}/veredicto-ia`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider: settings.provider,
      api_key: settings.apiKey,
      model: settings.model || undefined,
      tone,
      group_name: result.group_name,
      total_members: result.total_members,
      total_messages_in_range: result.total_messages_in_range,
      conversation_pattern: result.conversation_pattern,
      reactivation_attempts: result.reactivation_attempts,
      top3: result.top3,
      reactivation_leaders: result.reactivation_leaders,
      phase_summary: result.phase_summary,
      rule_based_cause: result.probable_cause,
    }),
  })

  if (!res.ok) {
    const error = await res.json().catch(() => null)
    throw new Error(error?.detail ?? `Error ${res.status} al generar el veredicto con IA`)
  }

  const data = await res.json()
  return data.verdict as string
}
