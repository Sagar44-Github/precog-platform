import * as THREE from 'three'
import SpriteText from 'three-spritetext'
import { coneOpacity, coneWidth } from './sceneModel.js'

// Three.js objects for the scene (owner: VIZ). Everything here except makeLabel works without a browser, so it is tested in Node.

export function makeHostMesh(node, colors) {
  const color = colors[node.state] || colors.normal
  const geometry = node.shape === 'octahedron' ? new THREE.OctahedronGeometry(node.radius)
    : node.shape === 'cube' ? new THREE.BoxGeometry(node.radius, node.radius, node.radius)
      : new THREE.SphereGeometry(node.radius, 16, 12)
  const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ color }))
  mesh.name = 'body'
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
  if (node.state === 'contained') group.add(makeRing(node.radius * 1.9, colors.contained, false))
  if (node.predicted !== null) {
    group.add(makeRing(node.radius * 2.3, colors.forecast, true))
    const percentLabel = makeLabel(`${node.predicted} %`, colors.forecast, 4)
    if (percentLabel) { percentLabel.position.set(0, node.radius * 3.2, 0); group.add(percentLabel) }
  }
  const name = makeLabel(node.name, colors.text, 3.5)
  if (name) { name.position.set(0, -node.radius * 2.2, 0); group.add(name) }
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
