// web/src/pages/GamePage.tsx
import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { advance, decide, getRecommendation } from '../api/client'
import { useGameStore } from '../store/gameStore'
import OrbitalMap from '../components/OrbitalMap'
import FactionSidebar from '../components/FactionSidebar'
import DominanceRail from '../components/DominanceRail'
import LoadingOverlay from '../components/LoadingOverlay'
import AdvisorPanel from '../components/AdvisorPanel'
import TurnSummary from '../components/TurnSummary'
import InvestPanel from '../components/phase/InvestPanel'
import OpsPanel from '../components/phase/OpsPanel'
import ResponsePanel from '../components/phase/ResponsePanel'

export default function GamePage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const {
    gameState, prevFactionStates, cumulativeAdded, cumulativeDestroyed,
    turnHistory, coalitionDominance, recommendation,
    isLoading, error, showSummary,
    setGameState, setRecommendation, setLoading, setError, setShowSummary,
  } = useGameStore()

  useEffect(() => {
    if (!sessionId || !gameState) return
    if (gameState.game_over) {
      navigate(`/result/${sessionId}`)
    }
  }, [gameState?.game_over]) // eslint-disable-line react-hooks/exhaustive-deps

  async function fetchRecommendation(phase: 'invest' | 'operations' | 'response') {
    if (!sessionId || !gameState?.use_advisor) return
    try {
      const rec = await getRecommendation(sessionId, phase)
      setRecommendation(rec)
    } catch {
      setRecommendation(null)
    }
  }

  async function handleDecision(decision: Record<string, unknown>) {
    if (!sessionId || !gameState) return
    setLoading(true)
    setError(null)
    setRecommendation(null)
    try {
      const res = await decide(sessionId, gameState.current_phase as string, decision)
      setGameState(res.state, res.coalition_dominance)
      if (res.state.current_phase === 'invest' && !res.state.game_over && res.state.turn > gameState.turn) {
        setShowSummary(true)
      } else if (res.state.human_snapshot && gameState.use_advisor) {
        await fetchRecommendation(res.state.current_phase as 'invest' | 'operations' | 'response')
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleNextTurn() {
    if (!sessionId) return
    setShowSummary(false)
    setLoading(true)
    setError(null)
    try {
      const res = await advance(sessionId)
      setGameState(res.state, res.coalition_dominance)
      if (res.state.human_snapshot && gameState?.use_advisor) {
        await fetchRecommendation(res.state.current_phase as 'invest' | 'operations' | 'response')
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  function handleAcceptAdvisor() {
    if (!recommendation || !gameState) return
    const phase = gameState.current_phase as string
    const rec = recommendation.top_recommendation
    let decision: Record<string, unknown> = {}
    if (phase === 'invest' && rec.investment) decision = { investment: rec.investment }
    else if (phase === 'operations' && rec.operations) decision = { operations: rec.operations }
    else if (phase === 'response' && rec.response) decision = { response: rec.response }
    setRecommendation(null)
    void handleDecision(decision)
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (isLoading) return
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (e.key === 'a' || e.key === 'A') {
        if (recommendation) handleAcceptAdvisor()
      } else if (e.key === 'd' || e.key === 'D') {
        if (recommendation) setRecommendation(null)
      } else if (e.key === 'Enter') {
        if (showSummary) void handleNextTurn()
      } else if (e.key === 'Escape') {
        navigate('/')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isLoading, recommendation, showSummary]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!gameState) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <div className="mono" style={{ color: '#00d4ff' }}>NO ACTIVE SESSION — <a href="/" style={{ color: '#00ff88' }}>RETURN TO SETUP</a></div>
      </div>
    )
  }

  const fs = gameState.human_snapshot?.faction_state ?? gameState.faction_states[gameState.human_faction_id]
  const snap = gameState.human_snapshot
  const phase = gameState.current_phase as string
  const factionNames = snap?.faction_names ?? Object.fromEntries(
    Object.entries(gameState.faction_states).map(([fid, s]) => [fid, s.name])
  )

  const isJammed = (() => {
    const name = fs.name.toLowerCase()
    const log = gameState.turn_log.join(' ').toLowerCase()
    return log.includes(name) && (log.includes('jam') || log.includes('[ew]'))
  })()

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{
        padding: '6px 16px', borderBottom: '1px solid #00d4ff22',
        display: 'flex', alignItems: 'center', gap: 16, background: '#020b18', flexShrink: 0,
      }}>
        <span className="mono" style={{ color: '#00d4ff', fontSize: 13, letterSpacing: 4 }}>◆ ASTRAKON</span>
        <span className="mono" style={{ color: '#334155', fontSize: 10 }}>·</span>
        <span className="mono" style={{ color: '#64748b', fontSize: 10 }}>
          TURN {gameState.turn}/{gameState.total_turns}
        </span>
        <span className="mono" style={{ color: '#334155', fontSize: 10 }}>·</span>
        <span className="mono" style={{ color: '#00d4ff88', fontSize: 10, letterSpacing: 2 }}>
          {phase.toUpperCase()} PHASE
        </span>
        <span style={{ flex: 1 }} />
        <span className="mono" style={{ color: '#64748b', fontSize: 10 }}>{gameState.scenario_name}</span>
        <span className="mono" style={{ color: '#1e3a4a', fontSize: 9, letterSpacing: 1 }}>
          [A] ACCEPT · [D] DISMISS · [↵] CONTINUE · [ESC] MENU
        </span>
        <button
          className="btn-primary"
          onClick={() => navigate('/')}
          style={{ fontSize: 10, padding: '2px 10px', borderColor: '#334155', color: '#64748b' }}
        >
          ← MENU
        </button>
      </div>

      {/* Two-panel layout */}
      <div style={{ flex: 1, display: 'flex', gap: 8, padding: 8, overflow: 'hidden', minHeight: 0 }}>

        {/* LEFT PANEL */}
        <div style={{ flex: 2, display: 'flex', flexDirection: 'column', gap: 8, minHeight: 0, overflow: 'hidden' }}>
          {/* Top box: faction info + coalition dominance side by side */}
          <div style={{ flex: '0 1 auto', maxHeight: '45%', minHeight: 0, display: 'flex', flexDirection: 'row', gap: 8, overflow: 'hidden' }}>
            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
              <FactionSidebar
                factionState={fs}
                turn={gameState.turn}
                totalTurns={gameState.total_turns}
                tensionLevel={gameState.tension_level}
                cumulativeAdded={cumulativeAdded}
                cumulativeDestroyed={cumulativeDestroyed}
                isJammed={isJammed}
              />
            </div>
            <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
              <DominanceRail gameState={gameState} coalitionDominance={coalitionDominance} turnHistory={turnHistory} />
            </div>
          </div>

          {/* Center: orbital map fills remaining space */}
          <div style={{ flex: 1, minHeight: 0 }}>
            <OrbitalMap gameState={gameState} coalitionDominance={coalitionDominance} prevFactionStates={prevFactionStates} />
          </div>

          {/* Bottom box: ops log */}
          <div className="panel" style={{ flex: '0 1 auto', maxHeight: '22%', overflowY: 'auto', minHeight: 0 }}>
            <div className="panel-title">◆ OPS LOG</div>
            {gameState.turn_log.slice(-10).map((entry, i) => {
              const color = entry.includes('[KINETIC]') || entry.includes('[RETALIATION') ? '#ff4499'
                : entry.includes('disrupted') || entry.includes('gray-zone') ? '#f59e0b'
                : '#475569'
              return (
                <div key={i} style={{ fontSize: 10, color, marginBottom: 2, fontFamily: 'Courier New' }}>
                  {entry}
                </div>
              )
            })}
          </div>
        </div>

        {/* RIGHT PANEL: decision area only */}
        <div className="panel" style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
          {error && (
            <div style={{ color: '#ff4499', fontSize: 11, marginBottom: 10, fontFamily: 'Courier New' }}>
              ERROR: {error}
              <button className="btn-primary" onClick={() => { setError(null); void handleNextTurn() }}
                style={{ marginLeft: 10, fontSize: 10, padding: '2px 8px' }}>
                RETRY
              </button>
            </div>
          )}

          {recommendation && (
            <AdvisorPanel
              recommendation={recommendation}
              phase={phase as 'invest' | 'operations' | 'response'}
              onAccept={handleAcceptAdvisor}
              onDismiss={() => setRecommendation(null)}
            />
          )}

          {phase === 'invest' && (
            <InvestPanel
              budget={fs.current_budget}
              onSubmit={handleDecision}
              disabled={isLoading}
            />
          )}
          {phase === 'operations' && (
            <OpsPanel
              factionNames={factionNames}
              humanFactionId={gameState.human_faction_id}
              onSubmit={handleDecision}
              disabled={isLoading}
            />
          )}
          {phase === 'response' && (
            <ResponsePanel
              factionNames={factionNames}
              humanFactionId={gameState.human_faction_id}
              turnLogSummary={snap?.turn_log_summary ?? ''}
              onSubmit={handleDecision}
              disabled={isLoading}
            />
          )}
        </div>
      </div>

      {isLoading && <LoadingOverlay />}

      {showSummary && (
        <TurnSummary
          gameState={gameState}
          coalitionDominance={coalitionDominance}
          onContinue={handleNextTurn}
        />
      )}
    </div>
  )
}
