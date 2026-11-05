import { createHash } from 'node:crypto'
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const PROJECT_ROOT = resolve(fileURLToPath(new URL('../..', import.meta.url)))
export const OUTPUT_PATH = resolve(PROJECT_ROOT, 'web/src/landing/data.generated.json')

const INPUTS = {
  scenario: 'graph/graph_replay/scenarios/golden-path.json',
  evaluation: 'lead-core/precog/results/precog_evaluation.json',
  nodeModel: 'lead-core/precog/precog_engine/data/node_model.json',
  detection: 'detect/offline_model/results/detection_report.json',
  hosts: 'contracts/data/hosts.json',
  topology: 'graph/graph_net/data/topology.json',
  techniques: 'detect/detect_events/data/attack_techniques.json',
  config: 'web/landing.config.json',
}

const CHAPTER_COPY = [
  { id: 'detect', label: 'Detect', title: 'A packet becomes evidence.', body: 'Scripted traffic enters the detector. The replay marks the compromised host in plain view.', status: 'shipped' },
  { id: 'reconstruct', label: 'Reconstruct', title: 'The path records what changed.', body: 'Read the observed compromise separately from the attempted move. ATT&CK labels describe the scripted events.', status: 'shipped' },
  { id: 'forecast', label: 'Forecast', title: 'Three reachable futures, ranked.', body: 'The model ranks feasible next hosts from repository transition counts. Each share is derived from those counts.', status: 'shipped' },
  { id: 'act', label: 'Act', title: 'A proposal is not an action.', body: 'Review the predicted target, then confirm the simulated response. No real network is changed.', status: 'shipped' },
  { id: 'reevaluate', label: 'Re-evaluate', title: 'The blocked move resolves as a hit.', body: 'The forecast is scored against the observed replay. Held-out evaluations also include misses.', status: 'shipped' },
  { id: 'evidence', label: 'Evidence', title: 'Read the numbers with their limits.', body: 'These results come from held-out or public sample data. They do not establish live detection or protection quality.', status: 'shipped' },
  { id: 'enter', label: 'Enter', title: 'A closed loop, ready to replay.', body: 'Detect, forecast, act, and re-evaluate in one scripted demonstration.', status: 'shipped' },
]

function jsonInput(root, relativePath) {
  const path = resolve(root, relativePath)
  const bytes = readFileSync(path)
  return { value: JSON.parse(bytes.toString('utf8')), sha256: createHash('sha256').update(bytes).digest('hex') }
}

function percent(value, digits = 1) {
  return Number((value * 100).toFixed(digits))
}

function attackRates(notes) {
  const match = notes.match(/WITHOUT it:\s*(.*?)(?:\. This is|$)/i)
  if (!match) throw new Error('Detection report has no unseen-attack limitation to display.')
  const rates = [...match[1].matchAll(/([A-Za-z][A-Za-z0-9]*)\s+(0(?:\.\d+)?)/g)]
    .map(([, attack, rate]) => ({ attack, rate: Number(rate), percent: percent(Number(rate), 0) }))
  if (!rates.length) throw new Error('Could not parse unseen-attack rates from the detection report.')
  return { rates, min: Math.min(...rates.map((item) => item.percent)), max: Math.max(...rates.map((item) => item.percent)) }
}

export function buildLandingData(root = PROJECT_ROOT) {
  const source = Object.fromEntries(Object.entries(INPUTS).map(([key, path]) => [key, jsonInput(root, path)]))
  const scenario = source.scenario.value
  const model = source.nodeModel.value
  const evaluations = source.evaluation.value
  const detector = source.detection.value
  const hosts = source.hosts.value.hosts
  const techniques = source.techniques.value
  const entryHost = scenario.events.find((event) => event.compromise)?.host
  const attemptedMove = scenario.events.find((event) => event.kind === 'attempt')
  if (!entryHost || !attemptedMove) throw new Error('Golden Path scenario must include a compromise and a host attempt.')

  const feasible = source.topology.value.feasible_connections[entryHost] || []
  const transitions = model.counts[entryHost] || {}
  const alpha = Number(model.alpha)
  const denominator = feasible.reduce((sum, hostId) => sum + Number(transitions[hostId] || 0) + alpha, 0)
  if (!feasible.length || denominator <= 0) throw new Error(`No Markov candidates are available for ${entryHost}.`)
  const forecast = feasible.map((hostId) => {
    const host = hosts.find((item) => item.host_id === hostId)
    const count = Number(transitions[hostId] || 0)
    const confidence = (count + alpha) / denominator
    return { hostId, name: host?.name || hostId, transitionCount: count, confidence, percent: percent(confidence, 0) }
  }).sort((a, b) => b.confidence - a.confidence)

  const techniqueById = new Map((techniques.techniques || []).map((item) => [item.id, item]))
  const scenarioTechniques = scenario.events.filter((event) => event.technique_id).map((event) => {
    const technique = techniqueById.get(event.technique_id)
    return { id: event.technique_id, name: technique?.name || event.technique_id, tactic: technique?.tactics?.[0] || 'technique', event: event.note || '' }
  })
  const goldenPathPackets = scenario.events.filter((event) => event.kind === 'traffic').flatMap((event) => event.packets || [])
  const packetCount = goldenPathPackets.reduce((sum, packet) => sum + Number(packet.repeat || 1), 0)

  const baselineData = (entry) => ({
    value: entry.precision_at_1,
    percent: percent(entry.precision_at_1, 1),
    standardError: entry.precision_at_1_std_error,
    standardErrorPercent: percent(entry.precision_at_1_std_error, 1),
    forecasts: entry.forecasts,
    precisionAt3: entry.precision_at_3,
  })
  const precisions = [evaluations.node_model.precision_at_3, evaluations.baseline_rule_based.precision_at_3, evaluations.baseline_uniform.precision_at_3]
  const sourceHashes = Object.fromEntries(Object.entries(source).map(([key, item]) => [INPUTS[key], item.sha256]))
  const zones = [...new Set(hosts.map((host) => host.zone))]
  const nodes = hosts.map((host, index) => ({ ...host, index }))
  const slots = { user: [[-5, -1.6], [-5, 1.6]], dmz: [[0, 0]], internal: [[5, -3], [6.8, 0], [5, 3]] }
  const slotUse = { user: 0, dmz: 0, internal: 0 }
  for (const host of nodes) {
    const zoneSlots = slots[host.zone] || [[0, 0]]
    host.position = zoneSlots[Math.min(slotUse[host.zone] || 0, zoneSlots.length - 1)]
    slotUse[host.zone] = (slotUse[host.zone] || 0) + 1
  }
  const edges = []
  for (const [from, targets] of Object.entries(source.topology.value.feasible_connections)) {
    for (const to of targets) {
      const edge = [from, to].sort().join('::')
      if (!edges.some((item) => item.key === edge)) edges.push({ key: edge, from, to })
    }
  }
  const rate = attackRates(detector.notes)
  const hostsCount = hosts.length

  return {
    schemaVersion: 1,
    sourceHashes,
    simulation: {
      label: 'SIMULATION',
      scenarioId: scenario.scenario_id,
      scenarioDescription: scenario.description,
      packetCount,
      hostsCount,
      zones,
      hosts: nodes,
      edges,
      trafficEdges: goldenPathPackets.map((packet) => ({ from: packet.src_host, to: packet.dst_host, repeat: Number(packet.repeat || 1) })),
      entryHost,
      attemptedFrom: attemptedMove.from_host,
      attemptedTo: attemptedMove.to_host,
      attemptTechniqueId: attemptedMove.technique_id || null,
      compromiseTechniqueId: scenario.events.find((event) => event.compromise)?.technique_id || null,
      blockedHit: forecast[0]?.hostId === attemptedMove.to_host,
    },
    forecast: {
      source: model.meta.generator,
      alpha,
      candidates: forecast,
      top1: forecast[0],
    },
    techniques: scenarioTechniques,
    evaluation: {
      heldOutForecasts: evaluations.node_model.forecasts,
      top1: baselineData(evaluations.node_model),
      ruleBased: baselineData(evaluations.baseline_rule_based),
      uniform: baselineData(evaluations.baseline_uniform),
      allTop3One: precisions.every((value) => value === 1),
      top3Percent: percent(evaluations.node_model.precision_at_3, 1),
      top3: {
        nodeModel: percent(evaluations.node_model.precision_at_3, 1),
        ruleBased: percent(evaluations.baseline_rule_based.precision_at_3, 1),
        uniform: percent(evaluations.baseline_uniform.precision_at_3, 1),
      },
      maxCandidates: Math.max(evaluations.node_model.max_candidates, evaluations.baseline_rule_based.max_candidates, evaluations.baseline_uniform.max_candidates),
      notes: evaluations.notes,
    },
    detection: {
      model: detector.model,
      dataset: detector.dataset,
      precision: detector.precision,
      precisionPercent: percent(detector.precision, 2),
      recall: detector.recall,
      recallPercent: percent(detector.recall, 2),
      f1: detector.f1,
      f1Percent: percent(detector.f1, 2),
      falsePositiveRate: detector.false_positive_rate,
      falsePositivePercent: percent(detector.false_positive_rate, 2),
      split: detector.split,
      unseenAttackRates: rate.rates,
      unseenRateMinPercent: rate.min,
      unseenRateMaxPercent: rate.max,
      notes: detector.notes,
    },
    chapters: CHAPTER_COPY.filter((chapter) => chapter.status === 'shipped').map((chapter, index) => ({ number: String(index + 1).padStart(2, '0'), ...chapter })),
    credits: source.config.value,
    attribution: {
      mitreNotice: techniques.notice,
      attackgraph: 'attackgraph; MIT License.',
      networkx: 'NetworkX; BSD-3-Clause License.',
      three: 'Three.js; MIT License.',
      nids: '123dars/NIDS; MIT License.',
    },
    copy: {
      promise: 'See where the attacker goes next, before they get there.',
      product: 'Precog SOC detects an intrusion, reconstructs how it spread, forecasts the next host, and lets an analyst contain it in two confirmed steps. Everything you see is a simulation.',
    },
  }
}

export function generatedText(data) {
  return `${JSON.stringify(data, null, 2)}\n`
}

export function checkGeneratedData(root = PROJECT_ROOT, outputPath = OUTPUT_PATH) {
  const expected = generatedText(buildLandingData(root))
  let current
  try { current = readFileSync(outputPath, 'utf8') } catch { return { fresh: false, expected } }
  return { fresh: current === expected, expected }
}

const isEntryPoint = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (isEntryPoint) {
  const checkOnly = process.argv.includes('--check')
  const outputPath = OUTPUT_PATH
  const expected = generatedText(buildLandingData())
  if (checkOnly) {
    let current = ''
    try { current = readFileSync(outputPath, 'utf8') } catch {}
    if (current !== expected) {
      console.error('Landing data is missing or stale. Run: npm run build-landing-data')
      process.exitCode = 1
    } else console.log('Landing data is current.')
  } else {
    mkdirSync(dirname(outputPath), { recursive: true })
    writeFileSync(outputPath, expected, 'utf8')
    console.log(`Wrote ${outputPath}`)
  }
}
