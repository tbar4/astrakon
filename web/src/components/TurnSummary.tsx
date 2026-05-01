// web/src/components/TurnSummary.tsx
import type { GameState, CombatEvent } from '../types'

interface Props {
  gameState: GameState
  coalitionDominance: Record<string, number>
  onContinue: () => void
}

export default function TurnSummary({ gameState, coalitionDominance, onContinue }: Props) {
  const { turn, total_turns, events, turn_log, coalition_states, coalition_colors, victory_threshold } = gameState

  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: 'rgba(2, 11, 24, 0.95)',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', padding: '40px 20px',
      overflowY: 'auto', zIndex: 50,
    }}>
      <div className="mono" style={{ color: '#00d4ff', fontSize: 16, letterSpacing: 6, marginBottom: 8 }}>
        ══ END OF TURN {turn} ══
      </div>
      <div className="mono" style={{ color: '#64748b', fontSize: 10, marginBottom: 32 }}>
        {total_turns - turn} turn{total_turns - turn !== 1 ? 's' : ''} remaining
      </div>

      <div style={{ width: '100%', maxWidth: 640, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {events.length > 0 && (
          <div className="panel" style={{ borderColor: 'rgba(245,158,11,0.3)' }}>
            <div className="panel-title" style={{ color: '#f59e0b' }}>◆ CRISIS EVENTS</div>
            {events.map((ev) => (
              <div key={ev.event_id} style={{ marginBottom: 8 }}>
                <div className="mono" style={{ fontSize: 11, color: '#f59e0b' }}>
                  {'█'.repeat(Math.round(ev.severity * 5))}{'░'.repeat(5 - Math.round(ev.severity * 5))} {ev.event_type.toUpperCase()}
                </div>
                <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{ev.description}</div>
              </div>
            ))}
          </div>
        )}

        {gameState.combat_events && gameState.combat_events.length > 0 && (
          <div className="panel" style={{ borderColor: 'rgba(255,68,153,0.3)' }}>
            <div className="panel-title" style={{ color: '#ff4499' }}>◆ STRIKES THIS TURN</div>
            {gameState.combat_events.map((ev: CombatEvent, i: number) => {
              const isKinetic = ev.event_type === 'kinetic'
              const color = isKinetic ? '#ff4499' : '#f59e0b'
              const arrow = isKinetic ? '→' : '⤳'
              const shellLabel = ev.shell.toUpperCase()
              const typeLabel = ev.event_type.replace(/_/g, ' ').toUpperCase()
              const attackerName = gameState.faction_states[ev.attacker_id]?.name ?? ev.attacker_id
              const targetName = gameState.faction_states[ev.target_faction_id]?.name ?? ev.target_faction_id
              return (
                <div key={i} className="mono" style={{
                  fontSize: 10, color, marginBottom: 4,
                  display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap',
                }}>
                  <span>{attackerName}</span>
                  <span>{arrow}</span>
                  <span>{targetName}</span>
                  <span style={{ opacity: 0.7 }}>[{shellLabel}]</span>
                  <span style={{ opacity: 0.7 }}>[{typeLabel}]</span>
                  {ev.nodes_destroyed > 0 && (
                    <span>−{ev.nodes_destroyed} NODES</span>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {turn_log.length > 0 && (
          <div className="panel">
            <div className="panel-title">◆ OPERATIONAL LOG</div>
            {turn_log.map((entry, i) => {
              const color = entry.includes('[KINETIC]') || entry.includes('[RETALIATION') ? '#ff4499'
                : entry.includes('disrupted') || entry.includes('gray-zone') ? '#f59e0b'
                : '#475569'
              return (
                <div key={i} className="mono" style={{ fontSize: 10, color, marginBottom: 3 }}>
                  {entry}
                </div>
              )
            })}
          </div>
        )}

        <div className="panel" style={{ borderColor: 'rgba(0,212,255,0.3)' }}>
          <div className="panel-title">◆ ORBITAL DOMINANCE</div>
          {Object.entries(coalition_states).map(([cid, cs]) => {
            const dom = coalitionDominance[cid] ?? 0
            const color = coalition_colors[cid] === 'green' ? '#00ff88' : '#ff4499'
            const gap = dom - victory_threshold
            return (
              <div key={cid} style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
                  <span className="mono" style={{ color }}>{cid} ({cs.member_ids.join(', ')})</span>
                  <span className="mono" style={{ color }}>{(dom * 100).toFixed(1)}%</span>
                  <span className="mono" style={{ color: gap >= 0 ? '#00ff88' : '#ff4499' }}>
                    {gap >= 0 ? '+' : ''}{(gap * 100).toFixed(1)}% vs threshold
                  </span>
                </div>
                <div style={{ height: 3, background: 'rgba(255,255,255,0.05)' }}>
                  <div style={{ height: '100%', width: `${Math.min(100, dom * 100)}%`, background: color }} />
                </div>
              </div>
            )
          })}
        </div>

        <button className="btn-primary" onClick={onContinue} style={{ width: '100%', fontSize: 13, padding: '12px' }}>
          [ CONTINUE TO TURN {turn + 1} ]
        </button>
      </div>
    </div>
  )
}
