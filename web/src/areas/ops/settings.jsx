import { ThemeToggle, useTheme } from '../../shared/theme-context.jsx'
import { useUiPreferences } from '../../shared/ui-preferences.jsx'
import { Field, PageFrame, PageHeader } from './shared.jsx'

export default function SettingsPage() {
  const { theme } = useTheme()
  const { preferences, setPreference } = useUiPreferences()
  return <PageFrame>
    <PageHeader eyebrow="OPERATOR / DISPLAY PREFERENCES" title="Settings" description="Preferences are stored in this browser. These controls change presentation only and do not modify detection or forecast thresholds." />
    <div className="ops-settings-layout">
      <section className="ops-card"><div className="ops-card-header"><div><h3>Display</h3><p>Theme and density for operational tables</p></div></div><div className="ops-card-body">
        <div className="ops-setting-row"><div><h3>Color theme</h3><p>Current theme: {theme}. The preference is stored on this device.</p></div><div className="ops-setting-control"><ThemeToggle /></div></div>
        <div className="ops-setting-row"><div><h3>Data density</h3><p>Controls row spacing in alert, asset, and audit tables.</p></div><div className="ops-setting-control"><Field label="Row spacing"><select value={preferences.density} onChange={(event) => setPreference('density', event.target.value)}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></Field></div></div>
      </div></section>
      <section className="ops-card"><div className="ops-card-header"><div><h3>Alert review</h3><p>Default severity filter when opening the alert workspace</p></div></div><div className="ops-card-body">
        <div className="ops-setting-row"><div><h3>Default severity</h3><p>Applies as an initial view preference. Analysts can change it at any time.</p></div><div className="ops-setting-control"><Field label="Severity"><select value={preferences.defaultAlertSeverity} onChange={(event) => setPreference('defaultAlertSeverity', event.target.value)}><option value="">All severities</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option><option value="NORMAL">Normal</option></select></Field></div></div>
      </div></section>
      <p className="ops-simulated-note">Settings are local display preferences. Alert colors communicate event severity, violet indicates predictions, and teal indicates simulated analyst actions.</p>
    </div>
  </PageFrame>
}
