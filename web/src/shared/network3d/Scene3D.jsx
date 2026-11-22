import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import ForceGraph3D from '3d-force-graph'
import { makeCone, makeHostObject, placeCone } from '../../areas/console/objects3d.js'
import { createSceneDecorations, disposeSceneDecorations } from '../../areas/console/sceneDecorations.js'
import { pulseScale, shouldPulseHost } from '../../areas/console/sceneModel.js'
import { browserVar, prefersReducedMotion, readSceneColors } from '../../areas/console/theme3d.js'
import { useTheme } from '../theme-context.jsx'
import { CAMERA_PRESETS } from './camera-presets.js'
import { fitDistance, nodeGeometryKey } from './camera-fit.js'

function fitGraph(graph, nodes, presetName, width, height, duration = 650) {
  if (!graph || width < 1 || height < 1) return false
  const fit = fitDistance(nodes, width, height, graph.camera().fov, 1.24)
  if (!fit) return false
  const preset = CAMERA_PRESETS[presetName] || CAMERA_PRESETS.isometric
  const position = preset.position
  const length = Math.hypot(position.x, position.y, position.z) || 1
  const controls = graph.controls()
  controls.minDistance = Math.max(24, fit.radius * 0.12)
  controls.maxDistance = Math.max(1200, fit.distance * 8)
  graph.cameraPosition({
    x: fit.center.x + position.x / length * fit.distance,
    y: fit.center.y + position.y / length * fit.distance,
    z: fit.center.z + position.z / length * fit.distance,
  }, fit.center, prefersReducedMotion() ? 0 : duration)
  return true
}

/** Shared 3D picture of the simulated network; its plain scene model and camera helpers are tested without a GPU. */
export default function Scene3D({ model, pendingForecast, onSelect, selectedHostId = null, focusHostId = selectedHostId, cameraPreset = 'isometric', onReady, onQualityChange, autoRotate = true }) {
  const { theme } = useTheme()
  const [reducedMotion, setReducedMotion] = useState(() => prefersReducedMotion())
  const holder = useRef(null)
  const graphRef = useRef(null)
  const live = useRef({ model, pendingForecast, previousStates: {}, nodesById: {}, pulses: {}, cones: [], onQualityChange, lowDetail: Boolean(model?.lowDetail), cameraPreset, reducedMotion: false })
  live.current.model = model
  live.current.pendingForecast = pendingForecast
  live.current.onQualityChange = onQualityChange
  live.current.lowDetail = Boolean(model?.lowDetail)
  live.current.cameraPreset = cameraPreset

  // create the scene once
  useEffect(() => {
    live.current.cones = []
    live.current.previousStates = {}
    live.current.pulses = {}
    const colors = readSceneColors(browserVar)
    const motionQuery = typeof window.matchMedia === 'function' ? window.matchMedia('(prefers-reduced-motion: reduce)') : null
    live.current.reducedMotion = motionQuery?.matches ?? prefersReducedMotion()
    if (holder.current) holder.current.dataset.reducedMotion = String(live.current.reducedMotion)
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
      .linkDirectionalParticles((link) => (live.current.reducedMotion || !link.onPath ? 0 : 2))
      .linkDirectionalParticleWidth(1.6)
      .linkDirectionalParticleSpeed(0.0028)
      .cooldownTicks(0)
      .onNodeClick((node) => onSelect && onSelect(node.id))
      .onBackgroundClick(() => onSelect && onSelect(null))
    graph.cameraPosition(CAMERA_PRESETS.isometric.position)
    const controls = graph.controls()
    controls.autoRotate = autoRotate && !live.current.reducedMotion
    controls.autoRotateSpeed = 0.67          // about one turn every 90 seconds
    controls.enableDamping = true
    controls.dampingFactor = 0.08
    const updateMotionPreference = (event) => {
      live.current.reducedMotion = event.matches
      setReducedMotion(event.matches)
      if (holder.current) holder.current.dataset.reducedMotion = String(event.matches)
      controls.autoRotate = autoRotate && !event.matches && !live.current.pendingForecast
      graph.linkDirectionalParticles((link) => (event.matches || !link.onPath ? 0 : 2))
      if (event.matches) {
        Object.keys(live.current.pulses).forEach((hostId) => {
          const object = live.current.nodesById[hostId]?.__threeObj
          if (!object) return
          object.scale.setScalar(1)
          const shockwave = object.getObjectByName('shockwave')
          if (shockwave) shockwave.visible = false
        })
        live.current.pulses = {}
      }
    }
    motionQuery?.addEventListener?.('change', updateMotionPreference)
    if (motionQuery && !motionQuery.addEventListener) motionQuery.addListener(updateMotionPreference)
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
      const current = live.current
      if (motionQuery && motionQuery.matches !== current.reducedMotion) updateMotionPreference(motionQuery)
      // Only update hosts that are in their short transition window; steady nodes are untouched.
      Object.entries(current.pulses).forEach(([hostId, started]) => {
        const object = current.nodesById[hostId]?.__threeObj
        if (!object) { if (now - started >= 600) delete current.pulses[hostId]; return }
        const elapsed = now - started
        const scale = pulseScale(elapsed)
        object.scale.setScalar(scale)
        const shockwave = object.getObjectByName('shockwave')
        if (shockwave?.visible) {
          const progress = Math.min(1, (now - shockwave.userData.started) / 900)
          shockwave.scale.setScalar(0.2 + progress * 2.2)
          shockwave.material.opacity = 0.55 * (1 - progress)
          if (progress >= 1) shockwave.visible = false
        }
        if (elapsed >= 900 || (elapsed >= 600 && !shockwave?.visible)) delete current.pulses[hostId]
      })
      // forecast cones: rebuild when the forecast changes, "breathe" slowly
      const wanted = current.model.cones
      if (current.cones.length !== wanted.length || current.cones.some((c, i) => c.userData.to !== wanted[i].to || c.userData.confidence !== wanted[i].confidence)) {
        current.cones.forEach((c) => { coneGroup.remove(c); c.geometry.dispose(); c.material.dispose() })
        current.cones = wanted.map((w) => { const cone = makeCone(colors, w.confidence); cone.userData.to = w.to; coneGroup.add(cone); return cone })
      }
      wanted.forEach((w, i) => {
        const from = current.nodesById[w.from]; const to = current.nodesById[w.to]
        if (!from || !to || from.x === undefined) return
        placeCone(current.cones[i], from, to, w.confidence)
        current.cones[i].material.opacity = w.opacity * (current.reducedMotion ? 1 : 1 + 0.08 * Math.sin(((now - start) / 2400) * Math.PI * 2))
      })
      controls.autoRotate = autoRotate && !current.reducedMotion && !current.pendingForecast       // keep the cones still while a decision is pending
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    let lastWidth = 0
    let lastHeight = 0
    const resize = () => {
      const width = holder.current?.clientWidth || 0
      const height = holder.current?.clientHeight || 0
      if (!width || !height) return
      graph.width(width).height(height)
      if (width !== lastWidth || height !== lastHeight) {
        lastWidth = width
        lastHeight = height
        fitGraph(graph, graph.graphData().nodes, live.current.cameraPreset, width, height, 450)
      }
    }
    resize()
    window.addEventListener('resize', resize)
    const resizeObserver = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(resize)
    if (holder.current) resizeObserver?.observe(holder.current)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', resize)
      motionQuery?.removeEventListener?.('change', updateMotionPreference)
      if (motionQuery && !motionQuery.removeEventListener) motionQuery.removeListener(updateMotionPreference)
      resizeObserver?.disconnect()
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
    const current = live.current
    current.nodesById = Object.fromEntries(graph.graphData().nodes.map((node) => [node.id, node]))
    const now = performance.now()
    current.nodesById && Object.values(current.nodesById).forEach((node) => {
      if (shouldPulseHost(current.previousStates[node.id], node.state, current.reducedMotion)) {
        current.pulses[node.id] = now
        const shockwave = node.__threeObj?.getObjectByName('shockwave')
        if (shockwave) { shockwave.visible = true; shockwave.userData.started = now; shockwave.scale.setScalar(0.2) }
      }
      current.previousStates[node.id] = node.state
    })
    Object.keys(current.previousStates).forEach((id) => {
      if (!current.nodesById[id]) { delete current.previousStates[id]; delete current.pulses[id] }
    })
    if (model.lowDetail) {
      graph.renderer().shadowMap.enabled = false
    }
  }, [model, theme, cameraPreset])

  const geometryKey = nodeGeometryKey(model.nodes)
  useEffect(() => {
    const graph = graphRef.current
    if (!graph) return
    const targetNode = focusHostId ? graph.graphData().nodes.find((node) => node.id === focusHostId) : null
    if (targetNode && targetNode.x !== undefined) {
      graph.cameraPosition({ x: targetNode.x + 140, y: targetNode.y + 70, z: targetNode.z + 220 }, { x: targetNode.x, y: targetNode.y, z: targetNode.z }, prefersReducedMotion() ? 0 : 900)
      return
    }
    const width = holder.current?.clientWidth || 0
    const height = holder.current?.clientHeight || 0
    fitGraph(graph, graph.graphData().nodes, cameraPreset, width, height)
  }, [cameraPreset, focusHostId, geometryKey, theme])

  return <div ref={holder} className="c-scene" role="presentation" data-theme={theme} data-reduced-motion={reducedMotion} />
}
