import { useMemo, useState } from "react"
import type { MemberStats } from "../api"

interface Props {
  members: MemberStats[]
}

function ComparisonCard({ label, valueA, valueB }: { label: string; valueA: string | number; valueB: string | number }) {
  return (
    <div className="comparison-row">
      <span>{label}</span>
      <strong>{valueA}</strong>
      <strong>{valueB}</strong>
    </div>
  )
}

function MemberCompare({ members }: Props) {
  const [left, setLeft] = useState(members[0]?.author ?? "")
  const [right, setRight] = useState(members[1]?.author ?? members[0]?.author ?? "")

  const selectedLeft = useMemo(() => members.find((member) => member.author === left) ?? members[0], [left, members])
  const selectedRight = useMemo(() => members.find((member) => member.author === right) ?? members[1] ?? members[0], [right, members])

  if (!selectedLeft || !selectedRight) return null

  return (
    <div className="compare-panel">
      <div className="compare-selectors">
        <label className="compare-select">
          <span>Miembro A</span>
          <select value={selectedLeft.author} onChange={(event) => setLeft(event.target.value)}>
            {members.map((member) => (
              <option key={member.author} value={member.author}>
                {member.author}
              </option>
            ))}
          </select>
        </label>

        <label className="compare-select">
          <span>Miembro B</span>
          <select value={selectedRight.author} onChange={(event) => setRight(event.target.value)}>
            {members.map((member) => (
              <option key={member.author} value={member.author}>
                {member.author}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="comparison-table">
        <div className="comparison-head">
          <strong>{selectedLeft.author}</strong>
          <strong>{selectedRight.author}</strong>
        </div>
        <ComparisonCard label="Mensajes" valueA={selectedLeft.messages_in_range} valueB={selectedRight.messages_in_range} />
        <ComparisonCard
          label="Inactividad"
          valueA={`${Math.round(selectedLeft.inactivity_score * 100)}%`}
          valueB={`${Math.round(selectedRight.inactivity_score * 100)}%`}
        />
        <ComparisonCard
          label="Dias sin escribir"
          valueA={Math.floor(selectedLeft.days_since_last_message)}
          valueB={Math.floor(selectedRight.days_since_last_message)}
        />
        <ComparisonCard
          label="Ultimo mensaje"
          valueA={new Date(selectedLeft.last_message_at).toLocaleDateString("es-AR")}
          valueB={new Date(selectedRight.last_message_at).toLocaleDateString("es-AR")}
        />
      </div>
    </div>
  )
}

export default MemberCompare
