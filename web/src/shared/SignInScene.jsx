import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { useTheme } from './theme-context.jsx'
import { browserVar, prefersReducedMotion } from '../areas/console/theme3d.js'

const NODES = [
  [-3.2, 1.3, 0], [-1.7, 0.2, 0.3], [0, 1.15, -0.3], [1.55, 0, 0.25],
  [3.15, 1.1, -0.15], [-2.7, -1.25, -0.25], [-0.7, -1.1, 0.2], [1.3, -1.35, -0.2], [3, -1.05, 0.3],
]
const EDGES = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,3],[6,7],[7,8],[4,8],[1,6],[2,6]]
const OBSERVED = [[0,1],[1,2],[2,3]]
const FORECAST = [[3,4],[3,7],[7,8]]

export default function SignInScene() {
  const hostRef = useRef(null)
  const [failed, setFailed] = useState(false)
  const { theme } = useTheme()

  useEffect(() => {
    const host = hostRef.current
    if (!host) return undefined
    let renderer
    let frame = 0
    let resizeObserver
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' })
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
      renderer.setSize(host.clientWidth, host.clientHeight)
      renderer.outputColorSpace = THREE.SRGBColorSpace
      renderer.toneMapping = THREE.ACESFilmicToneMapping
      host.appendChild(renderer.domElement)
    } catch {
      setFailed(true)
      return undefined
    }

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(34, host.clientWidth / host.clientHeight, 0.1, 100)
    camera.position.set(0.2, 0.25, 10.7)
    const group = new THREE.Group()
    scene.add(group)
    const lightMode = document.documentElement.dataset.theme === 'light'
    const tone = (name) => new THREE.Color(browserVar(name))
    scene.background = null
    scene.add(new THREE.AmbientLight(tone('--text'), lightMode ? 1.6 : 1.15))
    const key = new THREE.DirectionalLight(tone('--accent'), lightMode ? 2.1 : 1.7)
    key.position.set(-3, 5, 7)
    scene.add(key)
    const rim = new THREE.PointLight(tone('--forecast'), 18, 15)
    rim.position.set(3, -2, 4)
    scene.add(rim)

    const baseMat = new THREE.MeshStandardMaterial({ color: tone('--state-normal'), roughness: 0.38, metalness: 0.45 })
    const watchedMat = new THREE.MeshStandardMaterial({ color: tone('--accent'), roughness: 0.3, metalness: 0.42 })
    const threatMat = new THREE.MeshStandardMaterial({ color: tone('--state-compromised'), roughness: 0.3, metalness: 0.3, emissive: tone('--state-compromised'), emissiveIntensity: 0.25 })
    const geo = new THREE.IcosahedronGeometry(0.19, 2)
    const nodes = NODES.map((point, index) => {
      const mesh = new THREE.Mesh(geo, index === 2 ? threatMat : index === 3 ? watchedMat : baseMat)
      mesh.position.set(...point)
      mesh.scale.setScalar(index === 2 || index === 4 ? 1.22 : 1)
      group.add(mesh)
      const halo = new THREE.Mesh(new THREE.TorusGeometry(index === 2 ? 0.36 : 0.29, 0.009, 6, 48), new THREE.MeshBasicMaterial({ color: tone(index === 2 ? '--state-compromised' : index === 3 ? '--accent' : '--border-strong'), transparent: true, opacity: index === 2 ? 0.75 : 0.46 }))
      halo.position.copy(mesh.position)
      halo.rotation.x = Math.PI / 2.25
      group.add(halo)
      return mesh
    })
    const path = (pairs, color, opacity, dashed = false) => {
      for (const [from, to] of pairs) {
        const material = dashed ? new THREE.LineDashedMaterial({ color, transparent: true, opacity, dashSize: 0.13, gapSize: 0.1 }) : new THREE.LineBasicMaterial({ color, transparent: true, opacity })
        const geometry = new THREE.BufferGeometry().setFromPoints([nodes[from].position, nodes[to].position])
        const line = new THREE.Line(geometry, material)
        if (dashed) line.computeLineDistances()
        group.add(line)
      }
    }
    path(EDGES, tone('--border-strong'), lightMode ? 0.45 : 0.35)
    path(OBSERVED, tone('--accent'), 0.95)
    path(FORECAST, tone('--forecast'), 0.95, true)
    const boundary = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(2.6, 2.35, 0.9)), new THREE.LineBasicMaterial({ color: tone('--state-contained'), transparent: true, opacity: 0.62 }))
    boundary.position.set(2.35, 0, -0.25)
    group.add(boundary)
    const floor = new THREE.GridHelper(9, 18, tone('--border-strong'), tone('--border'))
    floor.position.y = -1.8
    floor.material.transparent = true
    floor.material.opacity = 0.36
    group.add(floor)

    const attacker = new THREE.Mesh(new THREE.SphereGeometry(0.075, 12, 10), new THREE.MeshBasicMaterial({ color: tone('--state-compromised') }))
    group.add(attacker)
    const trailNodes = [nodes[0], nodes[1], nodes[2], nodes[3]]
    const pointOnObservedPath = (progress) => {
      const scaled = Math.max(0, Math.min(1, progress)) * (trailNodes.length - 1)
      const segment = Math.min(trailNodes.length - 2, Math.floor(scaled))
      return trailNodes[segment].position.clone().lerp(trailNodes[segment + 1].position, scaled - segment)
    }
    const reduced = prefersReducedMotion()
    const start = performance.now()
    const render = (now) => {
      const elapsed = (now - start) / 1000
      if (!reduced) {
        group.rotation.y = Math.sin(elapsed * 0.16) * 0.065
        nodes.forEach((node, i) => { node.position.y = NODES[i][1] + Math.sin(elapsed * 0.65 + i * 0.7) * 0.025 })
        attacker.position.copy(pointOnObservedPath((elapsed * 0.13) % 1))
        boundary.material.opacity = 0.45 + (Math.sin(elapsed * 1.3) + 1) * 0.09
      } else attacker.position.copy(nodes[3].position)
      renderer.render(scene, camera)
      if (!reduced) frame = requestAnimationFrame(render)
    }
    frame = requestAnimationFrame(render)
    resizeObserver = new ResizeObserver(() => {
      if (!host.clientWidth || !host.clientHeight) return
      camera.aspect = host.clientWidth / host.clientHeight
      camera.updateProjectionMatrix()
      renderer.setSize(host.clientWidth, host.clientHeight)
    })
    resizeObserver.observe(host)
    return () => {
      cancelAnimationFrame(frame)
      resizeObserver?.disconnect()
      scene.traverse((item) => { item.geometry?.dispose(); if (Array.isArray(item.material)) item.material.forEach((material) => material.dispose()); else item.material?.dispose() })
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [theme])

  return <div className={`signin-scene${failed ? ' is-fallback' : ''}`} ref={hostRef} role="img" aria-label="Three dimensional simulation of network detection, observed attack path, predicted targets, and containment boundary">
    {failed && <div className="signin-scene-fallback" aria-hidden="true"><span>Endpoint A</span><span>Detection</span><span>Web Server B</span><span>Forecast targets</span><span>Contained zone</span></div>}
  </div>
}
