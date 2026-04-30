// web/src/components/phase/InvestPanel.tsx
import { useState } from 'react'

interface Props {
  budget: number
  onSubmit: (decision: Record<string, unknown>) => void
  disabled: boolean
}

const CATEGORIES = [
  { key: 'constellation', label: 'LEO Constellation (5 pts/node)' },
  { key: 'meo_deployment', label: 'MEO Deployment (12 pts/node, 2×)' },
  { key: 'geo_deployment', label: 'GEO Deployment (25 pts/node, 3×)' },
  { key: 'cislunar_deployment', label: 'Cislunar (40 pts/node, 4×)' },
  { key: 'r_and_d', label: 'R&D (payoff in 3 turns)' },
  { key: 'commercial', label: 'Commercial (market share)' },
  { key: 'influence_ops', label: 'Influence Ops' },
  { key: 'covert', label: 'Covert' },
  { key: 'diplomacy', label: 'Diplomacy' },
  { key: 'education', label: 'Education (payoff in 6 turns)' },
  { key: 'launch_capacity', label: 'Launch Capacity' },
] as const

type CategoryKey = typeof CATEGORIES[number]['key']

export default function InvestPanel({ budget, onSubmit, disabled }: Props) {
  const [allocs, setAllocs] = useState<Record<CategoryKey, number>>(
    Object.fromEntries(CATEGORIES.map((c) => [c.key, 0])) as Record<CategoryKey, number>
  )
  const [rationale, setRationale] = useState('')

  const total = Object.values(allocs).reduce((a, b) => a + b, 0)
  const remaining = 1.0 - total
  const isValid = total <= 1.001 && rationale.trim().length > 0

  function setAlloc(key: CategoryKey, pct: number) {
    setAllocs((prev) => ({ ...prev, [key]: Math.max(0, Math.min(1, pct)) }))
  }

  function handleSubmit() {
    onSubmit({
      investment: { ...allocs, rationale },
    })
  }

  return (
    <div>
      <div className="panel-title">◆ INVEST PHASE — BUDGET: {budget} PTS</div>
      <div className="mono" style={{ fontSize: 10, color: remaining < 0 ? '#ff4499' : '#64748b', marginBottom: 12 }}>
        ALLOCATED: {(total * 100).toFixed(0)}% · REMAINING: {(remaining * 100).toFixed(0)}%
      </div>

      {CATEGORIES.map(({ key, label }) => (
        <div key={key} style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
            <span style={{ color: '#94a3b8' }}>{label}</span>
            <span className="mono" style={{ color: '#00d4ff' }}>{(allocs[key] * 100).toFixed(0)}%</span>
          </div>
          <input
            type="range" min={0} max={100} step={5}
            value={allocs[key] * 100}
            onChange={(e) => setAlloc(key, parseInt(e.target.value) / 100)}
            style={{ width: '100%', accentColor: '#00d4ff' }}
            disabled={disabled}
          />
          <div style={{ fontSize: 10, color: '#334155' }}>
            ≈ {Math.floor(budget * allocs[key])} pts →{' '}
            {key === 'constellation' && `${Math.floor(budget * allocs[key] / 5)} LEO nodes`}
            {key === 'meo_deployment' && `${Math.floor(budget * allocs[key] / 12)} MEO nodes`}
            {key === 'geo_deployment' && `${Math.floor(budget * allocs[key] / 25)} GEO nodes`}
            {key === 'cislunar_deployment' && `${Math.floor(budget * allocs[key] / 40)} cislunar nodes`}
          </div>
        </div>
      ))}

      <div style={{ marginTop: 12 }}>
        <div className="panel-title" style={{ fontSize: 9 }}>RATIONALE</div>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Strategic rationale for this investment..."
          disabled={disabled}
          style={{
            width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
            color: '#94a3b8', padding: '6px 8px', fontFamily: 'system-ui',
            fontSize: 12, resize: 'vertical', minHeight: 60, borderRadius: 2,
            boxSizing: 'border-box',
          }}
        />
      </div>

      <button
        className="btn-primary"
        onClick={handleSubmit}
        disabled={disabled || !isValid || remaining < -0.001}
        style={{ marginTop: 12, width: '100%' }}
      >
        [ SUBMIT INVESTMENT ]
      </button>
    </div>
  )
}
