import * as THREE from 'three'
import { makeLabel } from './objects3d.js'

const ZONES = [
  { name: 'USER ZONE', x: -120 },
  { name: 'DMZ', x: 0 },
  { name: 'INTERNAL', x: 120 },
]

function line(points, color, opacity) {
  const geometry = new THREE.BufferGeometry().setFromPoints(points)
  const material = new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthWrite: false })
  return new THREE.Line(geometry, material)
}

/** A restrained 3D stage: ground grid, zone fields, orbital guides and a deterministic star field. */
export function createSceneDecorations(colors, { twin = false, zones = [] } = {}) {
  const stage = new THREE.Group()
  stage.name = 'precog-scene-atmosphere'

  if (twin) {
    const twinZones = zones.length ? zones : [
      { zone: 'user', label: 'USER ZONE', x: -150 },
      { zone: 'dmz', label: 'DMZ', x: 0 },
      { zone: 'internal', label: 'INTERNAL', x: 150 },
    ]
    twinZones.forEach((zone, index) => {
      const tint = index === 1 ? colors.forecast : colors.accent
      const slab = new THREE.Mesh(
        new THREE.BoxGeometry(132, 5, 185),
        new THREE.MeshBasicMaterial({ color: tint, transparent: true, opacity: 0.09, depthWrite: false }),
      )
      slab.name = `zone-slab-${zone.zone}`
      slab.position.set(zone.x, -36, 0)
      stage.add(slab)
      const outline = new THREE.LineSegments(
        new THREE.EdgesGeometry(slab.geometry),
        new THREE.LineBasicMaterial({ color: tint, transparent: true, opacity: 0.45 }),
      )
      outline.name = `zone-outline-${zone.zone}`
      outline.position.copy(slab.position)
      stage.add(outline)
      const label = makeLabel(zone.label || zone.zone.toUpperCase(), colors.text, 4)
      if (label) {
        label.name = `zone-label-${zone.zone}`
        label.position.set(zone.x, -26, -98)
        stage.add(label)
      }
    })
    const grid = new THREE.GridHelper(560, 28, colors.muted, colors.muted)
    grid.name = 'twin-floor-grid'
    grid.position.set(0, -40, 0)
    for (const material of Array.isArray(grid.material) ? grid.material : [grid.material]) {
      material.transparent = true
      material.opacity = 0.12
      material.depthWrite = false
    }
    stage.add(grid)
    return stage
  }

  const grid = new THREE.GridHelper(620, 40, colors.muted, colors.muted)
  grid.name = 'ground-grid'
  grid.position.set(0, -88, -8)
  for (const material of Array.isArray(grid.material) ? grid.material : [grid.material]) {
    material.transparent = true
    material.opacity = 0.16
    material.depthWrite = false
  }
  stage.add(grid)

  const outerOrbit = new THREE.Mesh(
    new THREE.TorusGeometry(286, 0.55, 6, 180),
    new THREE.MeshBasicMaterial({ color: colors.forecast, transparent: true, opacity: 0.16, depthWrite: false }),
  )
  outerOrbit.name = 'outer-orbit'
  outerOrbit.position.set(0, 0, -105)
  stage.add(outerOrbit)

  ZONES.forEach((zone, index) => {
    const field = new THREE.Mesh(
      new THREE.RingGeometry(46, 82, 72),
      new THREE.MeshBasicMaterial({ color: index === 1 ? colors.forecast : colors.accent, transparent: true, opacity: 0.055, side: THREE.DoubleSide, depthWrite: false }),
    )
    field.name = `zone-field-${index}`
    field.position.set(zone.x, 0, -75)
    stage.add(field)

    const orbit = new THREE.Mesh(
      new THREE.TorusGeometry(70, 0.7, 6, 100),
      new THREE.MeshBasicMaterial({ color: index === 1 ? colors.forecast : colors.accent, transparent: true, opacity: 0.2, depthWrite: false }),
    )
    orbit.name = `zone-orbit-${index}`
    orbit.position.set(zone.x, 0, -65)
    orbit.rotation.z = index === 1 ? Math.PI / 12 : -Math.PI / 18
    stage.add(orbit)

    const guide = line([new THREE.Vector3(zone.x, -95, -65), new THREE.Vector3(zone.x, 95, -65)], colors.muted, 0.15)
    guide.name = `zone-guide-${index}`
    stage.add(guide)

    const label = makeLabel(zone.name, colors.muted, 2.8)
    if (label) {
      label.name = `zone-label-${index}`
      label.position.set(zone.x, -104, -65)
      stage.add(label)
    }
  })

  const starPositions = []
  let seed = 71
  const random = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646 }
  for (let index = 0; index < 240; index += 1) {
    starPositions.push((random() - 0.5) * 760, (random() - 0.5) * 420, -210 - random() * 160)
  }
  const starsGeometry = new THREE.BufferGeometry()
  starsGeometry.setAttribute('position', new THREE.Float32BufferAttribute(starPositions, 3))
  const stars = new THREE.Points(starsGeometry, new THREE.PointsMaterial({ color: colors.muted, size: 1.5, transparent: true, opacity: 0.52, sizeAttenuation: false, depthWrite: false }))
  stars.name = 'background-stars'
  stage.add(stars)

  return stage
}

export function disposeSceneDecorations(stage) {
  stage.traverse((object) => {
    if (object.geometry) object.geometry.dispose()
    if (object.material) {
      const materials = Array.isArray(object.material) ? object.material : [object.material]
      materials.forEach((material) => material.dispose())
    }
  })
}

