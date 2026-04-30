// web/src/components/OpsTab.tsx
import type { GameState } from '../types'
import type { TurnSnapshot } from '../store/gameStore'
import EscalationLadder from './EscalationLadder'

interface Props {
  gameState: GameState
  coalitionDominance: Record<string, number>
  turnHistory: TurnSnapshot[]
}

const ESCALATION_LABELS = [
  'PEACETIME', 'CONTESTED', 'DEGRADED', 'THRESHOLD', 'KINETIC', 'ESCALATORY',
]
const ESCALATION_COLORS = ['#00ff88', '#64748b', '#f59e0b', '#f97316', '#ef4444', '#ff4499']

function OpsSparklines({ turnHistory, coalitionColors }: {
  turnHistory: TurnSnapshot[]
  coalitionColors: Record<string, string>
}) {
  if (turnHistory.length < 2) return null
  const W = 200
  const H = 32
  const coalitions = Object.keys(turnHistory[turnHistory.length - 1].dominance)
  const totalTurns = Math.max(turnHistory.length - 1, 1)

  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none"
      style={{ display: 'block', marginTop: 4 }}>
      {coalitions.map((cid) => {
        const color = coalitionColors[cid] === 'green' ? '#00ff88' : '#ff4499'
        const points = turnHistory.map((snap, i) => {
          const x = (i / totalTurns) * W
          const y = H - Math.min(snap.dominance[cid] ?? 0, 1) * H
          return `${x.toFixed(1)},${y.toFixed(1)}`
        }).join(' ')
        const last = turnHistory[turnHistory.length - 1]
        const lx = ((turnHistory.length - 1) / totalTurns) * W
        const ly = H - Math.min(last.dominance[cid] ?? 0, 1) * H
        return (
          <g key={cid}>
            <polyline points={points} fill="none" stroke={color} strokeWidth="1.5"
              strokeLinejoin="round" strokeLinecap="round" opacity={0.7} />
            <circle cx={lx.toFixed(1)} cy={ly.toFixed(1)} r="2" fill={color} />
          </g>
        )
      })}
    </svg>
  )
}

const SHELL_LABELS: Record<string, string> = { leo: 'LEO', meo: 'MEO', geo: 'GEO', cislunar: 'CIS' }

export default function OpsTab({ gameState, coalitionDominance, turnHistory }: Props) {
  void coalitionDominance
  const rung = gameState.escalation_rung ?? 0
  const rungColor = ESCALATION_COLORS[Math.min(rung, 5)]
  const threats = gameState.human_snapshot?.incoming_threats ?? []

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* SITUATION */}
      <div>
        <div className="panel-title">◆ SITUATION</div>

        {/* Access windows */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          {(['leo', 'meo', 'geo', 'cislunar'] as const).map((shell) => {
            const open = gameState.access_windows?.[shell] ?? true
            const debris = gameState.debris_fields?.[shell] ?? 0
            const kessler = debris >= 0.8
            const color = kessler ? '#ef4444' : open ? '#00ff88' : '#334155'
            const label = kessler ? 'KESSLER' : open ? 'OPEN' : 'CLOSED'
            const turn = gameState.turn
            const nextOpen = (() => {
              if (open || kessler) return null
              switch (shell) {
                case 'leo': return turn + 1
                case 'meo': return turn + 1
                case 'cislunar': { const k = ((1 - (turn % 4)) + 4) % 4 || 4; return turn + k }
                default: return null
              }
            })()
            return (
              <div key={shell} style={{ textAlign: 'center', flex: 1 }}>
                <div style={{ fontFamily: 'Courier New', fontSize: 8, color, letterSpacing: 1 }}>
                  {SHELL_LABELS[shell] ?? shell.toUpperCase()}
                </div>
                <div style={{ fontFamily: 'Courier New', fontSize: 7, color, marginTop: 1 }}>{label}</div>
                {nextOpen !== null && (
                  <div style={{ fontFamily: 'Courier New', fontSize: 7, color: '#64748b', marginTop: 1 }}>T{nextOpen}</div>
                )}
                {debris > 0 && (
                  <div style={{ fontFamily: 'Courier New', fontSize: 7, color: '#ef4444', marginTop: 1 }}>
                    {Math.round(debris * 100)}%
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Escalation status one-liner */}
        <div style={{ fontFamily: 'Courier New', fontSize: 9, color: rungColor, marginBottom: 6, letterSpacing: 1 }}>
          RUNG {rung} — {ESCALATION_LABELS[Math.min(rung, 5)]}
        </div>

        {/* EscalationLadder */}
        <EscalationLadder rung={rung} />

        {/* Coalition dominance sparklines */}
        <div style={{ marginTop: 8 }}>
          <div style={{ fontFamily: 'Courier New', fontSize: 8, color: '#334155', letterSpacing: 1, marginBottom: 2 }}>
            DOMINANCE TREND
          </div>
          <OpsSparklines turnHistory={turnHistory} coalitionColors={gameState.coalition_colors} />
        </div>
      </div>

      {/* THREATS — only when incoming threats exist */}
      {threats.length > 0 && (
        <div>
          <div className="panel-title" style={{ color: '#ff4499' }}>◆ THREATS</div>
          {threats.map((t, i) => (
            <div key={i} style={{ fontSize: 10, color: '#ff4499', fontFamily: 'Courier New', marginBottom: 4 }}>
              ⚠ KINETIC — {t.attacker} (declared T{t.declared_turn})
            </div>
          ))}
        </div>
      )}

      {/* LOG */}
      <div style={{ flex: 1 }}>
        <div className="panel-title">◆ LOG</div>

        {/* Crisis events */}
        {gameState.events.length > 0 && (
          <div style={{ marginBottom: 10 }}>
            {gameState.events.slice().reverse().map((ev) => {
              const borderColor = ev.severity >= 0.7 ? '#ef4444' : ev.severity >= 0.4 ? '#f97316' : '#f59e0b'
              return (
                <div key={ev.event_id} style={{
                  borderLeft: `2px solid ${borderColor}`, paddingLeft: 6, marginBottom: 6,
                }}>
                  <div style={{ fontFamily: 'Courier New', fontSize: 9, color: borderColor, letterSpacing: 1 }}>
                    {ev.event_type.toUpperCase()}
                  </div>
                  <div style={{ fontSize: 10, color: '#64748b' }}>{ev.description}</div>
                </div>
              )
            })}
          </div>
        )}

        {/* Turn log */}
        <div style={{ fontFamily: 'Courier New', fontSize: 9 }}>
          {gameState.turn_log.slice().reverse().map((entry, i) => {
            const color = entry.includes('[KINETIC]') || entry.includes('[RETALIATION') ? '#ff4499'
              : entry.includes('disrupted') || entry.includes('gray-zone') ? '#f59e0b'
              : '#334155'
            return (
              <div key={i} style={{ color, marginBottom: 2 }}>{entry}</div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
