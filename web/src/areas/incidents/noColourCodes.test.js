import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const folder = fileURLToPath(new URL('.', import.meta.url))

test('incident workbench uses shared theme tokens instead of inline color codes', () => {
  const files = readdirSync(folder).filter((name) => /\.(jsx?|css)$/.test(name) && !/\.test\./.test(name))
  assert.ok(files.length >= 2)
  for (const name of files) {
    const source = readFileSync(join(folder, name), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
    assert.doesNotMatch(source, /#[0-9a-fA-F]{3,8}\b/, `${name} has an inline color code`)
    assert.doesNotMatch(source, /rgba?\(/, `${name} has an inline rgb color`)
  }
})
