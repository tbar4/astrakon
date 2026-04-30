// web/src/components/DominanceRail.tsx
import type { GameState } from '../types'

interface Props {
  gameState: GameState
  coalitionDominance: Record<string, number>
}

export default function DominanceRail({ gameState, coalitionDominance }: Props) {
  const { coalition_states, coalition_colors, victory_threshold, events } = gameState

  return (
    <div className="panel" style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div>
        <div className="panel-title">◆ DOMINANCE</div>
        {Object.entries(coalition_states).map(([cid, cs]) => {
          const dom = coalitionDominance[cid] ?? 0
          const color = coalition_colors[cid] === 'green' ? '#00ff88' : '#ff4499'
          const barWidth = Math.min(100, dom * 100)
          const gap = dom - victory_threshold
          return (
            <div key={cid} style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 3 }}>
                <span className="mono" style={{ color }}>{cid}</span>
                <span className="mono" style={{ color }}>{(dom * 100).toFixed(1)}%</span>
              </div>
              <div style={{ height: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${barWidth}%`,
                  background: color, transition: 'width 0.5s',
                  boxShadow: `0 0 6px ${color}`,
                }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, marginTop: 2 }}>
                <span style={{ color: '#334155' }}>{cs.member_ids.join(', ')}</span>
                <span style={{ color: gap >= 0 ? '#00ff88' : '#ff4499' }}>
                  {gap >= 0 ? '+' : ''}{(gap * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          )
        })}
        <div style={{ fontSize: 9, color: '#334155', borderTop: '1px solid #00d4ff11', paddingTop: 6 }}>
          WIN THRESHOLD: {(victory_threshold * 100).toFixed(0)}%
        </div>
      </div>

      {events.length > 0 && (
        <div>
          <div className="panel-title" style={{ color: '#f59e0b' }}>◆ CRISIS EVENTS</div>
          {events.map((ev) => (
            <div key={ev.event_id} style={{ fontSize: 10, marginBottom: 6, padding: '4px 0', borderBottom: '1px solid #f59e0b11' }}>
              <div style={{ color: '#f59e0b', fontFamily: 'Courier New', marginBottom: 2 }}>
                {'█'.repeat(Math.round(ev.severity * 5))}{'░'.repeat(5 - Math.round(ev.severity * 5))} {ev.event_type.toUpperCase()}
              </div>
              <div style={{ color: '#64748b' }}>{ev.description}</div>
            </div>
          ))}
        </div>
      )}

    </div>
  )
}
