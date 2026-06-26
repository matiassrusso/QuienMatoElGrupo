import { useEffect, useRef, useState, type ReactNode } from "react"

interface Props {
  id?: string
  className?: string
  children: ReactNode
}

function RevealSection({ id, className = "", children }: Props) {
  const ref = useRef<HTMLElement | null>(null)
  const [visible, setVisible] = useState(() => {
    if (typeof window === "undefined") return false
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches
  })

  useEffect(() => {
    const node = ref.current
    if (!node) return

    if (visible) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { threshold: 0.18, rootMargin: "0px 0px -10% 0px" },
    )

    observer.observe(node)
    return () => observer.disconnect()
  }, [visible])

  return (
    <section
      id={id}
      ref={ref}
      className={`reveal-section ${visible ? "reveal-section-visible" : ""} ${className}`.trim()}
    >
      {children}
    </section>
  )
}

export default RevealSection
