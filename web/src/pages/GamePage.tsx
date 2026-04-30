// web/src/pages/GamePage.tsx
import { useEffect, useState } from 'react'
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
    gameState, coalitionDominance, recommendation,
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

  const [showMap, setShowMap] = useState(true)

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
      </div>

      {/* 3-column layout */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '200px 1fr 220px', gap: 8, padding: 8, overflow: 'hidden', minHeight: 0 }}>
        {/* Left: Faction Sidebar */}
        <FactionSidebar
          factionState={fs}
          turn={gameState.turn}
          totalTurns={gameState.total_turns}
          tensionLevel={gameState.tension_level}
        />

        {/* Center: collapsible Orbital Map + Phase Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, overflow: 'hidden', minHeight: 0 }}>
          {/* Map toggle bar */}
          <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              onClick={() => setShowMap((v) => !v)}
              style={{
                background: 'none', border: '1px solid #00d4ff22', color: '#00d4ff66',
                fontFamily: 'Courier New', fontSize: 9, letterSpacing: 2, cursor: 'pointer',
                padding: '3px 10px', borderRadius: 2,
              }}
            >
              {showMap ? '▾ HIDE MAP' : '▸ SHOW MAP'}
            </button>
          </div>

          {showMap && (
            <div style={{ height: 220, flexShrink: 0 }}>
              <OrbitalMap gameState={gameState} coalitionDominance={coalitionDominance} />
            </div>
          )}

          {/* Phase panel — takes all remaining space */}
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

        {/* Right: Dominance Rail */}
        <DominanceRail gameState={gameState} coalitionDominance={coalitionDominance} />
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
