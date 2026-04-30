// web/src/components/AARPanel.tsx
import type { GameState } from '../types'
import type { TurnSnapshot } from '../store/gameStore'

interface Props {
  gameState: GameState
  coalitionDominance: Record<string, number>
  turnHistory: TurnSnapshot[]
}

export default function AARPanel({ gameState, coalitionDominance, turnHistory }: Props) {
  if (!gameState.game_over) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontFamily: 'Courier New', fontSize: 10, color: '#00d4ff', letterSpacing: 2, marginBottom: 8 }}>
            ◆ AFTER ACTION REVIEW
          </div>
          <div style={{ fontFamily: 'Courier New', fontSize: 9, color: '#334155' }}>
            Game in progress. AAR available after final turn.
          </div>
        </div>
      </div>
    )
  }

  const result = gameState.result
  const winner = result?.winner_coalition
  const winnerColor = winner ? (gameState.coalition_colors[winner] === 'green' ? '#00ff88' : '#ff4499') : '#64748b'
  const W = 300
  const H = 48

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* Winner banner */}
      <div style={{ textAlign: 'center', padding: '12px 0', borderBottom: '1px solid #00d4ff11' }}>
        <div style={{ fontFamily: 'Courier New', fontSize: 9, color: '#334155', letterSpacing: 2, marginBottom: 4 }}>
          ◆ AFTER ACTION REVIEW
        </div>
        <div style={{ fontFamily: 'Courier New', fontSize: 18, color: winnerColor, letterSpacing: 4 }}>
          {winner ? winner.toUpperCase() : 'DRAW'}
        </div>
        <div style={{ fontFamily: 'Courier New', fontSize: 9, color: '#64748b', marginTop: 4 }}>
          {winner
            ? `${(coalitionDominance[winner] * 100).toFixed(1)}% DOMINANCE — ${result?.turns_completed} TURNS`
            : `${result?.turns_completed} TURNS COMPLETED`}
        </div>
      </div>

      {/* Final dominance bars */}
      <div>
        <div className="panel-title">FINAL DOMINANCE</div>
        {Object.entries(coalitionDominance).map(([cid, dom]) => {
          const color = gameState.coalition_colors[cid] === 'green' ? '#00ff88' : '#ff4499'
          return (
            <div key={cid} style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 3 }}>
                <span style={{ fontFamily: 'Courier New', color }}>{cid}</span>
                <span style={{ fontFamily: 'Courier New', color }}>{(dom * 100).toFixed(1)}%</span>
              </div>
              <div style={{ height: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${Math.min(100, dom * 100)}%`, background: color }} />
              </div>
            </div>
          )
        })}
      </div>

      {/* Full-game timeline */}
      {turnHistory.length >= 2 && (
        <div>
          <div className="panel-title">FULL-GAME DOMINANCE</div>
          <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none"
            style={{ display: 'block', marginTop: 4 }}>
            {Object.keys(turnHistory[0].dominance).map((cid) => {
              const color = gameState.coalition_colors[cid] === 'green' ? '#00ff88' : '#ff4499'
              const totalTurns = Math.max(turnHistory.length - 1, 1)
              const points = turnHistory.map((snap, i) => {
                const x = (i / totalTurns) * W
                const y = H - Math.min(snap.dominance[cid] ?? 0, 1) * H
                return `${x.toFixed(1)},${y.toFixed(1)}`
              }).join(' ')
              return (
                <polyline key={cid} points={points} fill="none" stroke={color}
                  strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" opacity={0.8} />
              )
            })}
          </svg>
        </div>
      )}

      {/* Per-faction summary */}
      <div>
        <div className="panel-title">FACTION SUMMARY</div>
        {Object.entries(gameState.faction_states).map(([fid, fs]) => {
          const coalEntry = Object.entries(gameState.coalition_states).find(([, cs]) => cs.member_ids.includes(fid))
          const cid = coalEntry?.[0]
          const color = cid ? (gameState.coalition_colors[cid] === 'green' ? '#00ff88' : '#ff4499') : '#00d4ff'
          return (
            <div key={fid} style={{ padding: '6px 0', borderBottom: '1px solid #00d4ff08', fontSize: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                <span style={{ color, fontFamily: 'Courier New' }}>{fs.name}</span>
                <span style={{ color: '#64748b', fontFamily: 'Courier New' }}>loyalty {(fs.coalition_loyalty * 100).toFixed(0)}%</span>
              </div>
              <div style={{ color: '#475569', fontFamily: 'Courier New', fontSize: 9 }}>
                LEO {fs.assets.leo_nodes} · MEO {fs.assets.meo_nodes} · GEO {fs.assets.geo_nodes} · CIS {fs.assets.cislunar_nodes}
              </div>
            </div>
          )
        })}
      </div>

      {/* Key events */}
      {gameState.events.length > 0 && (
        <div>
          <div className="panel-title">KEY EVENTS</div>
          {gameState.events.map((ev) => {
            const borderColor = ev.severity >= 0.7 ? '#ef4444' : ev.severity >= 0.4 ? '#f97316' : '#f59e0b'
            return (
              <div key={ev.event_id} style={{
                borderLeft: `2px solid ${borderColor}`, paddingLeft: 6, marginBottom: 6,
              }}>
                <div style={{ fontFamily: 'Courier New', fontSize: 9, color: borderColor }}>
                  {ev.event_type.toUpperCase()}
                </div>
                <div style={{ fontSize: 10, color: '#64748b' }}>{ev.description}</div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
