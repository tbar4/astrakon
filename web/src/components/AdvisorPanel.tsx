// web/src/components/AdvisorPanel.tsx
import type { Recommendation, Phase } from '../types'

interface Props {
  recommendation: Recommendation | null
  phase: Phase
  onAccept: () => void
  onDismiss: () => void
}

export default function AdvisorPanel({ recommendation: rec, phase, onAccept, onDismiss }: Props) {
  if (!rec) return null

  let summary = ''
  if (phase === 'invest' && rec.top_recommendation.investment) {
    const inv = rec.top_recommendation.investment
    const top = Object.entries(inv)
      .filter(([k, v]) => k !== 'rationale' && typeof v === 'number' && v > 0)
      .sort(([, a], [, b]) => (b as number) - (a as number))
      .slice(0, 3)
      .map(([k, v]) => `${k}: ${((v as number) * 100).toFixed(0)}%`)
    summary = top.join(' · ')
  } else if (phase === 'operations' && rec.top_recommendation.operations?.[0]) {
    const op = rec.top_recommendation.operations[0]
    summary = `${op.action_type}${op.target_faction ? ` → ${op.target_faction}` : ''}`
  } else if (phase === 'response' && rec.top_recommendation.response) {
    summary = rec.top_recommendation.response.escalate ? 'ESCALATE' : 'Stand down'
  }

  return (
    <div className="panel" style={{ borderColor: 'rgba(245,158,11,0.4)', marginBottom: 12 }}>
      <div className="panel-title" style={{ color: '#f59e0b' }}>◆ AI ADVISOR RECOMMENDATION</div>
      {summary && (
        <div className="mono" style={{ fontSize: 11, color: '#e2e8f0', marginBottom: 6 }}>{summary}</div>
      )}
      <div style={{ fontSize: 10, color: '#64748b', marginBottom: 10 }}>{rec.strategic_rationale}</div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn-primary" onClick={onAccept} style={{ flex: 1, fontSize: 10 }}>
          [ ACCEPT ]
        </button>
        <button className="btn-primary" onClick={onDismiss}
          style={{ flex: 1, fontSize: 10, borderColor: '#334155', color: '#64748b' }}>
          [ DISMISS ]
        </button>
      </div>
    </div>
  )
}
