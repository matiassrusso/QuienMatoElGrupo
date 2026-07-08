import { useEffect, useRef, useState } from "react"
import { Canvas, useFrame } from "@react-three/fiber"
import { OrbitControls } from "@react-three/drei"
import type * as THREE from "three"
import type { HeatmapCell } from "../api"
import ActivityHeatmap from "./ActivityHeatmap"

// Apertura 3D de "La Sala de Pruebas" (ver DESIGN.md / plan-rediseno-datos-ia.md):
// el heatmap se extruye en relieve, la camara orbita brevemente, y se asienta
// en la grilla 2D exacta (ActivityHeatmap) para lectura precisa del dato.

const AUTO_ORBIT_MS = 3200
const FADE_MS = 900

function mixColor(t: number) {
  const low = [42, 20, 20]
  const high = [194, 58, 58] // official-seal-red-bright, DESIGN.md
  const [r, g, b] = low.map((channel, i) => Math.round(channel + (high[i] - channel) * t))
  return `rgb(${r}, ${g}, ${b})`
}

function Terrain({ cells, maxCount }: { cells: HeatmapCell[]; maxCount: number }) {
  const groupRef = useRef<THREE.Group>(null)

  useFrame((_, delta) => {
    const group = groupRef.current
    if (!group) return
    for (const child of group.children) {
      const mesh = child as THREE.Mesh
      const data = mesh.userData as { targetScaleY: number; delay: number; elapsed: number }
      data.elapsed = (data.elapsed ?? 0) + delta
      if (data.elapsed < data.delay || mesh.scale.y >= data.targetScaleY) continue
      mesh.scale.y = Math.min(data.targetScaleY, mesh.scale.y + delta * 3.5)
      mesh.position.y = mesh.scale.y / 2
    }
  })

  return (
    <group ref={groupRef}>
      {cells.map((cell) => {
        const intensity = maxCount === 0 ? 0 : cell.count / maxCount
        const targetScaleY = Math.max(0.04, intensity * 3.2)
        return (
          <mesh
            key={`${cell.weekday}-${cell.hour}`}
            position={[(cell.hour - 11.5) * 0.85, 0.02, (cell.weekday - 3) * 0.85]}
            scale={[0.72, 0.04, 0.72]}
            userData={{ targetScaleY, delay: (cell.hour / 24) * 0.5 + (cell.weekday / 7) * 0.2, elapsed: 0 }}
          >
            <boxGeometry args={[1, 1, 1]} />
            <meshStandardMaterial color={mixColor(intensity)} />
          </mesh>
        )
      })}
    </group>
  )
}

function computeAllow3D() {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
  const isNarrow = window.innerWidth < 768
  return !reducedMotion && !isNarrow
}

interface Props {
  cells: HeatmapCell[]
}

function ActivityHeatmap3D({ cells }: Props) {
  const maxCount = Math.max(...cells.map((cell) => cell.count), 0)

  const [allow3D] = useState(computeAllow3D)
  const [show3D, setShow3D] = useState(allow3D)
  const [fading, setFading] = useState(false)

  useEffect(() => {
    if (!show3D) return
    const fadeTimer = setTimeout(() => setFading(true), AUTO_ORBIT_MS)
    const unmountTimer = setTimeout(() => setShow3D(false), AUTO_ORBIT_MS + FADE_MS)
    return () => {
      clearTimeout(fadeTimer)
      clearTimeout(unmountTimer)
    }
  }, [show3D])

  return (
    <div className="heatmap3d">
      <div className="heatmap3d-grid">
        <ActivityHeatmap cells={cells} />
      </div>

      {allow3D && show3D && (
        <div className={`heatmap3d-canvas ${fading ? "is-fading" : ""}`}>
          <Canvas camera={{ position: [4.5, 14, 12], fov: 42 }} dpr={[1, 1.5]}>
            <color attach="background" args={["#0e0d0c"]} />
            <ambientLight intensity={0.12} />
            <directionalLight position={[6, 10, 4]} intensity={1.6} color="#f1ede4" />
            <spotLight position={[-5, 6, -5]} intensity={0.5} angle={0.5} penumbra={1} color="#c23a3a" />
            <mesh position={[0, -0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
              <planeGeometry args={[24, 10]} />
              <meshStandardMaterial color="#0a0908" />
            </mesh>
            <Terrain cells={cells} maxCount={maxCount} />
            <OrbitControls
              target={[0, 1.1, 0]}
              autoRotate
              autoRotateSpeed={1.1}
              enableZoom={false}
              enablePan={false}
              minPolarAngle={Math.PI / 6}
              maxPolarAngle={Math.PI / 2.6}
            />
          </Canvas>
        </div>
      )}
    </div>
  )
}

export default ActivityHeatmap3D
