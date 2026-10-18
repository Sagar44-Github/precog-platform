// Runs every web test: plain *.test.js files directly, and *.test.jsx files after bundling them with esbuild.
// Used by "npm test". (Owner: LEAD-CORE)
import { build } from 'esbuild'
import { spawnSync } from 'node:child_process'
import { mkdirSync, readdirSync, rmSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL('..', import.meta.url))
const src = join(root, 'src')
const out = join(root, '.test-build')

function find(dir, found = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) find(path, found)
    else if (/\.test\.jsx?$/.test(name)) found.push(path)
  }
  return found
}

rmSync(out, { recursive: true, force: true })
mkdirSync(out, { recursive: true })
const files = find(src)
const toRun = []
for (const file of files) {
  if (file.endsWith('.jsx')) {
    const target = join(out, relative(src, file).replace(/[\\/]/g, '__').replace(/\.jsx$/, '.mjs'))
    await build({
      entryPoints: [file], outfile: target, bundle: true, platform: 'node', format: 'esm', jsx: 'automatic', loader: { '.js': 'jsx' }, logLevel: 'error',
      banner: { js: "import { createRequire as __cr } from 'node:module'; const require = __cr(import.meta.url);" }
    })
    toRun.push(target)
  } else {
    toRun.push(file)
  }
}
console.log(`Running ${toRun.length} web test files`)
const result = spawnSync(process.execPath, ['--test', ...toRun], { stdio: 'inherit' })
rmSync(out, { recursive: true, force: true })
process.exit(result.status ?? 1)