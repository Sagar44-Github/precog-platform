import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import ForceGraph3D from '3d-force-graph'
import { makeCone, makeHostObject, placeCone } from '../../areas/console/objects3d.js'
import { createSceneDecorations, disposeSceneDecorations } from '../../areas/console/sceneDecorations.js'
import { pulseScale } from '../../areas/console/sceneModel.js'
import { browserVar, prefersReducedMotion, readSceneColors } from '../../areas/console/theme3d.js'
import { useTheme } from '../theme-context.jsx'
import { CAMERA_PRESETS } from './camera-presets.js'

/** Shared 3D picture of the simulated network; its plain scene model and camera helpers are tested without a GPU. */
export default function Scene3D({ model, pendingForecast, onSelect, selectedHostId = null, focusHostId = selectedHostId, cameraPreset = 'isometric', onReady, onQualityChange, autoRotate = true }) {
  const { theme } = useTheme()
  const holder = useRef(null)
  const graphRef = useRef(null)
  const live = useRef({ model, pendingForecast, previousStates: {}, pulses: {}, cones: [], onQualityChange, lowDetail: Boolean(model?.lowDetail) })
  live.current.model = model
  live.current.pendingForecast = pendingForecast
  live.current.onQualityChange = onQualityChange
  live.current.lowDetail = Boolean(model?.lowDetail)

  function frameLargeGraph(graph, nodes, presetName) {
    if (!graph || !nodes.length) return
    const coords = nodes.filter((node) => Number.isFinite(node.x) && Number.isFinite(node.y) && Number.isFinite(node.z))
    if (!coords.length) return
    const bounds = coords.reduce((value, node) => ({
      minX: Math.min(value.minX, node.x), maxX: Math.max(value.maxX, node.x),
      minY: Math.min(value.minY, node.y), maxY: Math.max(value.maxY, node.y),
      minZ: Math.min(value.minZ, node.z), maxZ: Math.max(value.maxZ, node.z),
    }), { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity, minZ: Infinity, maxZ: -Infinity })
    const center = { x: (bounds.minX + bounds.maxX) / 2, y: (bounds.minY + bounds.maxY) / 2, z: (bounds.minZ + bounds.maxZ) / 2 }
    const extent = Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY, bounds.maxZ - bounds.minZ, 180)
    const preset = CAMERA_PRESETS[presetName] || CAMERA_PRESETS.isometric
    const direction = new THREE.Vector3(preset.position.x, preset.position.y, preset.position.z).normalize()
    const distance = Math.max(360, extent * 0.65)
    const controls = graph.controls()
    controls.minDistance = Math.max(80, extent * 0.18)
    controls.maxDistance = Math.max(540, distance * 5)
    graph.cameraPosition({ x: center.x + direction.x * distance, y: center.y + direction.y * distance, z: center.z + direction.z * distance }, center, 650)
  }

  // create the scene once
  useEffect(() => {
    live.current.cones = []
    live.current.previousStates = {}
    live.current.pulses = {}
    const colors = readSceneColors(browserVar)
    const reduced = prefersReducedMotion()
    const graph = ForceGraph3D({ controlType: 'orbit', rendererConfig: { antialias: true, alpha: true } })(holder.current)
      .backgroundColor(colors.bg)
      .showNavInfo(false)
      .nodeId('id')
      .nodeThreeObject((node) => makeHostObject(node, colors, { compact: live.current.lowDetail }))
      .nodeThreeObjectExtend(false)
      .linkColor((link) => (link.onPath ? colors.compromised : colors.muted))
      .linkOpacity(0.5)
      .linkWidth((link) => (link.onPath ? 1.2 : 0.4))
      .linkVisibility((link) => link.visible !== false)
      .linkDirectionalParticles((link) => (reduced || !link.onPath ? 0 : 2))
      .linkDirectionalParticleWidth(1.6)
      .linkDirectionalParticleSpeed(0.0028)
      .cooldownTicks(0)
      .onNodeClick((node) => onSelect && onSelect(node.id))
      .onBackgroundClick(() => onSelect && onSelect(null))
    graph.cameraPosition(CAMERA_PRESETS.isometric.position)
    const controls = graph.controls()
    controls.autoRotate = autoRotate && !reduced
    controls.autoRotateSpeed = 0.67          // about one turn every 90 seconds
    controls.enableDamping = true
    controls.dampingFactor = 0.08
    controls.minDistance = 125
    controls.maxDistance = 540
    const renderer = graph.renderer()
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
    renderer.shadowMap.enabled = !live.current.lowDetail
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.05
    graphRef.current = graph
    const atmosphere = createSceneDecorations(colors)
    graph.scene().add(atmosphere)
    const coneGroup = new THREE.Group()
    graph.scene().add(coneGroup)
    onReady?.(graph)

    let frame = 0
    const start = performance.now()
    let fpsFrames = 0
    let fpsCheckAt = start
    let qualityDropped = false
    const tick = () => {
      const now = performance.now()
      fpsFrames += 1
      if (!qualityDropped && now - fpsCheckAt >= 1000) {
        const fps = fpsFrames * 1000 / (now - fpsCheckAt)
        if (fps < 40) {
          qualityDropped = true
          renderer.setPixelRatio(1)
          const stars = atmosphere.getObjectByName('background-stars')
          if (stars?.material) stars.material.size = 1
          live.current.onQualityChange?.('reduced')
        }
        fpsFrames = 0
        fpsCheckAt = now
      }
      const nodes = graph.graphData().nodes
      const byId = Object.fromEntries(nodes.map((n) => [n.id, n]))
      const current = live.current
      // pulse once when a host becomes compromised
      for (const node of nodes) {
        if (current.previousStates[node.id] && current.previousStates[node.id] !== 'compromised' && node.state === 'compromised' && !reduced) {
          current.pulses[node.id] = now
          const shockwave = node.__threeObj?.getObjectByName('shockwave')
          if (shockwave) { shockwave.visible = true; shockwave.userData.started = now; shockwave.scale.setScalar(0.2) }
        }
        current.previousStates[node.id] = node.state
        const object = node.__threeObj
        if (object) {
          const scale = current.pulses[node.id] ? pulseScale(now - current.pulses[node.id]) : 1
          object.scale.setScalar(scale)
          if (scale === 1) delete current.pulses[node.id]
          const shockwave = object.getObjectByName('shockwave')
          if (shockwave?.visible) {
            const progress = Math.min(1, (now - shockwave.userData.started) / 900)
            shockwave.scale.setScalar(0.2 + progress * 2.2)
            shockwave.material.opacity = 0.55 * (1 - progress)
            if (progress >= 1) shockwave.visible = false
          }
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
      controls.autoRotate = autoRotate && !reduced && !current.pendingForecast       // keep the cones still while a decision is pending
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
      onReady?.(null)
    }
  }, [theme])  // Rebuild the shared network scene when CSS theme tokens change.

  // feed new data into the scene
  useEffect(() => {
    const graph = graphRef.current
    if (!graph) return
    const nodes = model.nodes.map((n) => ({ ...n, fx: n.x, fy: n.y, fz: n.z }))
    graph.graphData({ nodes, links: model.links.map((l) => ({ ...l })) })
    if (model.lowDetail) {
      graph.renderer().shadowMap.enabled = false
      frameLargeGraph(graph, nodes, cameraPreset)
    }
  }, [model, theme, cameraPreset])

  useEffect(() => {
    const graph = graphRef.current
    if (!graph) return
    const targetNode = focusHostId ? graph.graphData().nodes.find((node) => node.id === focusHostId) : null
    if (targetNode && targetNode.x !== undefined) {
      graph.cameraPosition({ x: targetNode.x + 140, y: targetNode.y + 70, z: targetNode.z + 220 }, { x: targetNode.x, y: targetNode.y, z: targetNode.z }, 900)
      return
    }
    if (model.lowDetail) {
      frameLargeGraph(graph, graph.graphData().nodes, cameraPreset)
      return
    }
    const preset = CAMERA_PRESETS[cameraPreset] || CAMERA_PRESETS.isometric
    graph.cameraPosition(preset.position, { x: 0, y: 0, z: 0 }, 650)
  }, [cameraPreset, focusHostId, theme, model.lowDetail])

  const forecastKey = model.cones.map((cone) => `${cone.from}:${cone.to}:${cone.confidence}`).join('|')
  useEffect(() => {
    const graph = graphRef.current
    if (!graph || !model.cones.length) return
    const targetId = model.cones[0].to
    const target = graph.graphData().nodes.find((node) => node.id === targetId)
    if (target && target.x !== undefined) graph.cameraPosition({ x: target.x + 160, y: target.y + 110, z: target.z + 245 }, { x: target.x, y: target.y, z: target.z }, 1000)
  }, [forecastKey, theme])

  return <div ref={holder} className="c-scene" role="presentation" data-theme={theme} />
}
