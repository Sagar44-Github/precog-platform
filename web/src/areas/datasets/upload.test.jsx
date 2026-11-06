import test from 'node:test'
import assert from 'node:assert/strict'
import { renderToStaticMarkup } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom/server.js'
import { AuthProvider } from '../../shared/AuthContext.jsx'
import { ThemeProvider } from '../../shared/theme-context.jsx'
import DatasetUploadPage from './upload.jsx'

test('upload wizard explains accepted inputs, rights acknowledgement, and simulation limits', () => {
  const html = renderToStaticMarkup(<StaticRouter location="/datasets/upload"><AuthProvider><ThemeProvider><DatasetUploadPage /></ThemeProvider></AuthProvider></StaticRouter>)
  assert.match(html, /Upload a dataset/)
  assert.match(html, /validated pack ZIP, UTF-8 CSV\/TSV, or a JSON array/)
  assert.match(html, /permission to process this file/)
  assert.match(html, /No uploaded data is executed/)
})
