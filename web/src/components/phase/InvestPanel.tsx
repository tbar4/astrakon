// web/src/components/phase/InvestPanel.tsx
import { useState, useMemo } from 'react'

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

  const preview = useMemo(() => {
    const p = (key: CategoryKey) => Math.floor(budget * allocs[key])
    const items: Array<{ label: string; color: string; soft?: boolean }> = []
    const leo = Math.floor(p('constellation') / 5)
    if (leo) items.push({ label: `+${leo} LEO`, color: '#00d4ff' })
    const meo = Math.floor(p('meo_deployment') / 12)
    if (meo) items.push({ label: `+${meo} MEO`, color: '#a78bfa' })
    const geo = Math.floor(p('geo_deployment') / 25)
    if (geo) items.push({ label: `+${geo} GEO`, color: '#c084fc' })
    const cis = Math.floor(p('cislunar_deployment') / 40)
    if (cis) items.push({ label: `+${cis} CIS`, color: '#4ade80' })
    const asat = Math.floor(p('kinetic_weapons') / 40)
    if (asat) items.push({ label: `+${asat} ASAT-K`, color: '#ff4499' })
    const deniable = Math.floor(p('covert') / 25)
    if (deniable) items.push({ label: `+${deniable} ASAT-D`, color: '#f59e0b' })
    const ew = Math.floor(p('influence_ops') / 12)
    if (ew) items.push({ label: `+${ew} EW JAM`, color: '#f59e0b' })
    const launch = Math.floor(p('launch_capacity') / 15)
    if (launch) items.push({ label: `+${launch} LAUNCH`, color: '#94a3b8' })
    const rd = p('r_and_d')
    if (rd) items.push({ label: `R&D ${rd}pts → T+3`, color: '#475569', soft: true })
    const edu = p('education')
    if (edu) items.push({ label: `EDU ${edu}pts → T+6`, color: '#475569', soft: true })
    const com = p('commercial')
    if (com) items.push({ label: `COM ${com}pts`, color: '#334155', soft: true })
    const dip = p('diplomacy')
    if (dip) items.push({ label: `DIP ${dip}pts`, color: '#334155', soft: true })
    return items
  }, [budget, allocs])

  function setAlloc(key: CategoryKey, pct: number) {
    setAllocs((prev) => ({ ...prev, [key]: Math.max(0, Math.min(1, pct)) }))
  }

  function handleSubmit() {
    onSubmit({ investment: { ...allocs, rationale } })
  }

  return (
    <div>
      <div className="panel-title">◆ INVEST PHASE — BUDGET: {budget} PTS</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <span className="mono" style={{ fontSize: 12, color: '#64748b' }}>
          USED: <span style={{ color: total > 0 ? '#00d4ff' : '#475569' }}>{usedPts} pts ({(total * 100).toFixed(0)}%)</span>
        </span>
        <span className="mono" style={{ fontSize: 12 }}>
          LEFT: <span style={{ color: remaining < 0 ? '#ff4499' : remaining < 0.1 ? '#f59e0b' : '#00ff88' }}>{remainingPts} pts ({(remaining * 100).toFixed(0)}%)</span>
        </span>
      </div>

      {CATEGORIES.map(({ key, label, desc }) => (
        <div key={key} style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 1 }}>
            <span style={{ color: '#94a3b8' }}>{label}</span>
            <span className="mono" style={{ color: '#00d4ff' }}>{(allocs[key] * 100).toFixed(0)}%</span>
          </div>
          <div style={{ fontSize: 12, color: '#475569', marginBottom: 3, lineHeight: 1.4 }}>{desc}</div>
          <input
            type="range" min={0} max={100} step={5}
            value={allocs[key] * 100}
            onChange={(e) => setAlloc(key, parseInt(e.target.value) / 100)}
            style={{ width: '100%', accentColor: '#00d4ff' }}
            disabled={disabled}
          />
          <div style={{ fontSize: 12, color: '#475569' }}>
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

      {preview.length > 0 && (
        <div style={{
          margin: '10px 0 12px', padding: '8px 10px',
          border: '1px solid #00d4ff22', borderRadius: 2, background: 'rgba(0,212,255,0.03)',
        }}>
          <div className="panel-title" style={{ fontSize: 11, marginBottom: 6 }}>◆ TURN PREVIEW</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {preview.map(({ label, color, soft }) => (
              <span key={label} style={{
                fontFamily: 'Courier New', fontSize: 11, padding: '2px 7px', borderRadius: 2,
                background: soft ? 'transparent' : `${color}18`,
                border: `1px solid ${color}44`,
                color,
                opacity: soft ? 0.7 : 1,
              }}>
                {label}
              </span>
            ))}
          </div>
        </div>
      )}

      <div style={{ marginTop: 12 }}>
        <div className="panel-title" style={{ fontSize: 11 }}>RATIONALE</div>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Strategic rationale for this investment..."
          disabled={disabled}
          style={{
            width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
            color: '#94a3b8', padding: '6px 8px', fontFamily: 'system-ui',
            fontSize: 13, resize: 'vertical', minHeight: 60, borderRadius: 2,
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
