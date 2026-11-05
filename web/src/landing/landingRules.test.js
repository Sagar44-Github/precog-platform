import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const folder = resolve(fileURLToPath(new URL('.', import.meta.url)))

function sourceFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    return entry.isDirectory() ? sourceFiles(path) : /\.(jsx?|css|json)$/.test(entry.name) && !/\.test\.[^.]+$/.test(entry.name) ? [path] : []
  })
}

test('landing copy avoids unsupported protection claims and carries its simulation limits', () => {
  const copy = sourceFiles(folder).map((path) => readFileSync(path, 'utf8')).join('\n').toLowerCase()
  for (const forbidden of ['stops breaches', 'ai-powered security', '99 %', 'real-time defence of your network', 'lorem ipsum']) assert.ok(!copy.includes(forbidden), `forbidden phrase found: ${forbidden}`)
  assert.match(copy, /everything shown here is a simulation/)
  assert.match(copy, /precision@1/)
  assert.match(copy, /held-out/)
  assert.match(copy, /attack type omitted from training/)
  assert.match(copy, /does not test future traffic or establish live detection/)
  assert.match(copy, /precision@3 is uninformative/)
})

test('landing and shared 3D source contain no inline colour codes', () => {
  const files = [...sourceFiles(folder), ...sourceFiles(resolve(folder, '../three'))]
  for (const path of files) {
    const source = readFileSync(path, 'utf8')
    assert.doesNotMatch(source, /#[\da-f]{3,8}\b/i, `${path} contains a hex colour`)
    assert.doesNotMatch(source, /\b(?:rgba?|hsla?)\s*\(/i, `${path} contains an inline colour function`)
  }
})
