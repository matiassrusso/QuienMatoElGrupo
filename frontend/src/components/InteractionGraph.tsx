import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react"
import type { InteractionGraphData } from "../api"

interface Props {
  graph: InteractionGraphData
}

interface Point {
  x: number
  y: number
}

interface SimNode extends Point {
  vx: number
  vy: number
}

const BASE_WIDTH = 640
const MARGIN = 56

// Fisica compartida entre el asentado inicial (layoutNodes) y el arrastre en
// vivo (liveStep). Mismas constantes y mismo modelo (gravedad hacia el centro
// de cada comunidad) para que la posicion asentada sea un equilibrio real: al
// soltar un nodo, la fuerza lo devuelve exacto a su lugar, sin salto al empezar
// a arrastrar ni reorganizacion del grafo en el primer gesto.
const REPULSION = 2600
const GRAVITY = 0.012
const EDGE_STRENGTH = 0.018

function canvasSize(nodeCount: number) {
  // Con pocos nodos el tamaño base alcanza; con un grupo grande (10+
  // personas) el layout necesita mas aire o las lineas se amontonan sin
  // importar cuanto se pode -- se descubrio con un grupo real de 13
  // personas, donde el tamaño fijo de antes daba una marana ilegible.
  const width = Math.min(1100, Math.max(BASE_WIDTH, nodeCount * 68))
  return { width, height: Math.round(width * 0.62) }
}

function springLengthFor(width: number, height: number, communityCount: number) {
  return Math.min(width, height) * (communityCount > 1 ? 0.22 : 0.3)
}

function clamp(value: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, value))
}

// Cada comunidad detectada tiene su propio centro de gravedad, repartidos en un
// circulo grande -- sin esto, todos los nodos convergen al mismo centro y las
// comunidades quedan superpuestas aunque esten bien separadas en los datos (el
// layout no "sabe" que existen). Deterministico, asi el asentado y el arrastre
// en vivo comparten exactamente los mismos centros.
function buildCommunityCenters(communities: string[][], width: number, height: number) {
  const communityOf = new Map<string, number>()
  communities.forEach((community, index) => {
    community.forEach((author) => communityOf.set(author, index))
  })
  const count = Math.max(communities.length, 1)
  const spread = count > 1 ? Math.min(width, height) * 0.3 : 0
  const centers = Array.from({ length: count }, (_, index) => {
    const angle = (2 * Math.PI * index) / count
    return { x: width / 2 + spread * Math.cos(angle), y: height / 2 + spread * Math.sin(angle) }
  })
  return { centers, communityOf }
}

// Layout congelado (ver DESIGN.md: nada de simulacion de fuerza en vivo por
// defecto). Simulacion tipo Fruchterman-Reingold en JS puro, sincronica; se
// descartan las velocidades y quedan las posiciones asentadas. NO se
// re-normaliza al final: el resultado es un equilibrio real del mismo modelo de
// fuerzas que usa el arrastre en vivo, asi soltar un nodo lo devuelve exacto a
// su lugar. Se acota con clamp al canvas en vez de re-escalar. No hace falta
// d3-force: son ~40 lineas de repulsion + resorte.
function layoutNodes(
  nodes: string[],
  edges: InteractionGraphData["edges"],
  communities: string[][],
  width: number,
  height: number,
): Map<string, Point> {
  const n = nodes.length
  if (n === 0) return new Map()
  if (n === 1) return new Map([[nodes[0], { x: width / 2, y: height / 2 }]])

  const { centers, communityOf } = buildCommunityCenters(communities, width, height)
  const centerFor = (id: string) => centers[communityOf.get(id) ?? 0]

  const positions = new Map<string, SimNode>()
  const startRadius = Math.min(width, height) * 0.14
  nodes.forEach((id, i) => {
    const center = centerFor(id)
    const angle = (2 * Math.PI * i) / n
    positions.set(id, {
      x: center.x + startRadius * Math.cos(angle),
      y: center.y + startRadius * Math.sin(angle),
      vx: 0,
      vy: 0,
    })
  })

  const maxWeight = Math.max(...edges.map((edge) => edge.weight), 1)
  const springLength = springLengthFor(width, height, centers.length)

  for (let iteration = 0; iteration < 280; iteration++) {
    for (const id of nodes) {
      const node = positions.get(id)!
      const center = centerFor(id)
      let fx = (center.x - node.x) * GRAVITY
      let fy = (center.y - node.y) * GRAVITY

      for (const otherId of nodes) {
        if (otherId === id) continue
        const other = positions.get(otherId)!
        const dx = node.x - other.x
        const dy = node.y - other.y
        const distSq = Math.max(dx * dx + dy * dy, 1)
        const dist = Math.sqrt(distSq)
        const force = REPULSION / distSq
        fx += (dx / dist) * force
        fy += (dy / dist) * force
      }

      node.vx = (node.vx + fx) * 0.82
      node.vy = (node.vy + fy) * 0.82
    }

    for (const edge of edges) {
      const source = positions.get(edge.source)
      const target = positions.get(edge.target)
      if (!source || !target) continue
      const dx = target.x - source.x
      const dy = target.y - source.y
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
      const strength = EDGE_STRENGTH * (0.4 + 0.6 * (edge.weight / maxWeight))
      const displacement = (dist - springLength) * strength
      const ux = dx / dist
      const uy = dy / dist
      source.vx += ux * displacement
      source.vy += uy * displacement
      target.vx -= ux * displacement
      target.vy -= uy * displacement
    }

    for (const id of nodes) {
      const node = positions.get(id)!
      node.x = clamp(node.x + node.vx, MARGIN, width - MARGIN)
      node.y = clamp(node.y + node.vy, MARGIN, height - MARGIN)
    }
  }

  const result = new Map<string, Point>()
  for (const id of nodes) {
    const node = positions.get(id)!
    result.set(id, { x: node.x, y: node.y })
  }
  return result
}

// Un paso de la simulacion en vivo (por frame mientras se arrastra). Mismo
// modelo que layoutNodes -- misma gravedad a los centros de comunidad, misma
// repulsion y resortes -- asi el layout asentado es su equilibrio: en reposo
// las fuerzas se cancelan y al soltar un nodo vuelve exacto a su lugar, con un
// poco de rebote (damping mas alto que el asentado). Las velocidades de los
// vecinos se perturban con los resortes al arrastrar, por eso la telaraña
// "reacciona". Devuelve la energia cinetica para saber cuando congelar.
function liveStep(
  sim: Map<string, SimNode>,
  nodes: string[],
  edges: InteractionGraphData["edges"],
  centers: Point[],
  communityOf: Map<string, number>,
  springLength: number,
  maxWeight: number,
  damping: number,
  dragging: string | null,
  width: number,
  height: number,
): number {
  for (const id of nodes) {
    const node = sim.get(id)
    if (!node) continue
    if (id === dragging) {
      node.vx = 0
      node.vy = 0
      continue
    }
    const center = centers[communityOf.get(id) ?? 0]
    let fx = (center.x - node.x) * GRAVITY
    let fy = (center.y - node.y) * GRAVITY

    for (const otherId of nodes) {
      if (otherId === id) continue
      const other = sim.get(otherId)!
      const dx = node.x - other.x
      const dy = node.y - other.y
      const distSq = Math.max(dx * dx + dy * dy, 1)
      const dist = Math.sqrt(distSq)
      const force = REPULSION / distSq
      fx += (dx / dist) * force
      fy += (dy / dist) * force
    }

    node.vx = (node.vx + fx) * damping
    node.vy = (node.vy + fy) * damping
  }

  for (const edge of edges) {
    const source = sim.get(edge.source)
    const target = sim.get(edge.target)
    if (!source || !target) continue
    const dx = target.x - source.x
    const dy = target.y - source.y
    const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
    const strength = EDGE_STRENGTH * (0.4 + 0.6 * (edge.weight / maxWeight))
    const displacement = (dist - springLength) * strength
    const ux = dx / dist
    const uy = dy / dist
    source.vx += ux * displacement
    source.vy += uy * displacement
    target.vx -= ux * displacement
    target.vy -= uy * displacement
  }

  let kinetic = 0
  for (const id of nodes) {
    const node = sim.get(id)
    if (!node || id === dragging) continue
    node.x = clamp(node.x + node.vx, 20, width - 20)
    node.y = clamp(node.y + node.vy, 24, height - 30)
    kinetic += node.vx * node.vx + node.vy * node.vy
  }
  return kinetic
}

function snapshot(sim: Map<string, SimNode>): Map<string, Point> {
  const out = new Map<string, Point>()
  sim.forEach((node, id) => out.set(id, { x: node.x, y: node.y }))
  return out
}

function formatLatency(seconds: number) {
  if (seconds < 90) return `${Math.round(seconds)}s`
  return `${Math.round(seconds / 60)}min`
}

function InteractionGraph({ graph }: Props) {
  const { width, height } = canvasSize(graph.nodes.length)
  const communityCount = Math.max(graph.communities.length, 1)
  const springLength = springLengthFor(width, height, communityCount)
  const maxWeight = Math.max(...graph.edges.map((edge) => edge.weight), 1)

  const home = useMemo(
    () => layoutNodes(graph.nodes, graph.edges, graph.communities, width, height),
    [graph, width, height],
  )
  const { centers, communityOf } = useMemo(
    () => buildCommunityCenters(graph.communities, width, height),
    [graph, width, height],
  )

  const prefersReducedMotion =
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  const interactive = !prefersReducedMotion && graph.nodes.length > 1

  const [positions, setPositions] = useState<Map<string, Point>>(home)
  const [hoverId, setHoverId] = useState<string | null>(null)
  const [syncedHome, setSyncedHome] = useState(home)

  const simRef = useRef<Map<string, SimNode>>(new Map())
  const draggingRef = useRef<string | null>(null)
  const rafRef = useRef<number | null>(null)
  const wakeRef = useRef<() => void>(() => {})
  const svgRef = useRef<SVGSVGElement | null>(null)

  // Resetear a la nueva disposicion cuando cambia el layout (nuevos datos o
  // resize). Patron de estado derivado de props en render -- evita el setState
  // dentro de un efecto (que dispara renders en cascada). La siembra de la
  // simulacion (mutar el ref) va en el efecto, no aca.
  if (syncedHome !== home) {
    setSyncedHome(home)
    setPositions(home)
    setHoverId(null)
  }

  useEffect(() => {
    const sim = new Map<string, SimNode>()
    home.forEach((point, id) => sim.set(id, { x: point.x, y: point.y, vx: 0, vy: 0 }))
    simRef.current = sim

    if (!interactive) {
      wakeRef.current = () => {}
      return
    }

    const loop = () => {
      const kinetic = liveStep(
        simRef.current,
        graph.nodes,
        graph.edges,
        centers,
        communityOf,
        springLength,
        maxWeight,
        0.92,
        draggingRef.current,
        width,
        height,
      )
      setPositions(snapshot(simRef.current))
      if (draggingRef.current || kinetic > 0.02) {
        rafRef.current = requestAnimationFrame(loop)
      } else {
        rafRef.current = null
      }
    }
    wakeRef.current = () => {
      if (rafRef.current == null) rafRef.current = requestAnimationFrame(loop)
    }

    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
      rafRef.current = null
      draggingRef.current = null
    }
  }, [home, graph, width, height, centers, communityOf, springLength, maxWeight, interactive])

  const pointerToSvg = (clientX: number, clientY: number) => {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect) return null
    return {
      x: ((clientX - rect.left) / rect.width) * width,
      y: ((clientY - rect.top) / rect.height) * height,
    }
  }

  const handleNodeDown = (author: string) => (event: ReactPointerEvent) => {
    if (!interactive) return
    event.preventDefault()
    draggingRef.current = author
    setHoverId(author)
    try {
      svgRef.current?.setPointerCapture(event.pointerId)
    } catch {
      // el puntero puede no estar activo (ej. gesto sintetico); no es fatal
    }
    wakeRef.current()
  }

  const handleSvgMove = (event: ReactPointerEvent) => {
    const id = draggingRef.current
    if (!id) return
    const node = simRef.current.get(id)
    const target = pointerToSvg(event.clientX, event.clientY)
    if (!node || !target) return
    node.x = target.x
    node.y = target.y
    node.vx = 0
    node.vy = 0
  }

  const endDrag = (event: ReactPointerEvent) => {
    if (!draggingRef.current) return
    draggingRef.current = null
    try {
      svgRef.current?.releasePointerCapture?.(event.pointerId)
    } catch {
      // el puntero pudo haberse liberado ya; no es fatal
    }
    wakeRef.current()
  }

  if (graph.nodes.length === 0) {
    return <p className="interaction-graph-empty">No hay suficientes mensajes para inferir vinculos en esta ventana.</p>
  }

  const maxCentrality = Math.max(...graph.nodes.map((author) => graph.centrality[author] ?? 0), 0.0001)
  const showCommunities = graph.communities.length > 1
  const nodeRadius = new Map(graph.nodes.map((author) => [author, 12 + ((graph.centrality[author] ?? 0) / maxCentrality) * 16]))
  const edgeKeys = new Set(graph.edges.map((edge) => `${edge.source}>${edge.target}`))

  return (
    <div className="interaction-graph">
      <svg
        ref={svgRef}
        className="interaction-graph-svg"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Grafo de quien le responde a quien en el grupo"
        style={{ touchAction: interactive ? "none" : undefined }}
        onPointerMove={interactive ? handleSvgMove : undefined}
        onPointerUp={interactive ? endDrag : undefined}
        onPointerCancel={interactive ? endDrag : undefined}
      >
        <defs>
          {/* markerUnits=userSpaceOnUse: la punta queda de tamaño fijo en vez
              de escalar con el grosor del trazo (las flechas gruesas quedaban
              desproporcionadas). */}
          <marker id="ig-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto">
            <path className="interaction-graph-arrowhead" d="M0,0 L10,5 L0,10 z" />
          </marker>
        </defs>

        {showCommunities &&
          graph.communities.map((community, index) => {
            const points = community.map((author) => positions.get(author)).filter((point): point is Point => Boolean(point))
            if (points.length === 0) return null
            const minX = Math.min(...points.map((p) => p.x)) - 30
            const maxX = Math.max(...points.map((p) => p.x)) + 30
            const minY = Math.min(...points.map((p) => p.y)) - 30
            const maxY = Math.max(...points.map((p) => p.y)) + 30
            return (
              <rect
                key={`community-${index}`}
                className="interaction-graph-community"
                x={minX}
                y={minY}
                width={maxX - minX}
                height={maxY - minY}
                rx={16}
              />
            )
          })}

        {graph.edges.map((edge) => {
          const source = positions.get(edge.source)
          const target = positions.get(edge.target)
          if (!source || !target) return null
          const dx = target.x - source.x
          const dy = target.y - source.y
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
          const sourceRadius = nodeRadius.get(edge.source) ?? 12
          const targetRadius = nodeRadius.get(edge.target) ?? 12
          // Si los nodos quedan casi encima (al arrastrar uno sobre otro) la
          // linea recortada se invertia y la flecha apuntaba al reves; mejor no
          // dibujarla.
          if (dist - sourceRadius - targetRadius < 10) return null
          const ux = dx / dist
          const uy = dy / dist
          // Vinculos reciprocos (A->B y B->A): se separan perpendicularmente a
          // lados opuestos para que no se dibujen una encima de la otra. El
          // perpendicular se invierte con la direccion, asi el par cae a lados
          // distintos automaticamente.
          const offset = edgeKeys.has(`${edge.target}>${edge.source}`) ? 6 : 0
          const ox = -uy * offset
          const oy = ux * offset
          const intensity = edge.weight / maxWeight
          const connected = hoverId != null && (edge.source === hoverId || edge.target === hoverId)
          const dimmed = hoverId != null && !connected
          const strokeOpacity = dimmed ? 0.06 : connected ? 0.95 : 0.32 + intensity * 0.5
          return (
            <line
              key={`${edge.source}-${edge.target}`}
              className="interaction-graph-edge"
              x1={source.x + ux * sourceRadius + ox}
              y1={source.y + uy * sourceRadius + oy}
              x2={target.x - ux * (targetRadius + 8) + ox}
              y2={target.y - uy * (targetRadius + 8) + oy}
              style={{ strokeWidth: 1 + intensity * 3, strokeOpacity }}
              markerEnd="url(#ig-arrow)"
            >
              <title>
                {edge.source} responde a {edge.target} en un promedio de {formatLatency(edge.avg_latency_seconds)}
              </title>
            </line>
          )
        })}

        {graph.nodes.map((author) => {
          const point = positions.get(author)
          if (!point) return null
          const centrality = graph.centrality[author] ?? 0
          const radius = nodeRadius.get(author) ?? 12
          const hot = hoverId === author
          const className = `interaction-graph-node${interactive ? " is-interactive" : ""}${hot ? " is-hot" : ""}`
          return (
            <g
              key={author}
              className={className}
              onPointerDown={interactive ? handleNodeDown(author) : undefined}
              onPointerEnter={interactive ? () => draggingRef.current || setHoverId(author) : undefined}
              onPointerLeave={interactive ? () => draggingRef.current || setHoverId(null) : undefined}
            >
              <circle cx={point.x} cy={point.y} r={radius}>
                <title>
                  {author} — centralidad {centrality.toFixed(2)}
                </title>
              </circle>
              <text x={point.x} y={point.y + radius + 16} textAnchor="middle">
                {author}
              </text>
            </g>
          )
        })}
      </svg>
      <p className="interaction-graph-caption">
        {interactive ? "Arrastra los nodos para reordenarlos. " : ""}Grosor y opacidad de las flechas ≈ fuerza del vinculo de
        respuesta. Tamano de nodo ≈ centralidad
        {showCommunities ? ". Los contornos marcan comunidades detectadas dentro del grupo." : "."}
      </p>
    </div>
  )
}

export default InteractionGraph
