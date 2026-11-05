export function allowedPlaybooksForRole(playbooks, role) {
  return (Array.isArray(playbooks) ? playbooks : []).filter((item) => Array.isArray(item.allowed_roles) && item.allowed_roles.includes(role))
}

export function previewProbabilityPercent(preview, playbookId) {
  if (!preview) return 0
  const value = playbookId === 'release-host' ? preview.probability_restored : preview.probability_removed
  return Math.round((Number(value) || 0) * 100)
}

export function filterGovernanceRecords(records, statusFilter, playbookFilter = 'all') {
  const combined = [...(records?.approvals || []), ...(records?.releases || [])]
    .sort((a, b) => String(b.proposed_at).localeCompare(String(a.proposed_at)))
  return combined.filter((item) => (statusFilter === 'all' || item.status === statusFilter)
    && (playbookFilter === 'all' || item.playbook_id === playbookFilter))
}
