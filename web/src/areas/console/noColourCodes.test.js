import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

// UI/UX brief check 1: no colour code in a screen file. VIZ's three folders and the service worker are checked.
const here = fileURLToPath(new URL('.', import.meta.url))
const folders = [here, join(here, '..', 'charts'), join(here, '..', 'push'), join(here, '..', '..', '..', 'public', 'push')]

test('no colour codes in the console, charts or push code', () => {
  let checked = 0
  for (const folder of folders) {
    for (const file of readdirSync(folder).filter((f) => /\.(jsx?|css)$/.test(f) && !/\.test\./.test(f))) {
      const text = readFileSync(join(folder, file), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
      assert.doesNotMatch(text, /#[0-9a-fA-F]{3,8}\b/, `${file} contains a colour code`)
      assert.doesNotMatch(text, /rgba?\(/, `${file} contains an rgb() colour`)
      checked += 1
    }
  }
  assert.ok(checked >= 12)
})
