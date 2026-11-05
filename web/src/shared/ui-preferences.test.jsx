import test from 'node:test'
import assert from 'node:assert/strict'
import { renderToStaticMarkup } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom/server.js'
import { UiPreferencesProvider, useUiPreferences } from './ui-preferences.jsx'

function PreferenceView() {
  const { preferences } = useUiPreferences()
  return <p>{preferences.density}:{preferences.defaultAlertSeverity || 'ALL'}</p>
}

test('UI preferences expose comfortable density and all severities by default', () => {
  const html = renderToStaticMarkup(<StaticRouter><UiPreferencesProvider><PreferenceView /></UiPreferencesProvider></StaticRouter>)
  assert.match(html, /comfortable:ALL/)
})

test('the preferences page can use the shared provider contract', () => {
  assert.equal(typeof UiPreferencesProvider, 'function')
  assert.equal(typeof useUiPreferences, 'function')
})
