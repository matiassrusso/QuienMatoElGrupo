import type { TimelineEvent } from "../api"

interface Props {
  events: TimelineEvent[]
}

function DeathTimeline({ events }: Props) {
  return (
    <ol className="timeline">
      {events.map((event) => (
        <li key={`${event.kind}-${event.at}`} className="timeline-item">
          <span className="timeline-date">{new Date(event.at).toLocaleDateString("es-AR")}</span>
          <div className="timeline-content">
            <strong>{event.title}</strong>
            <p>{event.description}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}

export default DeathTimeline
