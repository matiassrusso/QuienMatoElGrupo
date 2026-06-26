export type ToneMode = "forense" | "neutral" | "bardero"

interface Props {
  tone: ToneMode
  onChange: (tone: ToneMode) => void
}

const OPTIONS: { value: ToneMode; label: string }[] = [
  { value: "forense", label: "Forense" },
  { value: "neutral", label: "Neutral" },
  { value: "bardero", label: "Bardo" },
]

function ToneToggle({ tone, onChange }: Props) {
  return (
    <div className="tone-toggle" role="group" aria-label="Tono de la experiencia">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`tone-btn ${tone === option.value ? "tone-btn-active" : ""}`}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export default ToneToggle
