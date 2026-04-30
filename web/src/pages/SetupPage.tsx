// web/src/pages/SetupPage.tsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { listScenarios, listSessions, createGame, getState, advance, generateAar } from '../api/client'
import { useGameStore } from '../store/gameStore'
import type { ScenarioSummary, SessionSummary, AgentConfig } from '../types'

type Tab = 'NEW GAME' | 'SAVED GAMES' | 'AFTER ACTION REVIEWS'

const TABS: Tab[] = ['NEW GAME', 'SAVED GAMES', 'AFTER ACTION REVIEWS']

const MONO: React.CSSProperties = { fontFamily: 'Courier New' }

// ── Tab bar ──────────────────────────────────────────────────────────────────
function TabBar({ active, onChange }: { active: Tab; onChange: (t: Tab) => void }) {
  return (
    <div style={{ display: 'flex', gap: 0, marginBottom: 24, borderBottom: '1px solid #00d4ff22' }}>
      {TABS.map((t) => (
        <button key={t} onClick={() => onChange(t)} style={{
          background: 'none', border: 'none', borderBottom: active === t ? '2px solid #00d4ff' : '2px solid transparent',
          color: active === t ? '#00d4ff' : '#334155',
          fontFamily: 'Courier New', fontSize: 10, letterSpacing: 2, padding: '8px 18px',
          cursor: 'pointer', marginBottom: -1, transition: 'color 0.2s',
        }}>
          {t}
        </button>
      ))}
    </div>
  )
}

// ── New Game tab ──────────────────────────────────────────────────────────────
function NewGameTab() {
  const navigate = useNavigate()
  const { setSession, setGameState, setLoading, isLoading } = useGameStore()
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [agentConfig, setAgentConfig] = useState<AgentConfig[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listScenarios().then((s) => {
      setScenarios(s)
      if (s.length > 0) { setSelectedId(s[0].id); initConfig(s[0]) }
    }).catch(() => setError('Failed to load scenarios — is the API server running?'))
  }, [])

  function initConfig(scenario: ScenarioSummary) {
    setAgentConfig(scenario.factions.map((f, i) => ({
      faction_id: f.faction_id,
      agent_type: i === 0 ? 'web' : 'rule_based',
      use_advisor: false,
    })))
  }

  function handleScenarioChange(id: string) {
    setSelectedId(id)
    const s = scenarios.find((s) => s.id === id)
    if (s) initConfig(s)
  }

  function setAgentType(factionId: string, type: AgentConfig['agent_type']) {
    setAgentConfig((prev) => prev.map((c) => c.faction_id === factionId ? { ...c, agent_type: type } : c))
  }

  function setUseAdvisor(factionId: string, use: boolean) {
    setAgentConfig((prev) => prev.map((c) => c.faction_id === factionId ? { ...c, use_advisor: use } : c))
  }

  async function handleStart() {
    if (!selectedId || agentConfig.filter((c) => c.agent_type === 'web').length !== 1) {
      setError('Exactly one faction must be set to "Human (web)"')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const created = await createGame(selectedId, agentConfig)
      setSession(created.state.session_id, created.state, created.coalition_dominance)
      const advanced = await advance(created.state.session_id)
      setGameState(advanced.state, advanced.coalition_dominance)
      navigate(`/game/${created.state.session_id}`)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  const selected = scenarios.find((s) => s.id === selectedId)

  return (
    <div className="panel" style={{ width: '100%', maxWidth: 600 }}>
      {error && (
        <div style={{ color: '#ff4499', fontSize: 11, marginBottom: 16, ...MONO }}>{error}</div>
      )}

      <div className="panel-title">SELECT SCENARIO</div>
      <select value={selectedId} onChange={(e) => handleScenarioChange(e.target.value)}
        style={{ width: '100%', background: '#020b18', border: '1px solid #00d4ff33', color: '#94a3b8', padding: '8px 12px', fontFamily: 'Courier New', fontSize: 12, marginBottom: 8, borderRadius: 2 }}>
        {scenarios.map((s) => (
          <option key={s.id} value={s.id}>{s.name} ({s.turns} turns)</option>
        ))}
      </select>
      {selected && <div style={{ fontSize: 11, color: '#64748b', marginBottom: 20 }}>{selected.description}</div>}

      {selected && (
        <>
          <div className="panel-title" style={{ marginTop: 16 }}>CONFIGURE FACTIONS</div>
          {selected.factions.map((f) => {
            const cfg = agentConfig.find((c) => c.faction_id === f.faction_id)
            if (!cfg) return null
            return (
              <div key={f.faction_id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0', borderBottom: '1px solid #00d4ff11' }}>
                <div style={{ flex: 1, fontSize: 12, color: '#e2e8f0' }}>{f.name}</div>
                <select value={cfg.agent_type} onChange={(e) => setAgentType(f.faction_id, e.target.value as AgentConfig['agent_type'])}
                  style={{ background: '#020b18', border: '1px solid #00d4ff33', color: '#94a3b8', padding: '4px 8px', fontFamily: 'Courier New', fontSize: 11, borderRadius: 2 }}>
                  <option value="web">Human (web)</option>
                  <option value="rule_based">AI — Rule-based</option>
                  <option value="ai_commander">AI — Commander</option>
                </select>
                {cfg.agent_type === 'web' && (
                  <label style={{ fontSize: 11, color: '#64748b', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <input type="checkbox" checked={cfg.use_advisor} onChange={(e) => setUseAdvisor(f.faction_id, e.target.checked)} />
                    advisor
                  </label>
                )}
              </div>
            )
          })}
        </>
      )}

      <button className="btn-primary" onClick={handleStart} disabled={isLoading || !selectedId}
        style={{ marginTop: 24, width: '100%' }}>
        {isLoading ? 'INITIALIZING...' : '[ LAUNCH SIMULATION ]'}
      </button>
    </div>
  )
}

// ── Saved Games tab ───────────────────────────────────────────────────────────
function SavedGamesTab() {
  const navigate = useNavigate()
  const { setSession } = useGameStore()
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [resuming, setResuming] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listSessions().then(setSessions).catch(() => setError('Failed to load sessions')).finally(() => setLoading(false))
  }, [])

  async function handleResume(sessionId: string) {
    setResuming(sessionId)
    setError(null)
    try {
      const res = await getState(sessionId)
      setSession(res.state.session_id, res.state, res.coalition_dominance)
      navigate(`/game/${sessionId}`)
    } catch (e) {
      setError(String(e))
    } finally {
      setResuming(null)
    }
  }

  if (loading) return <div className="mono" style={{ color: '#334155', fontSize: 11 }}>LOADING SESSIONS...</div>

  const active = sessions.filter((s) => !s.game_over)

  return (
    <div style={{ width: '100%', maxWidth: 700 }}>
      {error && <div style={{ color: '#ff4499', fontSize: 11, marginBottom: 12, ...MONO }}>{error}</div>}

      {active.length === 0 ? (
        <div className="panel" style={{ color: '#334155', fontSize: 11, ...MONO, textAlign: 'center', padding: 32 }}>
          NO SAVED SESSIONS — START A NEW GAME
        </div>
      ) : (
        <div className="panel">
          <div className="panel-title">IN PROGRESS</div>
          {active.map((s) => (
            <div key={s.session_id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', borderBottom: '1px solid #00d4ff08' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, color: '#e2e8f0', marginBottom: 3 }}>{s.scenario_name}</div>
                <div style={{ fontSize: 10, color: '#64748b', ...MONO }}>
                  T{s.turn}/{s.total_turns} · {s.session_id.slice(0, 8)} · {new Date(s.updated_at).toLocaleString()}
                </div>
              </div>
              <button className="btn-primary" onClick={() => void handleResume(s.session_id)}
                disabled={resuming === s.session_id}
                style={{ fontSize: 10, padding: '4px 14px' }}>
                {resuming === s.session_id ? '...' : 'RESUME'}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── After Action Reviews tab ──────────────────────────────────────────────────
function AARTab() {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState<string | null>(null)
  const [aars, setAars] = useState<Record<string, string>>({})
  const [expanded, setExpanded] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listSessions().then(setSessions).catch(() => setError('Failed to load sessions')).finally(() => setLoading(false))
  }, [])

  async function handleGenerateAar(sessionId: string) {
    setGenerating(sessionId)
    setExpanded(sessionId)
    setError(null)
    try {
      const text = await generateAar(sessionId)
      setAars((prev) => ({ ...prev, [sessionId]: text }))
    } catch (e) {
      setError(String(e))
    } finally {
      setGenerating(null)
    }
  }

  if (loading) return <div className="mono" style={{ color: '#334155', fontSize: 11 }}>LOADING SESSIONS...</div>

  const completed = sessions.filter((s) => s.game_over)

  return (
    <div style={{ width: '100%', maxWidth: 700 }}>
      {error && <div style={{ color: '#ff4499', fontSize: 11, marginBottom: 12, ...MONO }}>{error}</div>}

      {completed.length === 0 ? (
        <div className="panel" style={{ color: '#334155', fontSize: 11, ...MONO, textAlign: 'center', padding: 32 }}>
          NO COMPLETED SESSIONS YET
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {completed.map((s) => (
            <div key={s.session_id} className="panel">
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, color: '#e2e8f0', marginBottom: 3 }}>{s.scenario_name}</div>
                  <div style={{ fontSize: 10, color: '#64748b', ...MONO }}>
                    {s.total_turns} TURNS · WINNER: {s.winner_coalition?.toUpperCase() ?? 'N/A'} · {new Date(s.updated_at).toLocaleDateString()}
                  </div>
                </div>
                <button className="btn-primary"
                  onClick={() => expanded === s.session_id ? setExpanded(null) : (aars[s.session_id] ? setExpanded(s.session_id) : void handleGenerateAar(s.session_id))}
                  disabled={generating === s.session_id}
                  style={{ fontSize: 10, padding: '4px 14px', borderColor: '#f59e0b', color: '#f59e0b' }}>
                  {generating === s.session_id ? 'GENERATING...' : expanded === s.session_id ? 'COLLAPSE' : aars[s.session_id] ? 'VIEW AAR' : 'GENERATE AAR'}
                </button>
              </div>

              {expanded === s.session_id && (
                <div style={{ marginTop: 14, borderTop: '1px solid #00d4ff11', paddingTop: 14 }}>
                  {generating === s.session_id ? (
                    <div className="mono" style={{ color: '#f59e0b', fontSize: 11 }}>GENERATING AFTER ACTION REVIEW — THIS MAY TAKE 30–60 SECONDS...</div>
                  ) : aars[s.session_id] ? (
                    <pre style={{ fontSize: 11, color: '#94a3b8', whiteSpace: 'pre-wrap', fontFamily: 'Courier New', lineHeight: 1.6, margin: 0 }}>
                      {aars[s.session_id]}
                    </pre>
                  ) : null}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Root ──────────────────────────────────────────────────────────────────────
export default function SetupPage() {
  const [tab, setTab] = useState<Tab>('NEW GAME')

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '40px 20px' }}>
      <div style={{ marginBottom: 32, textAlign: 'center' }}>
        <div className="mono" style={{ fontSize: 28, color: '#00d4ff', letterSpacing: 8 }}>◆ ASTRAKON ◆</div>
        <div className="mono" style={{ fontSize: 11, color: '#00d4ff66', letterSpacing: 3, marginTop: 6 }}>ORBITAL STRATEGY SIMULATION</div>
      </div>

      <div style={{ width: '100%', maxWidth: 700 }}>
        <TabBar active={tab} onChange={setTab} />
        {tab === 'NEW GAME' && <NewGameTab />}
        {tab === 'SAVED GAMES' && <SavedGamesTab />}
        {tab === 'AFTER ACTION REVIEWS' && <AARTab />}
      </div>
    </div>
  )
}
