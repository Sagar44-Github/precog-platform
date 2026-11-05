import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import ForceGraph3D from '3d-force-graph'
import { makeCone, makeHostObject, placeCone } from './objects3d.js'
import { createSceneDecorations, disposeSceneDecorations } from './sceneDecorations.js'
import { pulseScale } from './sceneModel.js'
import { browserVar, prefersReducedMotion, readSceneColors } from './theme3d.js'
import { useTheme } from '../../shared/theme-context.jsx'

/** The 3D picture of the network (owner: VIZ). It draws the plain-data model made by sceneModel.js.
 *  Hosts have fixed positions, so the picture is calm. It cannot be tested without a graphics card: check it by eye (guide step D8). */
export default function Scene3D({ model, pendingForecast, onSelect, mode = 'console', cameraPreset = 'isometric', focusHostId = null }) {
  const { theme } = useTheme()
  const holder = useRef(null)
  const graphRef = useRef(null)
  const live = useRef({ model, pendingForecast, previousStates: {}, pulses: {}, cones: [] })
  live.current.model = model
  live.current.pendingForecast = pendingForecast

  // create the scene once
  useEffect(() => {
    live.current.cones = []
    live.current.previousStates = {}
    live.current.pulses = {}
    const colors = readSceneColors(browserVar)
    const reduced = prefersReducedMotion()
    const graph = ForceGraph3D({ controlType: 'orbit' })(holder.current)
      .backgroundColor(colors.bg)
      .showNavInfo(false)
      .nodeId('id')
      .nodeThreeObject((node) => makeHostObject(node, colors))
      .nodeThreeObjectExtend(false)
      .linkColor((link) => (link.onPath ? colors.compromised : colors.muted))
      .linkOpacity(0.5)
      .linkWidth((link) => (link.onPath ? 1.8 : 0.7))
      .linkDirectionalParticles((link) => (reduced || !link.onPath ? 0 : 2))
      .linkDirectionalParticleWidth(1.6)
      .cooldownTicks(0)
      .onNodeClick((node) => onSelect && onSelect(node.id))
      .onBackgroundClick(() => onSelect && onSelect(null))
    graph.cameraPosition(mode === 'twin' ? { x: 0, y: 190, z: 300 } : { x: 0, y: 90, z: 280 })
    const controls = graph.controls()
    controls.autoRotate = mode !== 'twin' && !reduced
    controls.autoRotateSpeed = 0.67          // about one turn every 90 seconds
    graphRef.current = graph
    const atmosphere = createSceneDecorations(colors, { twin: mode === 'twin', zones: live.current.model.zones })
    graph.scene().add(atmosphere)
    const coneGroup = new THREE.Group()
    graph.scene().add(coneGroup)

    let frame = 0
    const start = performance.now()
    const tick = () => {
      const now = performance.now()
      const nodes = graph.graphData().nodes
      const byId = Object.fromEntries(nodes.map((n) => [n.id, n]))
      const current = live.current
      // pulse once when a host becomes compromised
      for (const node of nodes) {
        if (current.previousStates[node.id] && current.previousStates[node.id] !== 'compromised' && node.state === 'compromised' && !reduced) current.pulses[node.id] = now
        current.previousStates[node.id] = node.state
        const object = node.__threeObj
        if (object) {
          const scale = current.pulses[node.id] ? pulseScale(now - current.pulses[node.id]) : 1
          object.scale.setScalar(scale)
          if (scale === 1) delete current.pulses[node.id]
        }
      }
      // forecast cones: rebuild when the forecast changes, "breathe" slowly
      const wanted = current.model.cones
      if (current.cones.length !== wanted.length || current.cones.some((c, i) => c.userData.to !== wanted[i].to || c.userData.confidence !== wanted[i].confidence)) {
        current.cones.forEach((c) => { coneGroup.remove(c); c.geometry.dispose(); c.material.dispose() })
        current.cones = wanted.map((w) => { const cone = makeCone(colors, w.confidence); cone.userData.to = w.to; coneGroup.add(cone); return cone })
      }
      wanted.forEach((w, i) => {
        const from = byId[w.from]; const to = byId[w.to]
        if (!from || !to || from.x === undefined) return
        placeCone(current.cones[i], from, to, w.confidence)
        current.cones[i].material.opacity = w.opacity * (reduced ? 1 : 1 + 0.08 * Math.sin(((now - start) / 2400) * Math.PI * 2))
      })
      controls.autoRotate = mode !== 'twin' && !reduced && !current.pendingForecast       // keep the cones still while a decision is pending
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    const resize = () => graph.width(holder.current.clientWidth).height(holder.current.clientHeight)
    resize()
    window.addEventListener('resize', resize)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', resize)
      graph.scene().remove(atmosphere)
      disposeSceneDecorations(atmosphere)
      graph._destructor()
      graphRef.current = null
    }
  }, [theme, mode])  // Rebuild the small six-host scene when the CSS theme changes.

  // feed new data into the scene
  useEffect(() => {
    const graph = graphRef.current
    if (!graph) return
    const nodes = model.nodes.map((n) => ({ ...n, fx: n.x, fy: n.y, fz: n.z }))
    graph.graphData({ nodes, links: model.links.map((l) => ({ ...l })) })
  }, [model])

  useEffect(() => {
    const graph = graphRef.current
    if (!graph || mode !== 'twin') return
    const selected = model.nodes.find((node) => node.id === focusHostId)
    const lookAt = selected ? { x: selected.x, y: selected.y, z: selected.z } : { x: 0, y: 0, z: 0 }
    const positions = {
      isometric: { x: lookAt.x, y: 190, z: lookAt.z + 300 },
      top: { x: lookAt.x, y: 330, z: lookAt.z + 4 },
      side: { x: lookAt.x + 320, y: 75, z: lookAt.z + 5 },
    }
    graph.cameraPosition(positions[cameraPreset] || positions.isometric, lookAt, 750)
  }, [cameraPreset, focusHostId, mode, model])

  return <div ref={holder} className="c-scene" role="presentation" />
}
