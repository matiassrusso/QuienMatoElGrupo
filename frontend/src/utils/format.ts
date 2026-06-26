export const WEEKDAY_NAMES = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"] as const

export function formatShortDate(iso: string) {
  return new Date(iso).toLocaleDateString("es-AR")
}

export function formatWeekdayName(weekday: number) {
  return WEEKDAY_NAMES[weekday] ?? "Dia desconocido"
}

export function capitalize(value: string) {
  return value ? `${value[0].toUpperCase()}${value.slice(1)}` : value
}

export function formatMemberCoverage(count: number, total: number) {
  if (total <= 0 || count <= 0) return "ninguno"
  if (count >= total) return "todos"
  return `${count} de ${total}`
}

export function formatMembersSentence(
  count: number,
  total: number,
  copy: {
    none: string
    all: string
    some: (label: string) => string
  },
) {
  if (total <= 0 || count <= 0) {
    return copy.none
  }

  if (count >= total) {
    return copy.all
  }

  return copy.some(formatMemberCoverage(count, total))
}
