import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

export function resolveProjectRoot(scriptUrl) {
  return resolve(fileURLToPath(new URL('..', scriptUrl)))
}
