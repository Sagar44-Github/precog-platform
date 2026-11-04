import assert from 'node:assert/strict'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import { resolveProjectRoot } from './path-utils.mjs'

test('test runner resolves a project path containing spaces', (t) => {
  const parent = mkdtempSync(join(tmpdir(), 'precog project with spaces-'))
  t.after(() => rmSync(parent, { recursive: true, force: true }))

  const webRoot = join(parent, 'web app')
  const runner = join(webRoot, 'scripts', 'run-tests.mjs')
  assert.equal(resolveProjectRoot(pathToFileURL(runner).href), webRoot)
})
