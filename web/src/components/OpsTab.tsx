// web/src/components/OpsTab.tsx
import React from 'react'
import type { GameState, FactionState, FactionAssets } from '../types'
import type { TurnSnapshot } from '../store/gameStore'
import EscalationLadder from './EscalationLadder'

type AssetKey = keyof FactionAssets

interface Props {
  gameState: GameState
  coalitionDominance: Record<string, number>
  turnHistory: TurnSnapshot[]
  factionState: FactionState
  turn: number
  totalTurns: number
  tensionLevel: number
  cumulativeAdded: Partial<Record<AssetKey, number>>
  cumulativeDestroyed: Partial<Record<AssetKey, number>>
  isJammed: boolean
}

const ESCALATION_LABELS = [
  'PEACETIME', 'CONTESTED', 'DEGRADED', 'THRESHOLD', 'KINETIC', 'ESCALATORY',
]
const ESCALATION_COLORS = ['#00ff88', '#64748b', '#f59e0b', '#f97316', '#ef4444', '#ff4499']

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

const CELL: React.CSSProperties = { padding: '3px 0', borderBottom: '1px solid #00d4ff08' }
const MONO: React.CSSProperties = { fontFamily: 'Courier New' }
const SHELL_LABELS: Record<string, string> = { leo: 'LEO', meo: 'MEO', geo: 'GEO', cislunar: 'CIS' }

function OpsSparklines({ turnHistory, coalitionColors }: {
  turnHistory: TurnSnapshot[]
  coalitionColors: Record<string, string>
}) {
  if (turnHistory.length < 2) return null
  const W = 200, H = 36
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
            <circle cx={lx.toFixed(1)} cy={ly.toFixed(1)} r="2.5" fill={color} />
          </g>
        )
      })}
    </svg>
  )
}

export default function OpsTab({
  gameState, coalitionDominance, turnHistory,
  factionState: fs, turn, totalTurns, tensionLevel,
  cumulativeAdded, cumulativeDestroyed, isJammed,
}: Props) {
  void coalitionDominance
  const rung = gameState.escalation_rung ?? 0
  const rungColor = ESCALATION_COLORS[Math.min(rung, 5)]
  const threats = gameState.human_snapshot?.incoming_threats ?? []
  const jfe = fs.joint_force_effectiveness
  const jfeColor = jfe >= 0.8 ? '#00ff88' : jfe >= 0.5 ? '#f59e0b' : '#ff4499'
  const maneuver = fs.maneuver_budget ?? 10
  const maneuverColor = maneuver < 2 ? '#ef4444' : maneuver < 5 ? '#f59e0b' : '#00d4ff'

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 10 }}>

      {/* ── HEADER ── */}
      <div style={{ borderBottom: '1px solid #00d4ff22', paddingBottom: 8 }}>
        <div className="panel-title" style={{ marginBottom: 2 }}>◆ {fs.name}</div>
        <div style={{ fontSize: 12, color: '#64748b', ...MONO }}>
          T{turn}/{totalTurns} · TENSION {(tensionLevel * 100).toFixed(0)}%
        </div>
      </div>

      {/* ── TOP TWO COLUMNS: assets left | metrics right ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, borderBottom: '1px solid #00d4ff22', paddingBottom: 10 }}>

        {/* Asset table */}
        <div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 2.2rem 2.4rem 2.4rem 1.8rem 2rem',
            columnGap: 3,
          }}>
            <div style={{ fontSize: 10, color: '#475569', paddingBottom: 3 }} />
            <div style={{ fontSize: 10, color: '#475569', textAlign: 'right', paddingBottom: 3, ...MONO }}>NOW</div>
            <div style={{ fontSize: 10, color: '#00ff88aa', textAlign: 'right', paddingBottom: 3, ...MONO }}>+ADD</div>
            <div style={{ fontSize: 10, color: '#ff4499aa', textAlign: 'right', paddingBottom: 3, ...MONO }}>−DST</div>
            <div style={{ fontSize: 10, color: '#f59e0baa', textAlign: 'center', paddingBottom: 3, ...MONO }}>JAM</div>
            <div style={{ fontSize: 10, color: '#475569', textAlign: 'right', paddingBottom: 3, ...MONO }}>WT</div>

            {ASSET_ROWS.map(({ label, key, weight, jammable }) => {
              const added = cumulativeAdded[key] ?? 0
              const destroyed = cumulativeDestroyed[key] ?? 0
              const jammed = jammable && isJammed
              return (
                <React.Fragment key={key}>
                  <div style={{ ...CELL, color: '#64748b', fontSize: 12 }}>{label}</div>
                  <div style={{ ...CELL, ...MONO, color: '#e2e8f0', fontSize: 12, textAlign: 'right' }}>{fs.assets[key]}</div>
                  <div style={{ ...CELL, ...MONO, color: added > 0 ? '#00ff88' : '#475569', fontSize: 11, textAlign: 'right' }}>
                    {added > 0 ? `+${added}` : '—'}
                  </div>
                  <div style={{ ...CELL, ...MONO, color: destroyed > 0 ? '#ff4499' : '#475569', fontSize: 11, textAlign: 'right' }}>
                    {destroyed > 0 ? `-${destroyed}` : '—'}
                  </div>
                  <div style={{ ...CELL, ...MONO, color: jammed ? '#f59e0b' : '#475569', fontSize: 11, textAlign: 'center' }}>
                    {jammed ? '◆' : '—'}
                  </div>
                  <div style={{ ...CELL, ...MONO, color: '#475569', fontSize: 11, textAlign: 'right' }}>{weight}</div>
                </React.Fragment>
              )
            })}
          </div>
        </div>

        {/* Metrics + maneuver + pending */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {/* Metrics */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
            {[
              ['Budget',      `${fs.current_budget} pts`, '#00ff88'],
              ['Deterrence',  fs.deterrence_score.toFixed(0), '#00d4ff'],
              ['Mkt Share',   `${(fs.market_share * 100).toFixed(1)}%`, '#00d4ff'],
              ['Joint Force', `${(jfe * 100).toFixed(0)}%`, jfeColor],
            ].map(([label, value, color]) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748b' }}>{label}</span>
                <span style={{ color, ...MONO }}>{value}</span>
              </div>
            ))}
          </div>

          {/* Maneuver budget */}
          <div style={{ borderTop: '1px solid #00d4ff11', paddingTop: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
              <span style={{ ...MONO, fontSize: 10, color: '#475569', letterSpacing: 1 }}>MANEUVER</span>
              <span style={{ ...MONO, fontSize: 11, color: maneuverColor }}>{maneuver.toFixed(1)} DV</span>
            </div>
            <div style={{ height: 3, background: '#0f1c2d', borderRadius: 2 }}>
              <div style={{
                height: '100%', borderRadius: 2,
                width: `${Math.min((maneuver / 20) * 100, 100)}%`,
                background: maneuverColor, transition: 'width 0.3s',
              }} />
            </div>
          </div>

          {/* Cognitive penalty */}
          {(fs.cognitive_penalty ?? 0) > 0.1 && (
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ ...MONO, fontSize: 10, color: '#f97316' }}>COG. DEGRADATION</span>
              <span style={{ ...MONO, fontSize: 11, color: '#f97316' }}>
                {Math.round((fs.cognitive_penalty ?? 0) * 100)}%
              </span>
            </div>
          )}

          {/* Pending returns */}
          {fs.deferred_returns.length > 0 && (
            <div style={{ borderTop: '1px solid #00d4ff11', paddingTop: 6 }}>
              <div style={{ ...MONO, fontSize: 10, color: '#475569', letterSpacing: 1, marginBottom: 4 }}>PENDING RETURNS</div>
              {fs.deferred_returns.map((r, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#64748b', padding: '2px 0' }}>
                  <span>{r.category === 'r_and_d' ? 'R&D' : 'Education'}</span>
                  <span style={MONO}>{r.amount} pts → T{r.turn_due}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── SITUATION header + shell windows ── */}
      <div>
        <div className="panel-title" style={{ marginBottom: 6 }}>◆ SITUATION</div>

        {/* Shell access windows — compact single row */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
          {(['leo', 'meo', 'geo', 'cislunar'] as const).map((shell) => {
            const open = gameState.access_windows?.[shell] ?? true
            const debris = gameState.debris_fields?.[shell] ?? 0
            const kessler = debris >= 0.8
            const color = kessler ? '#ef4444' : open ? '#00ff88' : '#64748b'
            const statusLabel = kessler ? 'KESSLER' : open ? 'OPEN' : 'CLOSED'
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
              <div key={shell} style={{
                flex: 1, textAlign: 'center',
                border: `1px solid ${color}33`,
                borderRadius: 2, padding: '4px 0',
                background: open && !kessler ? `${color}08` : 'transparent',
              }}>
                <div style={{ ...MONO, fontSize: 11, color, letterSpacing: 1 }}>
                  {SHELL_LABELS[shell]}
                </div>
                <div style={{ ...MONO, fontSize: 10, color, marginTop: 1 }}>{statusLabel}</div>
                {nextOpen !== null && (
                  <div style={{ ...MONO, fontSize: 10, color: '#64748b', marginTop: 1 }}>T{nextOpen}</div>
                )}
                {debris > 0 && (
                  <div style={{ ...MONO, fontSize: 10, color: '#ef4444', marginTop: 1 }}>
                    {Math.round(debris * 100)}%
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* THREATS inline */}
        {threats.length > 0 && (
          <div style={{ marginBottom: 8 }}>
            {threats.map((t, i) => (
              <div key={i} style={{ fontSize: 12, color: '#ff4499', ...MONO }}>
                ⚠ KINETIC — {t.attacker} (declared T{t.declared_turn})
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── BOTTOM TWO COLUMNS: rung + sparkline left | escalation right ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, borderBottom: '1px solid #00d4ff22', paddingBottom: 10 }}>

        {/* Left: rung line + dominance sparkline */}
        <div>
          <div style={{ ...MONO, fontSize: 12, color: rungColor, marginBottom: 8, letterSpacing: 1 }}>
            RUNG {rung} — {ESCALATION_LABELS[Math.min(rung, 5)]}
          </div>
          <div style={{ ...MONO, fontSize: 10, color: '#475569', letterSpacing: 1, marginBottom: 2 }}>
            DOMINANCE TREND
          </div>
          <OpsSparklines turnHistory={turnHistory} coalitionColors={gameState.coalition_colors} />
        </div>

        {/* Right: escalation ladder */}
        <div>
          <EscalationLadder rung={rung} />
        </div>
      </div>

      {/* ── LOG ── */}
      <div style={{ flex: 1 }}>
        <div className="panel-title" style={{ marginBottom: 6 }}>◆ LOG</div>

        {gameState.events.length > 0 && (
          <div style={{ marginBottom: 10 }}>
            {gameState.events.slice().reverse().map((ev) => {
              const borderColor = ev.severity >= 0.7 ? '#ef4444' : ev.severity >= 0.4 ? '#f97316' : '#f59e0b'
              return (
                <div key={ev.event_id} style={{ borderLeft: `2px solid ${borderColor}`, paddingLeft: 6, marginBottom: 8 }}>
                  <div style={{ ...MONO, fontSize: 11, color: borderColor, letterSpacing: 1 }}>
                    {ev.event_type.toUpperCase()}
                  </div>
                  <div style={{ fontSize: 12, color: '#64748b' }}>{ev.description}</div>
                </div>
              )
            })}
          </div>
        )}

        <div style={{ ...MONO, fontSize: 11 }}>
          {gameState.turn_log.slice().reverse().map((entry, i) => {
            const color = entry.includes('[KINETIC]') || entry.includes('[RETALIATION') ? '#ff4499'
              : entry.includes('disrupted') || entry.includes('gray-zone') ? '#f59e0b'
              : '#475569'
            return (
              <div key={i} style={{ color, marginBottom: 3 }}>{entry}</div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
