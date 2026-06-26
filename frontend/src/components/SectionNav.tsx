interface SectionItem {
  id: string
  label: string
}

interface Props {
  items: SectionItem[]
  activeId?: string
}

function SectionNav({ items, activeId }: Props) {
  return (
    <nav className="section-nav" aria-label="Navegacion del analisis">
      {items.map((item) => (
        <a
          key={item.id}
          className={`section-nav-link ${activeId === item.id ? "section-nav-link-active" : ""}`}
          href={`#${item.id}`}
        >
          {item.label}
        </a>
      ))}
    </nav>
  )
}

export default SectionNav
