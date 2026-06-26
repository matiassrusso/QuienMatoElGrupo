import type { MemberStats } from "../api"

interface Props {
  members: MemberStats[]
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("es-AR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function MembersTable({ members }: Props) {
  return (
    <div className="table-wrapper">
      <table className="members-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Nombre</th>
            <th>Mensajes en el periodo</th>
            <th>Ultimo mensaje</th>
            <th>Dias sin escribir</th>
            <th>Indice de inactividad</th>
          </tr>
        </thead>
        <tbody>
          {members.map((m, i) => (
            <tr key={m.author}>
              <td>{i + 1}</td>
              <td>{m.author}</td>
              <td>{m.messages_in_range}</td>
              <td>{formatDate(m.last_message_at)}</td>
              <td>{Math.floor(m.days_since_last_message)}</td>
              <td>{Math.round(m.inactivity_score * 100)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default MembersTable
