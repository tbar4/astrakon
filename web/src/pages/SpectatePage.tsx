// web/src/pages/SpectatePage.tsx
import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { advance } from '../api/client'
import type { GameState } from '../types'
import type { TurnSnapshot } from '../store/gameStore'
import MapTabContainer from '../components/MapTabContainer'
import { LOADING_QUOTES } from '../data/loadingQuotes'

const SPEEDS = [
  { label: '0.5×', ms: 6000 },
  { label: '1×',   ms: 3000 },
  { label: '2×',   ms: 1500 },
  { label: '4×',   ms: 500  },
]

export default function SpectatePage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()

  const [gameState, setGameState] = useState<GameState | null>(null)
  const [prevFactionStates, setPrevFactionStates] = useState<Record<string, import('../types').FactionState> | null>(null)
  const [coalitionDominance, setCoalitionDominance] = useState<Record<string, number>>({})
  const [turnHistory, setTurnHistory] = useState<TurnSnapshot[]>([])
  const [paused, setPaused] = useState(false)
  const [speedIdx, setSpeedIdx] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const advancing = useRef(false)

  // Auto-advance loop
  useEffect(() => {
    if (!sessionId || !gameState || gameState.game_over || paused) return

    const timer = setTimeout(async () => {
      if (advancing.current) return
      advancing.current = true
      try {
        const res = await advance(sessionId)
        setTurnHistory((prev) => {
          const isTurnBoundary = res.state.turn > (gameState?.turn ?? 0)
          if (isTurnBoundary && gameState) {
            const allFs = Object.values(gameState.faction_states)
            const shellTotals = {
              leo: allFs.reduce((s, f) => s + f.assets.leo_nodes, 0),
              meo: allFs.reduce((s, f) => s + f.assets.meo_nodes, 0),
              geo: allFs.reduce((s, f) => s + f.assets.geo_nodes, 0),
              cis: allFs.reduce((s, f) => s + f.assets.cislunar_nodes, 0),
            }
            const factionTotals: Record<string, number> = {}
            for (const [fid, fs] of Object.entries(gameState.faction_states)) {
              factionTotals[fid] = fs.assets.leo_nodes + fs.assets.meo_nodes + fs.assets.geo_nodes + fs.assets.cislunar_nodes
            }
            return [...prev, { turn: gameState.turn, dominance: coalitionDominance, tension: gameState.tension_level, shellTotals, factionTotals }] as TurnSnapshot[]
          }
          return prev
        })
        setGameState((prev) => {
          if (prev && res.state.turn > prev.turn) setPrevFactionStates(prev.faction_states)
          return res.state
        })
        setCoalitionDominance(res.coalition_dominance)
      } catch (e) {
        setError(String(e))
        setPaused(true)
      } finally {
        advancing.current = false
      }
    }, SPEEDS[speedIdx].ms)

    return () => clearTimeout(timer)
  }, [gameState, paused, speedIdx, coalitionDominance]) // eslint-disable-line react-hooks/exhaustive-deps

  // Initial advance to get first state (sessionId was just created)
  useEffect(() => {
    if (!sessionId || gameState) return
    advance(sessionId).then((res) => {
      setGameState(res.state)
      setCoalitionDominance(res.coalition_dominance)
    }).catch((e) => setError(String(e)))
  }, [sessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!gameState) {
    const q = LOADING_QUOTES[Math.floor(Math.random() * LOADING_QUOTES.length)]
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: 20 }}>
        <div className="mono" style={{ color: '#00d4ff', fontSize: 11, letterSpacing: 4 }}>INITIALIZING SIMULATION...</div>
        <div style={{ width: 200, height: 2, background: 'rgba(0,212,255,0.1)', overflow: 'hidden', borderRadius: 1 }}>
          <div style={{ height: '100%', width: '40%', background: '#00d4ff', boxShadow: '0 0 8px #00d4ff', animation: 'scan 1.5s linear infinite' }} />
        </div>
        <div style={{ maxWidth: 480, textAlign: 'center', marginTop: 12 }}>
          <div style={{ fontSize: 12, color: '#64748b', fontStyle: 'italic', lineHeight: 1.7, marginBottom: 10, fontFamily: 'Georgia, serif' }}>
            "{q.text}"
          </div>
          <div className="mono" style={{ fontSize: 9, color: '#64748b', letterSpacing: 1 }}>— {q.author}</div>
          <div className="mono" style={{ fontSize: 9, color: '#1e3a4a', letterSpacing: 1, marginTop: 2 }}>{q.source}</div>
        </div>
        <style>{`@keyframes scan { 0% { transform: translateX(-100%); } 100% { transform: translateX(600%); } }`}</style>
      </div>
    )
  }

  if (gameState.game_over) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: 24 }}>
        <div className="mono" style={{ fontSize: 22, color: '#00d4ff', letterSpacing: 6 }}>◆ SIMULATION COMPLETE ◆</div>
        <div className="mono" style={{ fontSize: 13, color: '#00ff88' }}>
          WINNER: {gameState.result?.winner_coalition?.toUpperCase() ?? 'DRAW'}
        </div>
        <div className="mono" style={{ fontSize: 11, color: '#64748b' }}>
          {gameState.result?.turns_completed} TURNS COMPLETED
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <button className="btn-primary" onClick={() => navigate('/')}
            style={{ fontSize: 11, padding: '6px 20px' }}>← MENU</button>
        </div>
      </div>
    )
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{
        padding: '6px 16px', borderBottom: '1px solid #00d4ff22',
        display: 'flex', alignItems: 'center', gap: 16, background: '#020b18', flexShrink: 0,
      }}>
        <span className="mono" style={{ color: '#00d4ff', fontSize: 13, letterSpacing: 4 }}>◆ ASTRAKON</span>
        <span className="mono" style={{ color: '#f59e0b', fontSize: 12, letterSpacing: 2 }}>SPECTATOR</span>
        <span className="mono" style={{ color: '#475569', fontSize: 12 }}>·</span>
        <span className="mono" style={{ color: '#64748b', fontSize: 12 }}>
          TURN {gameState.turn}/{gameState.total_turns}
        </span>
        <span className="mono" style={{ color: '#475569', fontSize: 12 }}>·</span>
        <span className="mono" style={{ color: '#00d4ff88', fontSize: 12, letterSpacing: 2 }}>
          {(gameState.current_phase as string).toUpperCase()} PHASE
        </span>
        <span style={{ flex: 1 }} />
        <span className="mono" style={{ color: '#64748b', fontSize: 11 }}>{gameState.scenario_name}</span>
        {Object.keys(gameState.token_totals ?? {}).length > 0 && (() => {
          const totals = gameState.token_totals ?? {}
          const totalIn = Object.values(totals).reduce((s, t) => s + (t.input_tokens ?? 0), 0)
          const totalOut = Object.values(totals).reduce((s, t) => s + (t.output_tokens ?? 0), 0)
          const total = totalIn + totalOut
          const fmt = total >= 1000 ? `${(total / 1000).toFixed(1)}K` : String(total)
          return (
            <span className="mono" style={{ color: '#475569', fontSize: 11, letterSpacing: 1 }} title={`AI tokens: ${totalIn.toLocaleString()} in / ${totalOut.toLocaleString()} out`}>
              ⬡ {fmt} tok
            </span>
          )
        })()}

        {/* Speed controls */}
        <div style={{ display: 'flex', gap: 4 }}>
          {SPEEDS.map((s, i) => (
            <button key={i} className="btn-primary" onClick={() => setSpeedIdx(i)}
              style={{ fontSize: 11, padding: '2px 8px', borderColor: i === speedIdx ? '#00d4ff' : '#334155', color: i === speedIdx ? '#00d4ff' : '#64748b' }}>
              {s.label}
            </button>
          ))}
        </div>

        <button className="btn-primary" onClick={() => setPaused((p) => !p)}
          style={{ fontSize: 11, padding: '2px 10px', borderColor: paused ? '#00ff88' : '#f59e0b', color: paused ? '#00ff88' : '#f59e0b' }}>
          {paused ? '▶ RESUME' : '⏸ PAUSE'}
        </button>
        <button className="btn-primary" onClick={() => navigate('/')}
          style={{ fontSize: 11, padding: '2px 10px', borderColor: '#334155', color: '#64748b' }}>
          ← MENU
        </button>
      </div>

      {error && (
        <div style={{ padding: '6px 16px', background: 'rgba(255,68,153,0.1)', color: '#ff4499', fontSize: 11, fontFamily: 'Courier New' }}>
          ERROR: {error}
          <button className="btn-primary" onClick={() => { setError(null); setPaused(false) }}
            style={{ marginLeft: 12, fontSize: 10, padding: '1px 8px' }}>RETRY</button>
        </div>
      )}

      {/* Two-panel layout */}
      <div style={{ flex: 1, display: 'flex', gap: 8, padding: 8, overflow: 'hidden', minHeight: 0 }}>

        {/* LEFT: map tab panel */}
        <div style={{ flex: 2, minHeight: 0 }}>
          <MapTabContainer
            gameState={gameState}
            coalitionDominance={coalitionDominance}
            turnHistory={turnHistory}
            prevFactionStates={prevFactionStates}
            humanAdversaryEstimates={{}}
            factionState={Object.values(gameState.faction_states)[0]!}
            turn={gameState.turn}
            totalTurns={gameState.total_turns}
            tensionLevel={gameState.tension_level}
            cumulativeAdded={{}}
            cumulativeDestroyed={{}}
            isJammed={false}
          />
        </div>

        {/* RIGHT: faction overview + ops log */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8, minHeight: 0, overflow: 'hidden' }}>

          {/* All factions snapshot */}
          <div className="panel" style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
            <div className="panel-title">◆ ALL FACTIONS</div>
            {Object.entries(gameState.faction_states).map(([fid, fs]) => {
              const coalitionEntry = Object.entries(gameState.coalition_states).find(([, cs]) => cs.member_ids.includes(fid))
              const cid = coalitionEntry?.[0]
              const color = cid ? (gameState.coalition_colors[cid] === 'green' ? '#00ff88' : '#ff4499') : '#00d4ff'
              return (
                <div key={fid} style={{ padding: '8px 0', borderBottom: '1px solid #00d4ff08' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 11, color }}>{fs.name}</span>
                    <span className="mono" style={{ fontSize: 10, color: '#64748b' }}>{fs.current_budget} pts</span>
                  </div>
                  <div style={{ display: 'flex', gap: 10, fontSize: 10, fontFamily: 'Courier New', color: '#475569' }}>
                    <span>LEO {fs.assets.leo_nodes}</span>
                    <span>MEO {fs.assets.meo_nodes}</span>
                    <span>GEO {fs.assets.geo_nodes}</span>
                    <span>CIS {fs.assets.cislunar_nodes}</span>
                    {fs.assets.asat_kinetic > 0 && <span style={{ color: '#ff4499' }}>ASAT-K {fs.assets.asat_kinetic}</span>}
                    {fs.assets.ew_jammers > 0 && <span style={{ color: '#f59e0b' }}>EW {fs.assets.ew_jammers}</span>}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Ops log */}
          {gameState.turn_log.length > 0 && (
            <div className="panel" style={{ flex: '0 1 auto', maxHeight: '28%', overflowY: 'auto', minHeight: 0 }}>
              <div className="panel-title">◆ OPS LOG</div>
              {gameState.turn_log.slice(-12).map((entry, i) => {
                const color = entry.includes('[KINETIC]') || entry.includes('[RETALIATION') ? '#ff4499'
                  : entry.includes('disrupted') || entry.includes('gray-zone') ? '#f59e0b'
                  : '#475569'
                return (
                  <div key={i} style={{ fontSize: 10, color, marginBottom: 2, fontFamily: 'Courier New' }}>{entry}</div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
