import { describe, expect, it } from "vitest"
import { capitalize, formatMemberCoverage, formatMembersSentence, formatWeekdayName } from "./format"

describe("formatWeekdayName", () => {
  it("returns the Spanish weekday name", () => {
    expect(formatWeekdayName(0)).toBe("Lunes")
    expect(formatWeekdayName(6)).toBe("Domingo")
  })

  it("falls back for an out-of-range index", () => {
    expect(formatWeekdayName(7)).toBe("Dia desconocido")
    expect(formatWeekdayName(-1)).toBe("Dia desconocido")
  })
})

describe("capitalize", () => {
  it("uppercases the first letter", () => {
    expect(capitalize("hola")).toBe("Hola")
  })

  it("returns empty string unchanged", () => {
    expect(capitalize("")).toBe("")
  })
})

describe("formatMemberCoverage", () => {
  it("returns 'ninguno' when count or total is zero", () => {
    expect(formatMemberCoverage(0, 5)).toBe("ninguno")
    expect(formatMemberCoverage(3, 0)).toBe("ninguno")
  })

  it("returns 'todos' when count covers the total", () => {
    expect(formatMemberCoverage(5, 5)).toBe("todos")
    expect(formatMemberCoverage(6, 5)).toBe("todos")
  })

  it("returns the partial coverage otherwise", () => {
    expect(formatMemberCoverage(2, 5)).toBe("2 de 5")
  })
})

describe("formatMembersSentence", () => {
  const copy = {
    none: "nadie escribio",
    all: "todos escribieron",
    some: (label: string) => `escribieron ${label}`,
  }

  it("uses the none copy", () => {
    expect(formatMembersSentence(0, 5, copy)).toBe("nadie escribio")
  })

  it("uses the all copy", () => {
    expect(formatMembersSentence(5, 5, copy)).toBe("todos escribieron")
  })

  it("uses the some copy with the coverage label", () => {
    expect(formatMembersSentence(2, 5, copy)).toBe("escribieron 2 de 5")
  })
})
