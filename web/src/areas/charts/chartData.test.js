import test from 'node:test'
import assert from 'node:assert/strict'
import { CALIBRATION_CAPTION, PATTERNS, alertVolume, calibrationPoints, calibrationSummary, referenceLine, volumeSummary } from './chartData.js'

const bins = [{ bin_low: 0.7, bin_high: 0.8, mean_confidence: 0.74, observed_rate: 1, count: 1 }, { bin_low: 0.1, bin_high: 0.2, mean_confidence: 0.15, observed_rate: 0, count: 0 }]
const alert = (ts, severity) => ({ ts, severity })

test('calibration points are percentages and empty bins are left out', () => {
  assert.deepEqual(calibrationPoints({ calibration_bins: bins }), [{ x: 74, y: 100, count: 1 }])
  assert.deepEqual(calibrationPoints(null), [])
})

test('the reference line runs from 0 to 100 percent', () => {
  assert.deepEqual(referenceLine(), [{ x: 0, y: 0 }, { x: 100, y: 100 }])
})

test('the calibration summary is readable text, and honest when empty', () => {
  assert.equal(calibrationSummary({ calibration_bins: bins }), 'Calibration: stated 74 %, observed 100 % (1 forecast).')
  assert.equal(calibrationSummary({ calibration_bins: [] }), 'No forecasts resolved yet.')
  assert.match(CALIBRATION_CAPTION, /dashed line/)
})

test('alerts are counted per minute and per severity, oldest minute first', () => {
  const v = alertVolume([alert('2026-10-03T10:01:20Z', 'HIGH'), alert('2026-10-03T10:00:05Z', 'LOW'), alert('2026-10-03T10:01:50Z', 'HIGH'), alert('2026-10-03 10:01:55', 'MEDIUM')])
  assert.deepEqual(v.labels, ['10:00', '10:01'])
  assert.deepEqual(v.high, [0, 2])
  assert.deepEqual(v.medium, [0, 1])
  assert.deepEqual(v.low, [1, 0])
})

test('the volume summary and the empty case', () => {
  assert.equal(volumeSummary([]), 'No alerts yet.')
  assert.equal(volumeSummary([alert('2026-10-03T10:00:05Z', 'HIGH'), alert('2026-10-03T10:01:05Z', 'LOW')]), '2 alerts over 2 minutes: 1 high, 0 medium, 1 low.')
})

test('each severity has its own pattern so colour is not the only signal', () => {
  assert.equal(new Set(Object.values(PATTERNS)).size, 3)
})
