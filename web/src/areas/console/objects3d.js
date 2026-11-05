import * as THREE from 'three'
import SpriteText from 'three-spritetext'
import { coneOpacity, coneWidth } from './sceneModel.js'

// Three.js objects for the scene (owner: VIZ). Everything here except makeLabel works without a browser, so it is tested in Node.

export function makeHostMesh(node, colors) {
  const color = colors[node.state] || colors.normal
  const geometry = node.shape === 'octahedron' ? new THREE.OctahedronGeometry(node.radius)
    : node.shape === 'cube' ? new THREE.BoxGeometry(node.radius, node.radius, node.radius)
      : new THREE.SphereGeometry(node.radius, 16, 12)
  const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color, roughness: 0.68, metalness: 0.08 }))
  mesh.name = 'body'
  mesh.castShadow = true
  mesh.receiveShadow = true
  return mesh
}

function addRoleModel(group, node, colors) {
  const role = String(node.role || '').toLowerCase()
  if (!role || node.state !== 'normal') return
  const accent = new THREE.MeshStandardMaterial({ color: colors.text, roughness: 0.55, metalness: 0.12 })
  const radius = node.radius
  const detail = (name, geometry, x, y, z) => {
    const part = new THREE.Mesh(geometry, accent)
    part.name = name
    part.position.set(x, y, z)
    part.castShadow = true
    part.receiveShadow = true
    group.add(part)
  }
  if (role.includes('workstation')) {
    detail('host-model-screen', new THREE.BoxGeometry(radius * 1.15, radius * 0.72, radius * 0.18), 0, radius * 0.82, 0)
    detail('host-model-stand', new THREE.BoxGeometry(radius * 0.18, radius * 0.36, radius * 0.18), 0, radius * 0.25, 0)
  } else if (role.includes('web server') || role.includes('file server') || role.includes('domain controller')) {
    detail('host-model-tower', new THREE.BoxGeometry(radius * 0.72, radius * 1.8, radius * 0.72), 0, radius * 0.2, 0)
    detail('host-model-drive', new THREE.BoxGeometry(radius * 0.38, radius * 0.08, radius * 0.09), 0, radius * 0.36, radius * 0.39)
    if (role.includes('file')) detail('host-model-storage', new THREE.BoxGeometry(radius * 0.85, radius * 0.18, radius * 0.78), 0, -radius * 0.75, 0)
    if (role.includes('domain')) detail('host-model-domain-mark', new THREE.CylinderGeometry(radius * 0.28, radius * 0.28, radius * 0.3, 6), 0, radius * 1.18, 0)
  } else if (role.includes('database')) {
    detail('host-model-database', new THREE.CylinderGeometry(radius * 0.72, radius * 0.72, radius * 1.42, 8), 0, 0, 0)
    detail('host-model-database-cap', new THREE.CylinderGeometry(radius * 0.72, radius * 0.72, radius * 0.16, 8), 0, radius * 0.72, 0)
  }
}

function makeHeatFootprint(node, colors) {
  if (node.overlay !== 'risk' && node.overlay !== 'weakness') return null
  const amount = node.overlay === 'risk' ? Math.max(0, Math.min(1, node.risk / 100)) : Math.max(0, Math.min(1, node.weaknessCount / 4))
  const tint = new THREE.Color(colors.low).lerp(new THREE.Color(colors.high), amount)
  const mesh = new THREE.Mesh(
    new THREE.CylinderGeometry(1, 1.14, 0.7, 28),
    new THREE.MeshBasicMaterial({ color: tint, transparent: true, opacity: 0.13 + amount * 0.2, depthWrite: false }),
  )
  mesh.name = 'heat-overlay'
  mesh.scale.setScalar(node.radius * (2.9 + amount * 1.7))
  mesh.position.y = -node.radius * 1.15
  return mesh
}

/** A thin ring: teal around a contained host, dashed violet around a predicted target. */
export function makeRing(radius, color, dashed) {
  const points = []
  for (let i = 0; i <= 48; i += 1) points.push(new THREE.Vector3(Math.cos((i / 48) * Math.PI * 2) * radius, Math.sin((i / 48) * Math.PI * 2) * radius, 0))
  const geometry = new THREE.BufferGeometry().setFromPoints(points)
  const material = dashed ? new THREE.LineDashedMaterial({ color, dashSize: 2, gapSize: 1.5 }) : new THREE.LineBasicMaterial({ color })
  const ring = new THREE.Line(geometry, material)
  if (dashed) ring.computeLineDistances()
  ring.name = dashed ? 'predicted-ring' : 'contained-ring'
  return ring
}

export function makeLabel(text, color, size = 4) {
  if (typeof document === 'undefined') return null        // needs a browser canvas
  const sprite = new SpriteText(text, size, color)
  sprite.name = 'label'
  return sprite
}

/** Group = body + rings + labels for one host. */
export function makeHostObject(node, colors) {
  const group = new THREE.Group()
  group.name = node.id
  group.add(makeHostMesh(node, colors))
  addRoleModel(group, node, colors)
  const heat = makeHeatFootprint(node, colors)
  if (heat) group.add(heat)
  if (node.selected) {
    const selection = makeRing(node.radius * 3.15, colors.accent, false)
    selection.rotation.x = Math.PI / 2
    selection.name = 'selection-outline'
    group.add(selection)
  }
  if (node.state === 'compromised') {
    const halo = new THREE.Mesh(
      new THREE.SphereGeometry(node.radius * 2.25, 24, 16),
      new THREE.MeshBasicMaterial({ color: colors.compromised, transparent: true, opacity: 0.12, side: THREE.BackSide, depthWrite: false }),
    )
    halo.name = 'compromised-halo'
    group.add(halo)
    const orbit = makeRing(node.radius * 2.5, colors.compromised, false)
    orbit.rotation.x = Math.PI / 2
    orbit.name = 'compromised-orbit'
    group.add(orbit)
    const shockwave = new THREE.Mesh(new THREE.RingGeometry(node.radius * 0.85, node.radius, 40), new THREE.MeshBasicMaterial({ color: colors.compromised, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false }))
    shockwave.rotation.x = Math.PI / 2
    shockwave.position.y = -node.radius * 0.82
    shockwave.name = 'shockwave'
    shockwave.visible = false
    group.add(shockwave)
  }
  if (node.state === 'contained') {
    group.add(makeRing(node.radius * 1.9, colors.contained, false))
    const orbit = makeRing(node.radius * 2.35, colors.contained, false)
    orbit.rotation.x = Math.PI / 2
    orbit.name = 'contained-orbit'
    group.add(orbit)
    const shield = new THREE.Mesh(new THREE.SphereGeometry(node.radius * 2.05, 12, 8), new THREE.MeshBasicMaterial({ color: colors.contained, wireframe: true, transparent: true, opacity: 0.25, depthWrite: false }))
    shield.name = 'containment-shield'
    group.add(shield)
  }
  if (node.predicted !== null) {
    group.add(makeRing(node.radius * 2.3, colors.forecast, true))
    const glow = new THREE.Mesh(
      new THREE.SphereGeometry(node.radius * 2.0, 20, 14),
      new THREE.MeshBasicMaterial({ color: colors.forecast, transparent: true, opacity: 0.09, side: THREE.BackSide, depthWrite: false }),
    )
    glow.name = 'forecast-halo'
    group.add(glow)
    const percentLabel = makeLabel(`${node.predicted} %`, colors.forecast, 4)
    if (percentLabel) { percentLabel.position.set(0, node.radius * 3.2, 0); group.add(percentLabel) }
  }
  if (node.overlay === 'risk' || node.overlay === 'exposure') {
    const label = makeLabel(node.overlay === 'risk' ? `RISK ${Number(node.risk || 0).toFixed(1)}` : `LINKS ${node.exposure || 0}`, colors.text, 2.8)
    if (label) { label.position.set(0, node.radius * 2.35, 0); group.add(label) }
  }
  if (node.overlay === 'forecast' && node.predicted !== null) {
    const label = makeLabel(`EST ${node.predicted}%`, colors.forecast, 3)
    if (label) { label.position.set(0, node.radius * 3.8, 0); group.add(label) }
  }
  if (Array.isArray(node.services) && node.services.length) {
    node.services.slice(0, 4).forEach((service, index) => {
      const marker = new THREE.Mesh(new THREE.SphereGeometry(node.twin ? 1.8 : 1.35, 10, 8), new THREE.MeshBasicMaterial({ color: colors.accent }))
      const angle = (index / Math.min(node.services.length, 4)) * Math.PI * 2
      marker.position.set(Math.cos(angle) * (node.radius + 4), 0, Math.sin(angle) * (node.radius + 4))
      marker.name = `service-marker-${index}`
      marker.userData.service = service
      group.add(marker)
    })
  }
  const name = makeLabel(node.name, colors.text, node.twin ? 5 : 3.5)
  if (name) { name.position.set(0, -node.radius * 2.2, 0); group.add(name) }
  const stateLabel = makeLabel(String(node.state || 'normal').toUpperCase(), colors[node.state] || colors.muted, 2.4)
  if (stateLabel) { stateLabel.position.set(0, -node.radius * 3.1, 0); group.add(stateLabel) }
  return group
}

/** A cone from one host toward another: the wider and stronger, the more confident the forecast. */
export function makeCone(colors, confidence) {
  const cone = new THREE.Mesh(new THREE.ConeGeometry(1, 1, 24, 1, true), new THREE.MeshBasicMaterial({ color: colors.forecast, transparent: true, opacity: coneOpacity(confidence), side: THREE.DoubleSide, depthWrite: false }))
  cone.userData = { confidence }
  return cone
}

/** Puts a cone between two points: the tip at the target, the base at the source. */
export function placeCone(cone, from, to, confidence) {
  const start = new THREE.Vector3(from.x, from.y, from.z)
  const end = new THREE.Vector3(to.x, to.y, to.z)
  const direction = end.clone().sub(start)
  const length = Math.max(direction.length(), 0.001)
  const width = coneWidth(confidence)
  cone.scale.set(width, length, width)
  cone.position.copy(start.clone().add(end).multiplyScalar(0.5))
  cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.clone().normalize())
  return cone
}
