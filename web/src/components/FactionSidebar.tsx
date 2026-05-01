// web/src/components/FactionSidebar.tsx
import React from 'react'
import type { FactionState, FactionAssets } from '../types'

type AssetKey = keyof FactionAssets

interface Props {
  factionState: FactionState
  turn: number
  totalTurns: number
  tensionLevel: number
  cumulativeAdded: Partial<Record<AssetKey, number>>
  cumulativeDestroyed: Partial<Record<AssetKey, number>>
  isJammed: boolean
}

const ASSET_ROWS: { label: string; key: AssetKey; weight: string; jammable: boolean }[] = [
  { label: 'LEO Nodes',   key: 'leo_nodes',       weight: '1×', jammable: true  },
  { label: 'MEO Nodes',   key: 'meo_nodes',       weight: '2×', jammable: true  },
  { label: 'GEO Nodes',   key: 'geo_nodes',       weight: '3×', jammable: true  },
  { label: 'Cislunar',    key: 'cislunar_nodes',  weight: '4×', jammable: true  },
  { label: 'ASAT-K',      key: 'asat_kinetic',    weight: '—',  jammable: false },
  { label: 'ASAT-D',      key: 'asat_deniable',   weight: '—',  jammable: false },
  { label: 'EW Jammers',  key: 'ew_jammers',      weight: '—',  jammable: false },
  { label: 'SDA Sensors', key: 'sda_sensors',     weight: '—',  jammable: false },
  { label: 'Launch Cap.', key: 'launch_capacity', weight: '—',  jammable: false },
]

const CELL: React.CSSProperties = { padding: '2px 0', borderBottom: '1px solid #00d4ff08' }
const MONO: React.CSSProperties = { fontFamily: 'Courier New' }

export default function FactionSidebar({ factionState: fs, turn, totalTurns, tensionLevel, cumulativeAdded, cumulativeDestroyed, isJammed }: Props) {
  const jfe = fs.joint_force_effectiveness
  const jfeColor = jfe >= 0.8 ? '#00ff88' : jfe >= 0.5 ? '#f59e0b' : '#ff4499'

  return (
    <div className="panel" style={{ overflowY: 'auto' }}>
      <div className="panel-title">◆ {fs.name}</div>

      <div className="mono" style={{ fontSize: 10, color: '#64748b', marginBottom: 8 }}>
        T{turn}/{totalTurns} · TENSION {(tensionLevel * 100).toFixed(0)}%
      </div>

      {/* Asset grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 2.2rem 2.4rem 2.4rem 1.6rem 2rem',
        columnGap: 4,
        marginBottom: 10,
      }}>
        {/* Column headers */}
        <div style={{ fontSize: 9, color: '#64748b', paddingBottom: 4 }} />
        <div style={{ fontSize: 9, color: '#64748b', textAlign: 'right', paddingBottom: 4, ...MONO }}>NOW</div>
        <div style={{ fontSize: 9, color: '#00ff8866', textAlign: 'right', paddingBottom: 4, ...MONO }}>+ADD</div>
        <div style={{ fontSize: 9, color: '#ff449966', textAlign: 'right', paddingBottom: 4, ...MONO }}>−DST</div>
        <div style={{ fontSize: 9, color: '#f59e0b66', textAlign: 'center', paddingBottom: 4, ...MONO }}>JAM</div>
        <div style={{ fontSize: 9, color: '#64748b', textAlign: 'right', paddingBottom: 4, ...MONO }}>WT</div>

        {/* Asset rows */}
        {ASSET_ROWS.map(({ label, key, weight, jammable }) => {
          const added = cumulativeAdded[key] ?? 0
          const destroyed = cumulativeDestroyed[key] ?? 0
          const jammed = jammable && isJammed
          return (
            <React.Fragment key={key}>
              <div style={{ ...CELL, color: '#64748b', fontSize: 11 }}>{label}</div>
              <div style={{ ...CELL, ...MONO, color: '#e2e8f0', fontSize: 11, textAlign: 'right' }}>{fs.assets[key]}</div>
              <div style={{ ...CELL, ...MONO, color: added > 0 ? '#00ff88' : '#475569', fontSize: 10, textAlign: 'right' }}>
                {added > 0 ? `+${added}` : '—'}
              </div>
              <div style={{ ...CELL, ...MONO, color: destroyed > 0 ? '#ff4499' : '#475569', fontSize: 10, textAlign: 'right' }}>
                {destroyed > 0 ? `-${destroyed}` : '—'}
              </div>
              <div style={{ ...CELL, ...MONO, color: jammed ? '#f59e0b' : '#475569', fontSize: 10, textAlign: 'center' }}>
                {jammed ? '◆' : '—'}
              </div>
              <div style={{ ...CELL, ...MONO, color: '#475569', fontSize: 10, textAlign: 'right' }}>{weight}</div>
            </React.Fragment>
          )
        })}
      </div>

      {/* Metrics */}
      <div style={{ fontSize: 11, padding: '6px 0', borderTop: '1px solid #00d4ff11' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ color: '#64748b' }}>Budget</span>
          <span style={{ color: '#00ff88', ...MONO }}>{fs.current_budget} pts</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ color: '#64748b' }}>Deterrence</span>
          <span style={{ color: '#00d4ff', ...MONO }}>{fs.deterrence_score.toFixed(0)}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ color: '#64748b' }}>Mkt Share</span>
          <span style={{ color: '#00d4ff', ...MONO }}>{(fs.market_share * 100).toFixed(1)}%</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#64748b' }}>Joint Force</span>
          <span style={{ color: jfeColor, ...MONO }}>{(jfe * 100).toFixed(0)}%</span>
        </div>
      </div>

      {/* Maneuver budget */}
      <div style={{ marginTop: 10, padding: '6px 0', borderTop: '1px solid #00d4ff11' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontFamily: 'Courier New', fontSize: 10, color: '#475569' }}>MANEUVER BUDGET</span>
          <span style={{ fontFamily: 'Courier New', fontSize: 11, color:
            (fs.maneuver_budget ?? 10) < 2 ? '#ef4444' :
            (fs.maneuver_budget ?? 10) < 5 ? '#f59e0b' : '#00d4ff'
          }}>
            {(fs.maneuver_budget ?? 10).toFixed(1)} DV
          </span>
        </div>
        <div style={{ height: 3, background: '#0f1c2d', marginTop: 4, borderRadius: 2 }}>
          <div style={{
            height: '100%', borderRadius: 2,
            width: `${Math.min(((fs.maneuver_budget ?? 10) / 20) * 100, 100)}%`,
            background: (fs.maneuver_budget ?? 10) < 2 ? '#ef4444' :
                        (fs.maneuver_budget ?? 10) < 5 ? '#f59e0b' : '#00d4ff',
            transition: 'width 0.3s',
          }} />
        </div>
      </div>

      {/* Cognitive penalty — only shown when significant */}
      {(fs.cognitive_penalty ?? 0) > 0.1 && (
        <div style={{ marginTop: 6, display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ fontFamily: 'Courier New', fontSize: 10, color: '#f97316' }}>COGNITIVE DEGRADATION</span>
          <span style={{ fontFamily: 'Courier New', fontSize: 10, color: '#f97316' }}>
            {Math.round((fs.cognitive_penalty ?? 0) * 100)}%
          </span>
        </div>
      )}

      {fs.deferred_returns.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div className="panel-title" style={{ fontSize: 9 }}>PENDING RETURNS</div>
          {fs.deferred_returns.map((r, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#64748b', padding: '1px 0' }}>
              <span>{r.category === 'r_and_d' ? 'R&D' : 'Education'}</span>
              <span style={MONO}>{r.amount} pts → T{r.turn_due}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
