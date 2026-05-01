// web/src/pages/GamePage.tsx
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { advance, decide, getRecommendation } from '../api/client'
import { useGameStore } from '../store/gameStore'
import MapTabContainer from '../components/MapTabContainer'
import LoadingOverlay from '../components/LoadingOverlay'
import AdvisorPanel from '../components/AdvisorPanel'
import TurnSummary from '../components/TurnSummary'
import TutorialPanel from '../components/TutorialPanel'
import InvestPanel from '../components/phase/InvestPanel'
import OpsPanel from '../components/phase/OpsPanel'
import ResponsePanel from '../components/phase/ResponsePanel'
import DecisionLog from '../components/DecisionLog'
import { NODE_META } from '../components/TechTreePanel'
import type { Recommendation, GameState } from '../types'

const TECH_NODE_COSTS = Object.fromEntries(NODE_META.map(n => [n.id, n.cost]))

function sanitizeRecommendation(
  rec: Recommendation,
  gameState: GameState,
): { rec: Recommendation; warnings: string[] } {
  const validIds = new Set(Object.keys(gameState.faction_states))
  const factionNames = Object.fromEntries(
    Object.entries(gameState.faction_states).map(([id, fs]) => [id, fs.name.toLowerCase()])
  )
  const warnings: string[] = []

  function resolve(raw: string | undefined): string | undefined {
    if (!raw) return raw
    if (validIds.has(raw)) return raw

    // Coalition ID → resolve to member if unambiguous
    const coalition = gameState.coalition_states[raw]
    if (coalition) {
      const members = coalition.member_ids.filter(
        id => id !== gameState.human_faction_id && validIds.has(id)
      )
      if (members.length === 1) {
        warnings.push(`Target "${raw}" is a coalition name — resolved to ${gameState.faction_states[members[0]].name}`)
        return members[0]
      }
      warnings.push(`Target "${raw}" is a coalition with ${members.length} members — target cleared (advisor must specify a faction)`)
      return undefined
    }

    // Display name match (case-insensitive)
    const match = Object.entries(factionNames).find(([, name]) => name === raw.toLowerCase())
    if (match) {
      warnings.push(`Target "${raw}" matched by display name — resolved to faction ID "${match[0]}"`)
      return match[0]
    }

    warnings.push(`Target "${raw}" is not a valid faction ID — target cleared`)
    return undefined
  }

  const sanitized: Recommendation = {
    ...rec,
    top_recommendation: {
      ...rec.top_recommendation,
      operations: rec.top_recommendation.operations?.map(op => ({
        ...op,
        target_faction: resolve(op.target_faction),
      })),
      response: rec.top_recommendation.response
        ? { ...rec.top_recommendation.response, target_faction: resolve(rec.top_recommendation.response.target_faction) }
        : undefined,
    },
  }

  return { rec: sanitized, warnings }
}

export default function GamePage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const {
    gameState, prevFactionStates, cumulativeAdded, cumulativeDestroyed,
    turnHistory, coalitionDominance, recommendation,
    isLoading, error, showSummary,
    setGameState, setRecommendation, setLoading, setError, setShowSummary,
  } = useGameStore()

  const [showLog, setShowLog] = useState(false)
  const [handoff, setHandoff] = useState<{ toName: string } | null>(null)
  const [showOverlay, setShowOverlay] = useState(false)
  const [pendingTarget, setPendingTarget] = useState<string | null>(null)
  const [recommendationWarnings, setRecommendationWarnings] = useState<string[]>([])
  const [pendingTechUnlocks, setPendingTechUnlocks] = useState<string[]>([])
  const [arcOpacity, setArcOpacity] = useState(0)

  useEffect(() => { if (isLoading) setShowOverlay(true) }, [isLoading])

  // Clear map target whenever the phase changes
  useEffect(() => { setPendingTarget(null) }, [gameState?.current_phase])

  useEffect(() => { setPendingTechUnlocks([]) }, [gameState?.current_phase])
  useEffect(() => { setPendingTechUnlocks([]) }, [gameState?.human_faction_id])

  useEffect(() => {
    if (
      gameState?.current_phase === 'invest' &&
      !gameState.awaiting_next_turn &&
      gameState.combat_events &&
      gameState.combat_events.length > 0
    ) {
      setArcOpacity(1)
      const fadeTimer = setTimeout(() => setArcOpacity(0), 8000)
      return () => clearTimeout(fadeTimer)
    }
  }, [gameState?.turn, gameState?.current_phase, gameState?.awaiting_next_turn])

  useEffect(() => {
    if (!sessionId || !gameState) return
    if (gameState.game_over) {
      navigate(`/result/${sessionId}`)
    }
  }, [gameState?.game_over]) // eslint-disable-line react-hooks/exhaustive-deps

  async function fetchRecommendation(phase: 'invest' | 'operations' | 'response') {
    if (!sessionId || !gameState?.use_advisor) return
    try {
      const raw = await getRecommendation(sessionId, phase)
      if (!raw) { setRecommendation(null); setRecommendationWarnings([]); return }
      const { rec, warnings } = sanitizeRecommendation(raw, gameState)
      setRecommendation(rec)
      setRecommendationWarnings(warnings)
    } catch {
      setRecommendation(null)
      setRecommendationWarnings([])
    }
  }

  async function handleDecision(
    decision: Record<string, unknown>,
    forecast?: Record<string, unknown>,
  ) {
    if (!sessionId || !gameState) return
    const prevHumanId = gameState.human_faction_id
    setLoading(true)
    setError(null)
    setRecommendation(null)
    setRecommendationWarnings([])
    try {
      const res = await decide(sessionId, gameState.current_phase as string, decision, forecast)
      setGameState(res.state, res.coalition_dominance)
      // Hot-seat: detect player switch
      if (res.state.human_faction_id !== prevHumanId && !res.state.game_over && !res.state.awaiting_next_turn) {
        const toName = res.state.faction_states[res.state.human_faction_id]?.name ?? res.state.human_faction_id
        setHandoff({ toName })
      } else if (res.state.current_phase === 'invest' && !res.state.game_over && res.state.turn > gameState.turn) {
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
    const prevHumanId = gameState?.human_faction_id
    setShowSummary(false)
    setLoading(true)
    setError(null)
    try {
      const res = await advance(sessionId)
      setGameState(res.state, res.coalition_dominance)
      if (res.state.human_faction_id !== prevHumanId && !res.state.game_over) {
        const toName = res.state.faction_states[res.state.human_faction_id]?.name ?? res.state.human_faction_id
        setHandoff({ toName })
      } else if (res.state.human_snapshot && gameState?.use_advisor) {
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

  function handleQueueTech(nodeId: string) {
    setPendingTechUnlocks(prev =>
      prev.includes(nodeId) ? prev.filter(id => id !== nodeId) : [...prev, nodeId]
    )
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
      } else if (e.key === 'l' || e.key === 'L') {
        setShowLog((v) => !v)
      } else if (e.key === 'Escape') {
        if (showLog) setShowLog(false)
        else navigate('/')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isLoading, recommendation, showSummary, showLog]) // eslint-disable-line react-hooks/exhaustive-deps

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

  const pendingUnlockCost = pendingTechUnlocks.reduce(
    (sum, id) => sum + (TECH_NODE_COSTS[id] ?? 0), 0
  )
  const rdPoints = (fs.tech_tree?.r_and_d ?? 0) - pendingUnlockCost

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
        <span className="mono" style={{ color: '#475569', fontSize: 12 }}>·</span>
        <span className="mono" style={{ color: '#64748b', fontSize: 12 }}>
          TURN {gameState.turn}/{gameState.total_turns}
        </span>
        <span className="mono" style={{ color: '#475569', fontSize: 12 }}>·</span>
        <span className="mono" style={{ color: '#00d4ff88', fontSize: 12, letterSpacing: 2 }}>
          {phase.toUpperCase()} PHASE
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
        <span className="mono" style={{ color: '#64748b', fontSize: 11, letterSpacing: 1 }}>
          [A] ACCEPT · [D] DISMISS · [↵] CONTINUE · [L] LOG · [ESC] MENU
        </span>
        <button
          className="btn-primary"
          onClick={() => setShowLog((v) => !v)}
          style={{ fontSize: 11, padding: '2px 10px', borderColor: '#334155', color: '#64748b' }}
        >
          LOG
        </button>
        <button
          className="btn-primary"
          onClick={() => navigate('/')}
          style={{ fontSize: 11, padding: '2px 10px', borderColor: '#334155', color: '#64748b' }}
        >
          ← MENU
        </button>
      </div>

      {/* Two-panel layout */}
      <div style={{ flex: 1, display: 'flex', gap: 8, padding: 8, overflow: 'hidden', minHeight: 0 }}>

        {/* LEFT PANEL */}
        <div style={{ flex: 2, minHeight: 0, overflow: 'hidden' }}>
          <MapTabContainer
            gameState={gameState}
            coalitionDominance={coalitionDominance}
            turnHistory={turnHistory}
            prevFactionStates={prevFactionStates}
            humanAdversaryEstimates={gameState.human_adversary_estimates ?? {}}
            factionState={fs}
            turn={gameState.turn}
            totalTurns={gameState.total_turns}
            tensionLevel={gameState.tension_level}
            cumulativeAdded={cumulativeAdded}
            cumulativeDestroyed={cumulativeDestroyed}
            isJammed={isJammed}
            targetingMode={phase === 'operations' && !isLoading}
            lockedFaction={pendingTarget}
            onFactionClick={setPendingTarget}
            pendingTechUnlocks={pendingTechUnlocks}
            onQueueTech={handleQueueTech}
            rdPoints={rdPoints}
            combatEvents={gameState.combat_events}
            arcOpacity={arcOpacity}
            forecasts={gameState.operation_forecasts ?? []}
          />
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

          <TutorialPanel phase={phase} turn={gameState.turn} />

          {recommendation && (
            <AdvisorPanel
              recommendation={recommendation}
              phase={phase as 'invest' | 'operations' | 'response'}
              warnings={recommendationWarnings}
              onAccept={handleAcceptAdvisor}
              onDismiss={() => { setRecommendation(null); setRecommendationWarnings([]) }}
            />
          )}

          {phase === 'invest' && (
            <InvestPanel
              budget={fs.current_budget}
              onSubmit={(d) => handleDecision({ ...d, tech_unlocks: pendingTechUnlocks })}
              disabled={isLoading}
            />
          )}
          {phase === 'operations' && (
            <OpsPanel
              factionNames={factionNames}
              humanFactionId={gameState.human_faction_id}
              asatKinetic={fs.assets.asat_kinetic}
              sessionId={sessionId!}
              onSubmit={(d, f) => handleDecision(d, f)}
              disabled={isLoading}
              mapTarget={pendingTarget}
              onClearMapTarget={() => setPendingTarget(null)}
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

      {showOverlay && <LoadingOverlay loading={isLoading} onDismiss={() => setShowOverlay(false)} />}

      {handoff && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(2,11,24,0.97)', zIndex: 200,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 24,
        }}>
          <div className="mono" style={{ fontSize: 11, color: '#f59e0b', letterSpacing: 4 }}>◆ HOT SEAT ◆</div>
          <div className="mono" style={{ fontSize: 22, color: '#00d4ff', letterSpacing: 4 }}>
            {handoff.toName.toUpperCase()}
          </div>
          <div className="mono" style={{ fontSize: 12, color: '#64748b', textAlign: 'center', maxWidth: 360 }}>
            Hand the device to the next player.<br />Press READY when they are in position.
          </div>
          <button className="btn-primary" onClick={() => setHandoff(null)}
            style={{ fontSize: 12, padding: '8px 32px', letterSpacing: 3 }}>
            [ READY ]
          </button>
        </div>
      )}

      {showLog && sessionId && (
        <DecisionLog
          sessionId={sessionId}
          scenarioName={gameState.scenario_name}
          onClose={() => setShowLog(false)}
        />
      )}

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
