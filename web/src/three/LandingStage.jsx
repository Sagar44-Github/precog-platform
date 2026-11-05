import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import data from '../landing/data.generated.json'
import { demoState } from '../landing/demoState.js'
import { createQualityManager, qualitySettings, recordFrame } from '../landing/qualityManager.js'
import { useTheme } from '../shared/theme-context.jsx'
import { readBrowserTokenColors, readBrowserTokenStyles } from './tokenColors.js'

function makeLabel(text, height, color, fontToken = '--font-mono') {
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d')
  const fontFamily = getComputedStyle(document.documentElement).getPropertyValue(fontToken).trim() || 'monospace'
  const fontSize = 96
  const padding = 24
  context.font = `500 ${fontSize}px ${fontFamily}`
  const textWidth = Math.ceil(context.measureText(text).width)
  canvas.width = textWidth + padding * 2
  canvas.height = fontSize + padding * 2
  context.font = `500 ${fontSize}px ${fontFamily}`
  context.textBaseline = 'middle'
  context.fillStyle = color
  context.fillText(text, padding, canvas.height / 2)
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.minFilter = THREE.LinearFilter
  texture.magFilter = THREE.LinearFilter
  texture.generateMipmaps = false
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false }))
  sprite.scale.set(height * (canvas.width / canvas.height), height, 1)
  return sprite
}

function addLine(scene, from, to, color, opacity = 0.52) {
  const geometry = new THREE.BufferGeometry().setFromPoints([from, to])
  const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color, transparent: true, opacity }))
  scene.add(line)
  return line
}

function makeHost(host, colors, styles, detail, lightMode) {
  const group = new THREE.Group()
  group.userData.hostId = host.host_id
  group.name = `host-${host.host_id}`
  const radius = 0.48
  const pedestal = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.78, 0.18, 28), new THREE.MeshStandardMaterial({ color: colors.surface, metalness: lightMode ? 0.04 : 0.5, roughness: lightMode ? 0.76 : 0.42, emissive: colors.normal, emissiveIntensity: lightMode ? 0 : 0.08 }))
  pedestal.position.y = 0.08
  const baseRing = new THREE.Mesh(new THREE.TorusGeometry(0.69, 0.026, 6, 36), new THREE.MeshBasicMaterial({ color: colors.normal, transparent: true, opacity: 0.74 }))
  baseRing.rotation.x = Math.PI / 2
  baseRing.position.y = 0.18
  const sphere = new THREE.Mesh(new THREE.SphereGeometry(radius, detail, detail), new THREE.MeshStandardMaterial({ color: colors.normal, roughness: lightMode ? 0.48 : 0.25, metalness: lightMode ? 0.03 : 0.22, emissive: colors.normal, emissiveIntensity: lightMode ? 0.015 : 0.18 }))
  sphere.position.y = 0.76
  sphere.name = 'normal-sphere'
  const octahedron = new THREE.Mesh(new THREE.OctahedronGeometry(radius * 1.22, 0), new THREE.MeshStandardMaterial({ color: colors.compromised, roughness: lightMode ? 0.46 : 0.2, metalness: lightMode ? 0.04 : 0.25, emissive: colors.compromised, emissiveIntensity: lightMode ? 0.07 : 0.55 }))
  octahedron.position.y = 0.79
  octahedron.name = 'compromised-octahedron'
  octahedron.visible = false
  const cube = new THREE.Mesh(new THREE.BoxGeometry(radius * 1.8, radius * 1.8, radius * 1.8), new THREE.MeshStandardMaterial({ color: colors.contained, roughness: lightMode ? 0.46 : 0.19, metalness: lightMode ? 0.04 : 0.28, emissive: colors.contained, emissiveIntensity: lightMode ? 0.06 : 0.42 }))
  cube.position.y = 0.78
  cube.name = 'contained-cube'
  cube.visible = false
  const ring = new THREE.Mesh(new THREE.TorusGeometry(radius * 1.75, 0.035, 6, detail * 2), new THREE.MeshBasicMaterial({ color: colors.contained, transparent: true, opacity: 0.82 }))
  ring.rotation.x = Math.PI / 2
  ring.position.y = 0.23
  ring.visible = false
  const label = makeLabel(host.name, lightMode ? 0.31 : 0.39, styles.text, '--font-ui')
  label.position.y = 1.56
  group.add(pedestal, baseRing, sphere, octahedron, cube, ring, label)
  group.position.set(host.position[0], 0, host.position[1])
  return { group, sphere, octahedron, cube, ring, host }
}

function makeZone(scene, zoneId, hosts, colors, styles, lightMode) {
  const xs = hosts.map((host) => host.position[0])
  const zs = hosts.map((host) => host.position[1])
  const centerX = (Math.min(...xs) + Math.max(...xs)) / 2
  const centerZ = (Math.min(...zs) + Math.max(...zs)) / 2
  const width = Math.max(3.8, Math.max(...xs) - Math.min(...xs) + 3.2)
  const depth = Math.max(3.8, Math.max(...zs) - Math.min(...zs) + 3.4)
  const zoneColor = lightMode ? colors.surface.clone().lerp(colors.border, 0.22) : colors.surface
  const plane = new THREE.Mesh(new THREE.BoxGeometry(width, 0.24, depth), new THREE.MeshStandardMaterial({ color: zoneColor, metalness: lightMode ? 0 : 0.28, roughness: lightMode ? 0.82 : 0.5, emissive: colors.forecast, emissiveIntensity: lightMode ? 0 : 0.025 }))
  plane.position.set(centerX, -0.16, centerZ)
  plane.name = `zone-surface-${zoneId}`
  scene.add(plane)
  const outline = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(width, 0.04, depth)),
    new THREE.LineBasicMaterial({ color: colors.border, transparent: true, opacity: 0.76 }),
  )
  outline.position.set(centerX, -0.16, centerZ)
  scene.add(outline)
  const label = makeLabel(zoneId.toUpperCase(), lightMode ? 0.28 : 0.38, styles.muted)
  label.position.set(centerX - width * 0.42, 0.02, centerZ - depth * 0.39)
  scene.add(label)
}

function curveBetween(from, to, lift = 0.7) {
  const start = new THREE.Vector3(from.x, 0.2, from.z)
  const end = new THREE.Vector3(to.x, 0.2, to.z)
  const middle = start.clone().lerp(end, 0.5).setY(lift)
  return new THREE.QuadraticBezierCurve3(start, middle, end)
}

function createScene(canvas, { activeStep, onSelectHost, theme }) {
  const lightMode = theme === 'light'
  const styles = readBrowserTokenStyles()
  const colors = readBrowserTokenColors()
  canvas.dataset.theme = theme
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, powerPreference: 'low-power' })
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.NoToneMapping
  const gl = renderer.getContext()
  const info = gl.getExtension('WEBGL_debug_renderer_info')
  const rendererName = info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : ''
  let quality = createQualityManager({
    phone: window.matchMedia('(max-width: 760px)').matches,
    lowPower: (navigator.hardwareConcurrency || 8) <= 4 || (navigator.deviceMemory || 8) <= 4,
    saveData: navigator.connection?.saveData,
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    renderer: rendererName,
    devicePixelRatio: window.devicePixelRatio,
  })
  const settings = () => qualitySettings(quality, window.devicePixelRatio)
  renderer.setPixelRatio(settings().pixelRatio)
  renderer.shadowMap.enabled = settings().shadows
  const scene = new THREE.Scene()
  scene.background = colors.background
  scene.fog = new THREE.Fog(colors.background, 28, 58)
  const bounds = data.simulation.hosts.map((host) => host.position)
  const centerX = (Math.min(...bounds.map(([x]) => x)) + Math.max(...bounds.map(([x]) => x))) / 2
  const centerZ = (Math.min(...bounds.map(([, z]) => z)) + Math.max(...bounds.map(([, z]) => z))) / 2
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100)
  camera.position.set(centerX + 8, 9, centerZ + 11)
  camera.lookAt(centerX, 0, centerZ)
  const ambient = new THREE.HemisphereLight(lightMode ? colors.surface : colors.text, lightMode ? colors.background : colors.surface, lightMode ? 1.2 : 1.45)
  scene.add(ambient)
  const keyLight = new THREE.DirectionalLight(lightMode ? colors.surface : colors.text, lightMode ? 1.25 : 2.3)
  keyLight.position.set(centerX - 7, 12, centerZ + 8)
  keyLight.castShadow = settings().shadows
  keyLight.shadow.mapSize.set(512, 512)
  scene.add(keyLight)
  const forecastLight = new THREE.PointLight(colors.forecast, lightMode ? 0.12 : 21, 26, 2)
  forecastLight.position.set(centerX + 1, 5, centerZ - 1)
  scene.add(forecastLight)
  const grid = new THREE.GridHelper(36, 36, colors.border, colors.surface)
  grid.position.y = -0.31
  grid.material.transparent = true
  grid.material.opacity = lightMode ? 0.22 : 0.36
  scene.add(grid)

  const hostsById = new Map(data.simulation.hosts.map((host) => [host.host_id, host]))
  for (const zone of data.simulation.zones) makeZone(scene, zone, data.simulation.hosts.filter((host) => host.zone === zone), colors, styles, lightMode)
  const hosts = new Map(data.simulation.hosts.map((host) => [host.host_id, makeHost(host, colors, styles, settings().maxHostSegments, lightMode)]))
  for (const { group } of hosts.values()) scene.add(group)
  for (const edge of data.simulation.edges) {
    const a = hostsById.get(edge.from)
    const b = hostsById.get(edge.to)
    addLine(scene, new THREE.Vector3(a.position[0], 0.04, a.position[1]), new THREE.Vector3(b.position[0], 0.04, b.position[1]), colors.border, 0.7)
  }

  const entryHost = hostsById.get(data.simulation.entryHost)
  const targetHost = hostsById.get(data.simulation.attemptedTo)
  const entry = new THREE.Vector3(entryHost.position[0], 0, entryHost.position[1])
  const target = new THREE.Vector3(targetHost.position[0], 0, targetHost.position[1])
  const attackCurve = curveBetween(entry, target, 1.15)
  const attackTrail = new THREE.Mesh(
    new THREE.TubeGeometry(attackCurve, 56, 0.065, 7, false),
    new THREE.MeshBasicMaterial({ color: colors.compromised, transparent: true, opacity: 0.92 }),
  )
  attackTrail.name = 'observed-attack-path'
  attackTrail.visible = false
  scene.add(attackTrail)

  const forecasts = data.forecast.candidates.map((candidate) => {
    const host = hostsById.get(candidate.hostId)
    const curve = curveBetween(entry, new THREE.Vector3(host.position[0], 0, host.position[1]), 0.75 + candidate.confidence)
    const radius = 0.075 + candidate.confidence * 0.22
    const path = new THREE.Mesh(
      new THREE.TubeGeometry(curve, 36, radius, 7, false),
      new THREE.MeshStandardMaterial({ color: colors.forecast, roughness: lightMode ? 0.68 : 0.25, metalness: lightMode ? 0 : 0.3, emissive: colors.forecast, emissiveIntensity: lightMode ? 0.06 : 0.7, transparent: true, opacity: lightMode ? 0.82 : 0.86, depthWrite: false }),
    )
    path.name = `forecast-path-${candidate.hostId}`
    path.visible = false
    scene.add(path)
    const label = makeLabel(`${candidate.percent}%`, lightMode ? 0.22 : 0.28, styles.forecast)
    label.position.set(host.position[0], 1.65, host.position[1])
    label.visible = false
    scene.add(label)
    return { path, label, candidate }
  })

  const lattice = new THREE.Group()
  lattice.name = 'containment-lattice'
  const latticeBox = new THREE.EdgesGeometry(new THREE.BoxGeometry(1.8, 1.8, 1.8))
  lattice.add(new THREE.LineSegments(latticeBox, new THREE.LineBasicMaterial({ color: colors.contained, transparent: true, opacity: 0.88 })))
  const gridPoints = []
  for (const y of [-0.55, 0, 0.55]) {
    gridPoints.push(new THREE.Vector3(-0.9, y, 0), new THREE.Vector3(0.9, y, 0))
    gridPoints.push(new THREE.Vector3(y, -0.9, 0), new THREE.Vector3(y, 0.9, 0))
    gridPoints.push(new THREE.Vector3(0, y, -0.9), new THREE.Vector3(0, y, 0.9))
  }
  lattice.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(gridPoints), new THREE.LineBasicMaterial({ color: colors.contained, transparent: true, opacity: 0.58 })))
  lattice.position.set(target.x, 0.1, target.z)
  lattice.visible = false
  scene.add(lattice)

  const packets = data.simulation.trafficEdges.flatMap((route) => Array.from({ length: route.repeat }, (_, index) => {
    const packet = new THREE.Mesh(new THREE.SphereGeometry(0.09, 8, 6), new THREE.MeshBasicMaterial({ color: colors.compromised }))
    packet.name = `scripted-packet-${route.from}-${route.to}-${index}`
    scene.add(packet)
    return { packet, route, index }
  }))

  const raycaster = new THREE.Raycaster()
  const pointer = new THREE.Vector2()
  const controls = new OrbitControls(camera, renderer.domElement)
  controls.target.set(centerX, 0, centerZ)
  controls.enableDamping = true
  controls.dampingFactor = 0.06
  controls.minDistance = 11
  controls.maxDistance = 38
  controls.maxPolarAngle = Math.PI * 0.46
  controls.autoRotate = false
  controls.addEventListener('change', () => renderer.render(scene, camera))

  let width = 1
  let height = 1
  let disposed = false
  let previousFrame = 0
  let elapsed = 0
  let currentStep = activeStep
  const initialQuality = quality.tier

  function resize() {
    const rect = canvas.getBoundingClientRect()
    width = Math.max(1, Math.round(rect.width))
    height = Math.max(1, Math.round(rect.height))
    camera.aspect = width / height
    if (width < height) {
      camera.position.set(centerX + 24, 14, centerZ + 3)
      // Keep the hero copy clear on phones by placing the network below it.
      controls.target.set(centerX, 2.3, centerZ)
      camera.fov = 42
    } else if (lightMode) {
      camera.position.set(centerX + 6, 10.5, centerZ + 14)
      controls.target.set(centerX - 1.8, 0, centerZ)
      camera.fov = 43
    } else {
      camera.position.set(centerX + 8, 9, centerZ + 11)
      controls.target.set(centerX, 0, centerZ)
      camera.fov = 38
    }
    camera.updateProjectionMatrix()
    renderer.setPixelRatio(settings().pixelRatio)
    renderer.setSize(width, height, false)
  }

  function draw(step = activeStep, delta = 16.7) {
    if (disposed) return
    currentStep = step
    const state = demoState(step)
    const before = quality.tier
    quality = recordFrame(quality, delta)
    if (before !== quality.tier) {
      renderer.setPixelRatio(settings().pixelRatio)
      renderer.shadowMap.enabled = settings().shadows
      keyLight.castShadow = settings().shadows
    }
    for (const [hostId, item] of hosts) {
      const compromised = hostId === data.simulation.entryHost && state.detected
      const contained = hostId === data.simulation.attemptedTo && state.contained
      item.sphere.visible = !compromised && !contained
      item.octahedron.visible = compromised
      item.cube.visible = contained
      item.ring.visible = contained
    }
    attackTrail.visible = state.reconstructed
    for (const { path, label, candidate } of forecasts) {
      path.visible = state.forecast
      label.visible = state.forecast
      path.material.opacity = state.contained ? (candidate.hostId === data.simulation.attemptedTo ? 0.9 : 0.16) : 0.7
    }
    lattice.visible = state.contained
    for (const { packet, route, index } of packets) {
      const from = hostsById.get(route.from)
      const to = hostsById.get(route.to)
      const progress = (elapsed * 0.2 + index / Math.max(1, route.repeat)) % 1
      packet.position.set(
        from.position[0] + (to.position[0] - from.position[0]) * progress,
        0.24 + Math.sin(progress * Math.PI) * 0.22,
        from.position[1] + (to.position[1] - from.position[1]) * progress,
      )
      packet.visible = state.detected && !state.contained
    }
    renderer.render(scene, camera)
    canvas.dataset.geometryCount = String(renderer.info.memory.geometries)
    canvas.dataset.textureCount = String(renderer.info.memory.textures)
    canvas.dataset.quality = quality.tier
    canvas.dataset.initialQuality = initialQuality
  }

  function animate(now) {
    if (disposed) return
    const frameLimit = quality.tier === 'lite' ? 1000 / 30 : 1000 / 45
    if (previousFrame && now - previousFrame < frameLimit) return
    const delta = previousFrame ? Math.min(50, now - previousFrame) : 16.7
    previousFrame = now
    elapsed += delta / 1000
    controls.update()
    if (demoState(currentStep).detected && !demoState(currentStep).contained) draw(currentStep, delta)
  }

  let pointerStart = null
  function onPointerDown(event) { pointerStart = { x: event.clientX, y: event.clientY } }
  function onPointerUp(event) {
    if (event.button !== 0) return
    if (pointerStart && Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 5) return
    const rect = canvas.getBoundingClientRect()
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
    raycaster.setFromCamera(pointer, camera)
    const hit = raycaster.intersectObjects([...hosts.values()].map(({ group }) => group), true)[0]
    if (!hit) return
    let node = hit.object
    while (node && !node.userData.hostId) node = node.parent
    const host = node && hostsById.get(node.userData.hostId)
    if (host) onSelectHost(host)
  }
  renderer.domElement.addEventListener('pointerdown', onPointerDown)
  renderer.domElement.addEventListener('pointerup', onPointerUp)

  function dispose() {
    disposed = true
    renderer.setAnimationLoop(null)
    renderer.domElement.removeEventListener('pointerdown', onPointerDown)
    renderer.domElement.removeEventListener('pointerup', onPointerUp)
    controls.dispose()
    scene.traverse((object) => {
      object.geometry?.dispose()
      const materials = Array.isArray(object.material) ? object.material : object.material ? [object.material] : []
      for (const material of materials) {
        material.map?.dispose()
        material.dispose()
      }
    })
    renderer.dispose()
    renderer.forceContextLoss()
  }

  resize()
  draw(activeStep)
  renderer.setAnimationLoop(animate)
  return { draw, resize, dispose }
}

export default function LandingStage({ activeStep, onSelectHost, onFailure }) {
  const { theme } = useTheme()
  const canvasRef = useRef(null)
  const sceneRef = useRef(null)
  const selectedCallback = useRef(onSelectHost)
  selectedCallback.current = onSelectHost
  const failureCallback = useRef(onFailure)
  failureCallback.current = onFailure

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return undefined
    let scene
    try {
      scene = createScene(canvas, { activeStep, theme, onSelectHost: (host) => selectedCallback.current?.(host) })
      sceneRef.current = scene
    } catch (error) {
      failureCallback.current?.(error)
      return undefined
    }
    const observer = new ResizeObserver(() => scene?.resize())
    observer.observe(canvas)
    return () => {
      observer.disconnect()
      scene?.dispose()
      sceneRef.current = null
    }
  }, [theme])

  useEffect(() => { sceneRef.current?.draw(activeStep) }, [activeStep])
  return <canvas ref={canvasRef} className="landing-canvas" aria-hidden="true" data-landing-renderer="three" />
}
