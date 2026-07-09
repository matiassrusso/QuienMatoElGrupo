import { useMemo } from "react"
import type { InteractionGraphData } from "../api"

interface Props {
  graph: InteractionGraphData
}

interface Point {
  x: number
  y: number
}

const BASE_WIDTH = 640
const MARGIN = 56

function canvasSize(nodeCount: number) {
  // Con pocos nodos el tamaño base alcanza; con un grupo grande (10+
  // personas) el layout necesita mas aire o las lineas se amontonan sin
  // importar cuanto se pode -- se descubrio con un grupo real de 13
  // personas, donde el tamaño fijo de antes daba una marana ilegible.
  const width = Math.min(1100, Math.max(BASE_WIDTH, nodeCount * 68))
  return { width, height: Math.round(width * 0.62) }
}

// Layout congelado (ver DESIGN.md: nada de simulacion de fuerza en vivo). Se
// corre una simulacion tipo Fruchterman-Reingold en JS puro, de forma
// sincronica, y se descartan las velocidades -- solo quedan las posiciones
// finales. No hace falta d3-force para esto: son ~40 lineas de repulsion +
// resorte, y evita meter una dependencia nueva para calcular un layout que
// se usa una unica vez.
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

  // Cada comunidad detectada tiene su propio centro de gravedad, repartidos
  // en un circulo grande -- sin esto, todos los nodos convergen al mismo
  // centro y las comunidades quedan superpuestas aunque esten bien
  // separadas en los datos (el layout no "sabe" que existen).
  const communityOf = new Map<string, number>()
  communities.forEach((community, index) => {
    community.forEach((author) => communityOf.set(author, index))
  })
  const communityCount = Math.max(communities.length, 1)
  const clusterSpread = communityCount > 1 ? Math.min(width, height) * 0.3 : 0
  const communityCenters = Array.from({ length: communityCount }, (_, index) => {
    const angle = (2 * Math.PI * index) / communityCount
    return {
      x: width / 2 + clusterSpread * Math.cos(angle),
      y: height / 2 + clusterSpread * Math.sin(angle),
    }
  })
  const centerFor = (id: string) => communityCenters[communityOf.get(id) ?? 0]

  const positions = new Map<string, { x: number; y: number; vx: number; vy: number }>()
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
  const springLength = Math.min(width, height) * (communityCount > 1 ? 0.22 : 0.3)
  const repulsion = 2600

  for (let iteration = 0; iteration < 280; iteration++) {
    for (const id of nodes) {
      const node = positions.get(id)!
      const center = centerFor(id)
      let fx = (center.x - node.x) * 0.012
      let fy = (center.y - node.y) * 0.012

      for (const otherId of nodes) {
        if (otherId === id) continue
        const other = positions.get(otherId)!
        const dx = node.x - other.x
        const dy = node.y - other.y
        const distSq = Math.max(dx * dx + dy * dy, 1)
        const dist = Math.sqrt(distSq)
        const force = repulsion / distSq
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
      const strength = 0.018 * (0.4 + 0.6 * (edge.weight / maxWeight))
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
      node.x += node.vx
      node.y += node.vy
    }
  }

  const xs = nodes.map((id) => positions.get(id)!.x)
  const ys = nodes.map((id) => positions.get(id)!.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const spanX = Math.max(maxX - minX, 1)
  const spanY = Math.max(maxY - minY, 1)

  const result = new Map<string, Point>()
  for (const id of nodes) {
    const node = positions.get(id)!
    result.set(id, {
      x: MARGIN + ((node.x - minX) / spanX) * (width - MARGIN * 2),
      y: MARGIN + ((node.y - minY) / spanY) * (height - MARGIN * 2),
    })
  }
  return result
}

function formatLatency(seconds: number) {
  if (seconds < 90) return `${Math.round(seconds)}s`
  return `${Math.round(seconds / 60)}min`
}

function InteractionGraph({ graph }: Props) {
  const { width, height } = canvasSize(graph.nodes.length)
  const positions = useMemo(
    () => layoutNodes(graph.nodes, graph.edges, graph.communities, width, height),
    [graph, width, height],
  )

  if (graph.nodes.length === 0) {
    return <p className="interaction-graph-empty">No hay suficientes mensajes para inferir vinculos en esta ventana.</p>
  }

  const maxWeight = Math.max(...graph.edges.map((edge) => edge.weight), 1)
  const maxCentrality = Math.max(...graph.nodes.map((author) => graph.centrality[author] ?? 0), 0.0001)
  const showCommunities = graph.communities.length > 1
  const nodeRadius = new Map(graph.nodes.map((author) => [author, 12 + ((graph.centrality[author] ?? 0) / maxCentrality) * 16]))

  return (
    <div className="interaction-graph">
      <svg className="interaction-graph-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Grafo de quien le responde a quien en el grupo">
        <defs>
          <marker id="ig-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
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
          const intensity = edge.weight / maxWeight
          const dx = target.x - source.x
          const dy = target.y - source.y
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
          const ux = dx / dist
          const uy = dy / dist
          const sourceRadius = nodeRadius.get(edge.source) ?? 12
          const targetRadius = nodeRadius.get(edge.target) ?? 12
          return (
            <line
              key={`${edge.source}-${edge.target}`}
              className="interaction-graph-edge"
              x1={source.x + ux * sourceRadius}
              y1={source.y + uy * sourceRadius}
              x2={target.x - ux * (targetRadius + 6)}
              y2={target.y - uy * (targetRadius + 6)}
              style={{ strokeWidth: 1 + intensity * 3, strokeOpacity: 0.16 + intensity * 0.6 }}
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
          return (
            <g key={author} className="interaction-graph-node">
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
        Grosor y opacidad de las flechas ≈ fuerza del vinculo de respuesta. Tamano de nodo ≈ centralidad
        {showCommunities ? ". Los contornos marcan comunidades detectadas dentro del grupo." : "."}
      </p>
    </div>
  )
}

export default InteractionGraph
