import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

// UI/UX brief check 1: no colour code appears in a screen file. Colours only come from theme.css variables.
const folder = fileURLToPath(new URL('.', import.meta.url))

test('no colour codes in the phone screens or their styles', () => {
  const files = readdirSync(folder).filter((f) => /\.(jsx?|css)$/.test(f) && !/\.test\./.test(f))
  assert.ok(files.length >= 5)
  for (const file of files) {
    const text = readFileSync(join(folder, file), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
    assert.doesNotMatch(text, /#[0-9a-fA-F]{3,8}\b/, `${file} contains a colour code`)
    assert.doesNotMatch(text, /rgba?\(/, `${file} contains an rgb() colour`)
  }
})
