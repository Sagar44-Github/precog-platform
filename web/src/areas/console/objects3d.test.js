import test from 'node:test'
import assert from 'node:assert/strict'
import * as THREE from 'three'
import { makeCone, makeHostObject, placeCone } from './objects3d.js'
import { readSceneColors } from './theme3d.js'

const colors = readSceneColors(() => 'white')

test('a compromised host is an octahedron body', () => {
  const group = makeHostObject({ id: 'a', name: 'A', shape: 'octahedron', radius: 6, state: 'compromised', predicted: null }, colors)
  assert.equal(group.getObjectByName('body').geometry.type, 'OctahedronGeometry')
})

test('a contained host is a cube with a ring', () => {
  const group = makeHostObject({ id: 'd', name: 'D', shape: 'cube', radius: 8, state: 'contained', predicted: null }, colors)
  assert.equal(group.getObjectByName('body').geometry.type, 'BoxGeometry')
  assert.ok(group.getObjectByName('contained-ring'))
})

test('a predicted host gets a dashed ring', () => {
  const group = makeHostObject({ id: 's', name: 'S', shape: 'sphere', radius: 4, state: 'normal', predicted: 74 }, colors)
  assert.equal(group.getObjectByName('predicted-ring').material.type, 'LineDashedMaterial')
  assert.equal(group.getObjectByName('contained-ring'), undefined)
})

test('a normal, unpredicted host is only a sphere', () => {
  const group = makeHostObject({ id: 'b', name: 'B', shape: 'sphere', radius: 4, state: 'normal', predicted: null }, colors)
  assert.equal(group.getObjectByName('body').geometry.type, 'SphereGeometry')
  assert.equal(group.children.length, 1)          // no labels in Node: they need a browser canvas
})

test('a cone is placed between two hosts, wider and stronger when more confident', () => {
  const strong = placeCone(makeCone(colors, 0.74), { x: 0, y: 0, z: 0 }, { x: 0, y: 100, z: 0 }, 0.74)
  const weak = placeCone(makeCone(colors, 0.07), { x: 0, y: 0, z: 0 }, { x: 0, y: 100, z: 0 }, 0.07)
  assert.deepEqual(strong.position.toArray(), [0, 50, 0])
  assert.equal(strong.scale.y, 100)
  assert.ok(strong.scale.x > weak.scale.x)
  assert.ok(strong.material.opacity > weak.material.opacity)
  const sideways = placeCone(makeCone(colors, 0.5), { x: 0, y: 0, z: 0 }, { x: 100, y: 0, z: 0 }, 0.5)
  const up = new THREE.Vector3(0, 1, 0).applyQuaternion(sideways.quaternion)
  assert.ok(Math.abs(up.x - 1) < 1e-6)             // the cone's long axis points along +x
})

test('scene colours come from the CSS variables, with a safe fallback', () => {
  const read = readSceneColors((name) => (name === '--forecast' ? ' violet ' : ''))
  assert.equal(read.forecast, 'violet')
  assert.equal(read.bg, 'white')
})
