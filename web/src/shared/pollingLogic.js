// Small pure functions used by the polling hook, kept separate so they can be tested without a browser.

/** The display is "stale" when no successful reply has arrived for twice the polling interval. */
export function isStale(lastSuccessMs, nowMs, intervalMs) {
  if (lastSuccessMs === null || lastSuccessMs === undefined) return false
  return nowMs - lastSuccessMs > 2 * intervalMs
}

/** Builds the address to poll. since = the version already held, or null the first time. */
export function stateUrl(since) {
  return since === null || since === undefined ? '/api/x/state' : `/api/x/state?since=${since}`
}

/** Decides what to do with a reply: keep the old state, or take the new one. */
export function applyReply(previous, reply) {
  if (!reply || typeof reply.version !== 'number') return previous
  if (reply.changed === false) return previous
  return reply
}
