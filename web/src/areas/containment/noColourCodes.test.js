import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const folder = dirname(fileURLToPath(import.meta.url))

test('response governance styles use shared theme tokens instead of screen-level color codes', () => {
  for (const file of readdirSync(folder).filter((name) => name.endsWith('.css') || name.endsWith('.jsx'))) {
    const source = readFileSync(join(folder, file), 'utf8')
    assert.doesNotMatch(source, /#[0-9a-f]{3,8}\b/i, `${file} contains a hard-coded color`)
  }
})
