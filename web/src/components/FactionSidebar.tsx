// web/src/components/FactionSidebar.tsx
import type { FactionState } from '../types'

interface Props {
  factionState: FactionState
  turn: number
  totalTurns: number
  tensionLevel: number
}

export default function FactionSidebar({ factionState: fs, turn, totalTurns, tensionLevel }: Props) {
  const jfe = fs.joint_force_effectiveness
  const jfeColor = jfe >= 0.8 ? '#00ff88' : jfe >= 0.5 ? '#f59e0b' : '#ff4499'

  const assets = [
    ['LEO Nodes', fs.assets.leo_nodes, '1×'],
    ['MEO Nodes', fs.assets.meo_nodes, '2×'],
    ['GEO Nodes', fs.assets.geo_nodes, '3×'],
    ['Cislunar', fs.assets.cislunar_nodes, '4×'],
    ['ASAT-K', fs.assets.asat_kinetic, '—'],
    ['ASAT-D', fs.assets.asat_deniable, '—'],
    ['EW Jammers', fs.assets.ew_jammers, '—'],
    ['SDA Sensors', fs.assets.sda_sensors, '—'],
    ['Launch Cap.', fs.assets.launch_capacity, '—'],
  ] as const

  return (
    <div className="panel" style={{ height: '100%', overflowY: 'auto' }}>
      <div className="panel-title">◆ {fs.name}</div>

      <div className="mono" style={{ fontSize: 10, color: '#64748b', marginBottom: 8 }}>
        T{turn}/{totalTurns} · TENSION {(tensionLevel * 100).toFixed(0)}%
      </div>

      <div style={{ marginBottom: 10 }}>
        {assets.map(([label, val, weight]) => (
          <div key={label} style={{
            display: 'flex', justifyContent: 'space-between',
            fontSize: 11, padding: '2px 0', borderBottom: '1px solid #00d4ff08',
          }}>
            <span style={{ color: '#64748b' }}>{label}</span>
            <span style={{ color: '#e2e8f0', fontFamily: 'Courier New' }}>{val}</span>
            <span style={{ color: '#334155', fontSize: 10 }}>{weight}</span>
          </div>
        ))}
      </div>

      <div style={{ fontSize: 11, padding: '6px 0', borderTop: '1px solid #00d4ff11' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ color: '#64748b' }}>Budget</span>
          <span style={{ color: '#00ff88', fontFamily: 'Courier New' }}>{fs.current_budget} pts</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ color: '#64748b' }}>Deterrence</span>
          <span style={{ color: '#00d4ff', fontFamily: 'Courier New' }}>{fs.deterrence_score.toFixed(0)}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ color: '#64748b' }}>Mkt Share</span>
          <span style={{ color: '#00d4ff', fontFamily: 'Courier New' }}>{(fs.market_share * 100).toFixed(1)}%</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#64748b' }}>Joint Force</span>
          <span style={{ color: jfeColor, fontFamily: 'Courier New' }}>{(jfe * 100).toFixed(0)}%</span>
        </div>
      </div>

      {fs.deferred_returns.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div className="panel-title" style={{ fontSize: 9 }}>PENDING RETURNS</div>
          {fs.deferred_returns.map((r, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between',
              fontSize: 10, color: '#64748b', padding: '1px 0',
            }}>
              <span>{r.category === 'r_and_d' ? 'R&D' : 'Education'}</span>
              <span style={{ fontFamily: 'Courier New' }}>{r.amount} pts → T{r.turn_due}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
