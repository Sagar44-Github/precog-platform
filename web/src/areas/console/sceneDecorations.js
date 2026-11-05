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
export function createSceneDecorations(colors) {
  const stage = new THREE.Group()
  stage.name = 'precog-scene-atmosphere'

  const hemisphere = new THREE.HemisphereLight(colors.text, colors.bg, 0.55)
  hemisphere.name = 'ambient-hemisphere'
  stage.add(hemisphere)
  const directional = new THREE.DirectionalLight(colors.text, 0.9)
  directional.name = 'key-directional'
  directional.position.set(-90, 210, 155)
  directional.castShadow = true
  directional.shadow.mapSize.set(1024, 1024)
  directional.shadow.camera.left = -320
  directional.shadow.camera.right = 320
  directional.shadow.camera.top = 260
  directional.shadow.camera.bottom = -260
  directional.shadow.bias = -0.0002
  stage.add(directional)

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
  outerOrbit.position.set(0, -86, 0)
  outerOrbit.rotation.x = Math.PI / 2
  stage.add(outerOrbit)

  ZONES.forEach((zone, index) => {
    const platform = new THREE.Mesh(
      new THREE.CylinderGeometry(82, 88, 3, 56),
      new THREE.MeshStandardMaterial({ color: index === 1 ? colors.forecast : colors.accent, roughness: 0.92, metalness: 0.02, transparent: true, opacity: 0.12 }),
    )
    platform.name = `zone-platform-${index}`
    platform.position.set(zone.x, -84, -28)
    platform.castShadow = false
    platform.receiveShadow = true
    stage.add(platform)

    const field = new THREE.Mesh(
      new THREE.RingGeometry(46, 82, 72),
      new THREE.MeshBasicMaterial({ color: index === 1 ? colors.forecast : colors.accent, transparent: true, opacity: 0.055, side: THREE.DoubleSide, depthWrite: false }),
    )
    field.name = `zone-field-${index}`
    field.position.set(zone.x, -81, -28)
    field.rotation.x = Math.PI / 2
    stage.add(field)

    const orbit = new THREE.Mesh(
      new THREE.TorusGeometry(70, 0.7, 6, 100),
      new THREE.MeshBasicMaterial({ color: index === 1 ? colors.forecast : colors.accent, transparent: true, opacity: 0.2, depthWrite: false }),
    )
    orbit.name = `zone-orbit-${index}`
    orbit.position.set(zone.x, -79, -28)
    orbit.rotation.x = Math.PI / 2
    orbit.rotation.z = index === 1 ? Math.PI / 12 : -Math.PI / 18
    stage.add(orbit)

    const guide = line([new THREE.Vector3(zone.x, -81, -148), new THREE.Vector3(zone.x, -81, 100)], colors.muted, 0.15)
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

