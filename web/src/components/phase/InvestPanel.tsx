// web/src/components/phase/InvestPanel.tsx
import { useState } from 'react'

interface Props {
  budget: number
  onSubmit: (decision: Record<string, unknown>) => void
  disabled: boolean
}

const CATEGORIES = [
  { key: 'constellation', label: 'LEO Constellation (5 pts/node)', desc: 'Cheap, high-volume nodes in Low Earth Orbit. Core of SDA coverage and comms. Most vulnerable to kinetic ASAT attack.' },
  { key: 'meo_deployment', label: 'MEO Deployment (12 pts/node, 2×)', desc: 'GPS & navigation band. Harder to target than LEO. 2× orbital dominance weight. Key for precision strike support.' },
  { key: 'geo_deployment', label: 'GEO Deployment (25 pts/node, 3×)', desc: 'Geostationary comms relays & missile-warning satellites. 3× dominance weight. Very costly to replace once destroyed.' },
  { key: 'cislunar_deployment', label: 'Cislunar (40 pts/node, 4×)', desc: 'Nodes in cis-lunar space. 4× dominance weight. Controls future space economy. Beyond most ASAT range.' },
  { key: 'r_and_d', label: 'R&D (payoff in 3 turns)', desc: 'Budget invested now returns with interest in 3 turns. No immediate tactical effect — plan ahead.' },
  { key: 'commercial', label: 'Commercial (market share)', desc: 'Expand satellite services revenue. Grows budget-per-turn income over time through market share gains.' },
  { key: 'influence_ops', label: 'Influence Ops', desc: 'Information & psychological operations. Erodes adversary coalition loyalty and undermines public support.' },
  { key: 'covert', label: 'Covert', desc: 'Deniable cyber and space operations. Builds ASAT-deniable capacity to act without triggering formal escalation.' },
  { key: 'kinetic_weapons', label: 'Kinetic Weapons (40 pts/weapon)', desc: '⚠ Direct-ascent interceptors. One-use weapons that destroy enemy satellite nodes. Creates orbital debris and triggers escalation.' },
  { key: 'diplomacy', label: 'Diplomacy', desc: 'Alliance-building and coalition maintenance. Strengthens partner loyalty and enables coordination bonuses.' },
  { key: 'education', label: 'Education (payoff in 6 turns)', desc: 'Workforce & doctrine investment. Highest return multiplier but 6-turn delay. Best for extended campaigns.' },
  { key: 'launch_capacity', label: 'Launch Capacity', desc: 'Ground-based launch infrastructure. Expands how many satellite nodes you can deploy per turn.' },
] as const

type CategoryKey = typeof CATEGORIES[number]['key']

export default function InvestPanel({ budget, onSubmit, disabled }: Props) {
  const [allocs, setAllocs] = useState<Record<CategoryKey, number>>(
    Object.fromEntries(CATEGORIES.map((c) => [c.key, 0])) as Record<CategoryKey, number>
  )
  const [rationale, setRationale] = useState('')

  const total = Object.values(allocs).reduce((a, b) => a + b, 0)
  const remaining = 1.0 - total
  const usedPts = Math.round(total * budget)
  const remainingPts = budget - usedPts
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
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <span className="mono" style={{ fontSize: 10, color: '#64748b' }}>
          USED: <span style={{ color: total > 0 ? '#00d4ff' : '#334155' }}>{usedPts} pts ({(total * 100).toFixed(0)}%)</span>
        </span>
        <span className="mono" style={{ fontSize: 10 }}>
          LEFT: <span style={{ color: remaining < 0 ? '#ff4499' : remaining < 0.1 ? '#f59e0b' : '#00ff88' }}>{remainingPts} pts ({(remaining * 100).toFixed(0)}%)</span>
        </span>
      </div>

      {CATEGORIES.map(({ key, label, desc }) => (
        <div key={key} style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 1 }}>
            <span style={{ color: '#94a3b8' }}>{label}</span>
            <span className="mono" style={{ color: '#00d4ff' }}>{(allocs[key] * 100).toFixed(0)}%</span>
          </div>
          <div style={{ fontSize: 9, color: '#334155', marginBottom: 3, lineHeight: 1.4 }}>{desc}</div>
          <input
            type="range" min={0} max={100} step={5}
            value={allocs[key] * 100}
            onChange={(e) => setAlloc(key, parseInt(e.target.value) / 100)}
            style={{ width: '100%', accentColor: '#00d4ff' }}
            disabled={disabled}
          />
          <div style={{ fontSize: 10, color: '#334155' }}>
            {(() => {
              const pts = Math.floor(budget * allocs[key])
              if (pts === 0) return null
              const nodeHint =
                key === 'constellation' ? `→ ${Math.floor(pts / 5)} LEO nodes` :
                key === 'meo_deployment' ? `→ ${Math.floor(pts / 12)} MEO nodes` :
                key === 'geo_deployment' ? `→ ${Math.floor(pts / 25)} GEO nodes` :
                key === 'cislunar_deployment' ? `→ ${Math.floor(pts / 40)} cislunar nodes` : ''
              return `≈ ${pts} pts ${nodeHint}`
            })()}
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
