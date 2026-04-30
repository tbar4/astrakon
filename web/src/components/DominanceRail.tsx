// web/src/components/DominanceRail.tsx
import type { GameState } from '../types'
import type { TurnSnapshot } from '../store/gameStore'
import EscalationLadder from './EscalationLadder'

interface Props {
  gameState: GameState
  coalitionDominance: Record<string, number>
  turnHistory: TurnSnapshot[]
}

function Sparkline({ cid, turnHistory, totalTurns, color, threshold }: {
  cid: string
  turnHistory: TurnSnapshot[]
  totalTurns: number
  color: string
  threshold: number
}) {
  if (turnHistory.length < 2) return null

  const W = 100
  const H = 28

  const points = turnHistory.map((snap) => {
    const x = ((snap.turn - 1) / Math.max(totalTurns - 1, 1)) * W
    const y = H - Math.min(snap.dominance[cid] ?? 0, 1) * H
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')

  const threshY = (H - threshold * H).toFixed(1)

  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none"
      style={{ display: 'block', marginTop: 4, opacity: 0.7 }}>
      {/* threshold line */}
      <line x1="0" y1={threshY} x2={W} y2={threshY}
        stroke={color} strokeWidth="0.5" strokeDasharray="2 2" opacity="0.4" />
      {/* trend line */}
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5"
        strokeLinejoin="round" strokeLinecap="round" />
      {/* current point dot */}
      {(() => {
        const last = turnHistory[turnHistory.length - 1]
        const x = ((last.turn - 1) / Math.max(totalTurns - 1, 1)) * W
        const y = H - Math.min(last.dominance[cid] ?? 0, 1) * H
        return <circle cx={x.toFixed(1)} cy={y.toFixed(1)} r="2" fill={color} />
      })()}
    </svg>
  )
}

export default function DominanceRail({ gameState, coalitionDominance, turnHistory }: Props) {
  const { coalition_states, coalition_colors, victory_threshold, events, total_turns } = gameState

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
              <Sparkline
                cid={cid}
                turnHistory={turnHistory}
                totalTurns={total_turns}
                color={color}
                threshold={victory_threshold}
              />
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

      <EscalationLadder rung={gameState.escalation_rung ?? 0} />

      {gameState.access_windows && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontFamily: 'Courier New', fontSize: 9, color: '#334155', letterSpacing: 2, marginBottom: 4 }}>
            ACCESS WINDOWS
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {(['leo', 'meo', 'geo', 'cislunar'] as const).map((shell) => {
              const open = gameState.access_windows[shell]
              const debris = gameState.debris_fields?.[shell] ?? 0
              const color = debris >= 0.8 ? '#ef4444' : open ? '#00ff88' : '#334155'
              const label = debris >= 0.8 ? 'KESSLER' : open ? 'OPEN' : 'CLOSED'
              return (
                <div key={shell} style={{ textAlign: 'center' }}>
                  <div style={{ fontFamily: 'Courier New', fontSize: 8, color, letterSpacing: 1 }}>
                    {shell.toUpperCase()}
                  </div>
                  <div style={{ fontFamily: 'Courier New', fontSize: 7, color, marginTop: 1 }}>
                    {label}
                  </div>
                  {debris > 0 && (
                    <div style={{ fontFamily: 'Courier New', fontSize: 7, color: '#ef4444', marginTop: 1 }}>
                      {Math.round(debris * 100)}%
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
