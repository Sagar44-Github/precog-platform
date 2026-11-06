import test from 'node:test'
import assert from 'node:assert/strict'
import { renderToStaticMarkup } from 'react-dom/server'
import { Route, Routes } from 'react-router-dom'
import { StaticRouter } from 'react-router-dom/server.js'
import { AuthProvider } from '../../shared/AuthContext.jsx'
import { ThemeProvider } from '../../shared/theme-context.jsx'
import DatasetsPage, { DatasetComparePage, DatasetDetailPage } from './index.jsx'

function render(path) {
  return renderToStaticMarkup(<StaticRouter location={path}><AuthProvider><ThemeProvider><Routes>
    <Route path="/datasets" element={<DatasetsPage />} />
    <Route path="/datasets/compare" element={<DatasetComparePage />} />
    <Route path="/datasets/:id" element={<DatasetDetailPage />} />
  </Routes></ThemeProvider></AuthProvider></StaticRouter>)
}

test('dataset directory and deep-link pages provide their workbench headings', () => {
  assert.match(render('/datasets'), /Dataset workspaces/)
  assert.match(render('/datasets/demo-6'), /Dataset details/)
  assert.match(render('/datasets/compare?left=demo-6&right=synth-enterprise-30'), /Compare dataset workspaces/)
})
