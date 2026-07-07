import { useEffect, useMemo, useRef, useState } from "react"

interface Props {
  text: string
  className?: string
}

/** Ilumina el texto palabra por palabra a medida que se scrollea sobre el. */
function WordReveal({ text, className }: Props) {
  const ref = useRef<HTMLParagraphElement>(null)
  const [litCount, setLitCount] = useState(0)
  const words = useMemo(() => text.split(" "), [text])

  useEffect(() => {
    const el = ref.current
    if (!el) return
    let raf = 0

    const update = () => {
      raf = 0
      const rect = el.getBoundingClientRect()
      const vh = window.innerHeight
      const progress = Math.min(1, Math.max(0, (vh * 0.85 - rect.top) / (rect.height + vh * 0.4)))
      setLitCount(Math.round(progress * words.length))
    }

    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update)
    }

    update()
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [words.length])

  return (
    <p ref={ref} className={className}>
      {words.map((word, i) => (
        <span key={i} className={i < litCount ? "word-lit" : "word-dim"}>
          {word}{" "}
        </span>
      ))}
    </p>
  )
}

export default WordReveal
