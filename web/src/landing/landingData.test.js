import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { buildLandingData, checkGeneratedData, generatedText, OUTPUT_PATH, PROJECT_ROOT } from '../../scripts/build-landing-data.mjs'

test('generated landing data matches every checked repository source hash', () => {
  const result = checkGeneratedData()
  assert.equal(result.fresh, true, 'run npm run build-landing-data to refresh stale landing data')
  const data = JSON.parse(readFileSync(OUTPUT_PATH, 'utf8'))
  assert.equal(Object.keys(data.sourceHashes).length, 8)
  assert.equal(data.simulation.hostsCount, 6)
  assert.deepEqual(data.forecast.candidates.map(({ percent }) => percent), [45, 39, 16])
  assert.equal(data.simulation.attemptTechniqueId, 'T1021.004')
  assert.equal(data.simulation.blockedHit, data.forecast.top1.hostId === data.simulation.attemptedTo)
  assert.deepEqual(data.evaluation.top3, { nodeModel: 100, ruleBased: 100, uniform: 100 })
  assert.equal(data.chapters.every((chapter) => chapter.status === 'shipped'), true)
})

test('staleness check rejects a missing or edited generated data file', () => {
  const folder = mkdtempSync(join(tmpdir(), 'precog-landing-freshness-'))
  const output = join(folder, 'data.generated.json')
  try {
    const expected = generatedText(buildLandingData(PROJECT_ROOT))
    assert.equal(checkGeneratedData(PROJECT_ROOT, output).fresh, false)
    writeFileSync(output, expected)
    assert.equal(checkGeneratedData(PROJECT_ROOT, output).fresh, true)
    writeFileSync(output, expected.replace('Workstation A', 'Changed host'))
    assert.equal(checkGeneratedData(PROJECT_ROOT, output).fresh, false)
  } finally { rmSync(folder, { recursive: true, force: true }) }
})
