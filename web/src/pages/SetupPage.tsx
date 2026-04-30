// web/src/pages/SetupPage.tsx
import React, { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { useNavigate } from 'react-router-dom'
import { listScenarios, listSessions, createGame, getState, advance, generateAar, listAars, getScenario, createScenario, updateScenario, deleteScenario } from '../api/client'
import type { SavedAar, AarResult } from '../api/client'
import { useGameStore } from '../store/gameStore'
import type { ScenarioSummary, SessionSummary, AgentConfig, ScenarioDetail, ScenarioFactionDetail } from '../types'

type Tab = 'NEW GAME' | 'SAVED GAMES' | 'AFTER ACTION REVIEWS' | 'SCENARIO EDITOR' | 'HOW TO PLAY'

const TABS: Tab[] = ['NEW GAME', 'SAVED GAMES', 'AFTER ACTION REVIEWS', 'SCENARIO EDITOR', 'HOW TO PLAY']

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
    const webCount = agentConfig.filter((c) => c.agent_type === 'web').length
    if (!selectedId || webCount === 0) {
      setError('At least one faction must be set to "Human (web)"')
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

  async function handleSpectate() {
    if (!selectedId) return
    setLoading(true)
    setError(null)
    try {
      // All factions set to AI for spectator mode
      const spectatorConfig: AgentConfig[] = agentConfig.map((c, i) => ({
        ...c,
        agent_type: i === 0 ? 'rule_based' : c.agent_type === 'web' ? 'rule_based' : c.agent_type,
        use_advisor: false,
      }))
      const created = await createGame(selectedId, spectatorConfig)
      navigate(`/spectate/${created.state.session_id}`)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  const selected = scenarios.find((s) => s.id === selectedId)

  return (
    <div className="panel" style={{ width: '100%' }}>
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

      <div style={{ display: 'flex', gap: 8, marginTop: 24 }}>
        <button className="btn-primary" onClick={handleStart} disabled={isLoading || !selectedId}
          style={{ flex: 1 }}>
          {isLoading ? 'INITIALIZING...' : '[ LAUNCH SIMULATION ]'}
        </button>
        <button className="btn-primary" onClick={() => void handleSpectate()} disabled={isLoading || !selectedId}
          style={{ flex: '0 0 auto', fontSize: 10, padding: '6px 16px', borderColor: '#f59e0b', color: '#f59e0b' }}>
          WATCH AI vs AI
        </button>
      </div>
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
const AAR_INPUT: React.CSSProperties = {
  width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
  color: '#94a3b8', fontFamily: 'Courier New', fontSize: 11, borderRadius: 2,
  padding: '6px 8px', resize: 'vertical',
}

function SessionAarRow({ s }: { s: SessionSummary }) {
  const [expanded, setExpanded] = useState(false)
  const [savedAars, setSavedAars] = useState<SavedAar[]>([])
  const [loadedAars, setLoadedAars] = useState(false)
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)
  const [focus, setFocus] = useState('')
  const [generating, setGenerating] = useState(false)
  const [lastGenerated, setLastGenerated] = useState<AarResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function openPanel() {
    setExpanded(true)
    if (!loadedAars) {
      try {
        const aars = await listAars(s.session_id)
        setSavedAars(aars)
        if (aars.length > 0) setSelectedIdx(0)
      } catch { /* ignore */ }
      setLoadedAars(true)
    }
  }

  async function handleGenerate(force = false) {
    setGenerating(true)
    setError(null)
    try {
      const result = await generateAar(s.session_id, focus, force)
      setLastGenerated(result.cached ? null : result)
      const aars = await listAars(s.session_id)
      setSavedAars(aars)
      const idx = aars.findIndex(a => a.focus === result.focus)
      setSelectedIdx(idx >= 0 ? idx : 0)
    } catch (e) {
      setError(String(e))
    } finally {
      setGenerating(false)
    }
  }

  function downloadMd(text: string, focus: string) {
    const suffix = focus ? `-${focus.slice(0, 30).toLowerCase().replace(/\s+/g, '-')}` : ''
    const blob = new Blob([text], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `aar-${(s.scenario_name ?? s.session_id).toLowerCase().replace(/\s+/g, '-')}${suffix}.md`
    a.click(); URL.revokeObjectURL(url)
  }

  function openPdf(text: string) {
    const win = window.open('', '_blank')
    if (!win) return
    const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    win.document.open()
    win.document.write(`<html><head><title>AAR</title><style>body{font-family:Georgia,serif;max-width:800px;margin:40px auto;padding:0 20px;line-height:1.7}@media print{body{margin:20px}}</style></head><body><pre style="white-space:pre-wrap;font-family:Georgia,serif;font-size:14px">${escaped}</pre><script>window.onload=function(){window.print()}<\/script></body></html>`)
    win.document.close()
  }

  const active = selectedIdx !== null ? savedAars[selectedIdx] : null

  return (
    <div className="panel">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, color: '#e2e8f0', marginBottom: 3 }}>{s.scenario_name}</div>
          <div style={{ fontSize: 10, color: '#64748b', ...MONO }}>
            {s.total_turns} TURNS · WINNER: {s.winner_coalition?.toUpperCase() ?? 'N/A'} · {new Date(s.updated_at).toLocaleDateString()}
            {savedAars.length > 0 && <span style={{ color: '#334155' }}> · {savedAars.length} REPORT{savedAars.length !== 1 ? 'S' : ''} SAVED</span>}
          </div>
        </div>
        <button className="btn-primary"
          onClick={() => expanded ? setExpanded(false) : void openPanel()}
          style={{ fontSize: 10, padding: '4px 14px', borderColor: '#f59e0b', color: '#f59e0b' }}>
          {expanded ? 'COLLAPSE' : 'VIEW AARs'}
        </button>
      </div>

      {expanded && (
        <div style={{ marginTop: 14, borderTop: '1px solid #00d4ff11', paddingTop: 14 }}>
          {error && <div style={{ color: '#ff4499', fontSize: 11, marginBottom: 10, ...MONO }}>{error}</div>}

          {/* Saved report selector */}
          {savedAars.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 10, color: '#475569', ...MONO, marginBottom: 6, letterSpacing: 1 }}>SAVED REPORTS</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                {savedAars.map((a, i) => (
                  <button key={i} onClick={() => { setSelectedIdx(i); setLastGenerated(null) }}
                    style={{
                      textAlign: 'left', background: selectedIdx === i ? '#00d4ff08' : 'none',
                      border: `1px solid ${selectedIdx === i ? '#00d4ff22' : '#00d4ff0a'}`,
                      borderRadius: 2, padding: '5px 8px', cursor: 'pointer',
                      display: 'flex', justifyContent: 'space-between',
                    }}>
                    <span style={{ fontSize: 11, color: '#94a3b8', ...MONO }}>{a.focus ? `"${a.focus}"` : 'Standard report'}</span>
                    <span style={{ fontSize: 10, color: '#334155', ...MONO }}>{new Date(a.created_at).toLocaleDateString()}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Focus input + generate */}
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 10, color: '#475569', ...MONO, marginBottom: 4, letterSpacing: 1 }}>
              FOCUS AREA <span style={{ color: '#334155' }}>(optional)</span>
            </div>
            <textarea rows={2} value={focus} onChange={(e) => setFocus(e.target.value)}
              placeholder="e.g. coalition defection dynamics, Turn 4 kinetic exchange..."
              style={AAR_INPUT} />
          </div>
          <button className="btn-primary" onClick={() => void handleGenerate(false)} disabled={generating}
            style={{ width: '100%', marginBottom: 14, fontSize: 11 }}>
            {generating ? '[ GENERATING — 30–60s... ]' : savedAars.some(a => a.focus === focus.trim()) ? '[ VIEW CACHED REPORT ]' : '[ GENERATE REPORT ]'}
          </button>

          {/* Active report */}
          {active && (
            <>
              <div style={{ display: 'flex', gap: 8, marginBottom: 6, alignItems: 'center' }}>
                <span style={{ fontSize: 10, color: '#475569', ...MONO, flex: 1 }}>
                  {active.focus ? `FOCUS: "${active.focus}"` : 'STANDARD REPORT'}
                </span>
                <button className="btn-primary" onClick={() => void handleGenerate(true)} disabled={generating}
                  style={{ fontSize: 10, padding: '2px 10px', borderColor: '#334155', color: '#64748b' }}>REGENERATE</button>
                <button className="btn-primary" onClick={() => downloadMd(active.text, active.focus)}
                  style={{ fontSize: 10, padding: '2px 10px', borderColor: '#00d4ff66', color: '#00d4ff' }}>↓ MD</button>
                <button className="btn-primary" onClick={() => openPdf(active.text)}
                  style={{ fontSize: 10, padding: '2px 10px', borderColor: '#f59e0b66', color: '#f59e0b' }}>↓ PDF</button>
              </div>
              {lastGenerated?.usage && (
                <div style={{ display: 'flex', gap: 16, padding: '5px 10px', marginBottom: 8, border: '1px solid #00d4ff11', borderRadius: 2, background: '#020b18' }}>
                  <span className="mono" style={{ fontSize: 9, color: '#334155', letterSpacing: 1 }}>AAR TOKENS</span>
                  <span className="mono" style={{ fontSize: 9, color: '#475569' }}>IN {lastGenerated.usage.input_tokens.toLocaleString()}</span>
                  <span className="mono" style={{ fontSize: 9, color: '#475569' }}>OUT {lastGenerated.usage.output_tokens.toLocaleString()}</span>
                  {(lastGenerated.usage.cache_read_tokens ?? 0) > 0 && (
                    <span className="mono" style={{ fontSize: 9, color: '#334155' }}>CACHE HIT {lastGenerated.usage.cache_read_tokens!.toLocaleString()}</span>
                  )}
                </div>
              )}
              <div style={{ fontSize: 13, lineHeight: 1.75, color: '#94a3b8', fontFamily: 'Georgia, serif' }}>
                <ReactMarkdown
                  components={{
                    h1: ({ children }) => <h1 style={{ fontSize: 15, color: '#00d4ff', letterSpacing: 1, marginBottom: 10, marginTop: 20, fontFamily: 'Courier New' }}>{children}</h1>,
                    h2: ({ children }) => <h2 style={{ fontSize: 12, color: '#00d4ff99', letterSpacing: 1, marginBottom: 6, marginTop: 16, fontFamily: 'Courier New' }}>{children}</h2>,
                    h3: ({ children }) => <h3 style={{ fontSize: 11, color: '#64748b', marginBottom: 4, marginTop: 12, fontFamily: 'Courier New' }}>{children}</h3>,
                    p: ({ children }) => <p style={{ marginBottom: 10, color: '#94a3b8' }}>{children}</p>,
                    strong: ({ children }) => <strong style={{ color: '#e2e8f0' }}>{children}</strong>,
                    ul: ({ children }) => <ul style={{ marginBottom: 10, paddingLeft: 18, color: '#94a3b8' }}>{children}</ul>,
                    li: ({ children }) => <li style={{ marginBottom: 3 }}>{children}</li>,
                    hr: () => <hr style={{ border: 'none', borderTop: '1px solid #00d4ff22', margin: '16px 0' }} />,
                  }}
                >
                  {active.text}
                </ReactMarkdown>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function AARTab() {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listSessions().then(setSessions).catch(() => setError('Failed to load sessions')).finally(() => setLoading(false))
  }, [])

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
          {completed.map((s) => <SessionAarRow key={s.session_id} s={s} />)}
        </div>
      )}
    </div>
  )
}

// ── Scenario Editor tab ───────────────────────────────────────────────────────
const ARCHETYPES = ['mahanian', 'commercial_broker', 'gray_zone', 'rogue_accelerationist']
const ASSET_KEYS = ['leo_nodes', 'meo_nodes', 'geo_nodes', 'cislunar_nodes', 'asat_kinetic', 'asat_deniable', 'ew_jammers', 'sda_sensors', 'launch_capacity'] as const
const INPUT_S: React.CSSProperties = { background: '#020b18', border: '1px solid #00d4ff33', color: '#94a3b8', fontFamily: 'Courier New', fontSize: 11, borderRadius: 2, padding: '3px 6px' }

function makeBlankFaction(): ScenarioFactionDetail {
  return { faction_id: '', name: 'New Faction', archetype: 'mahanian', agent_type: 'rule_based', budget_per_turn: 100, coalition_id: '', coalition_loyalty: 0.5, starting_assets: { leo_nodes: 2 } }
}

function makeBlankDetail(): ScenarioDetail {
  return {
    name: 'New Scenario', description: '', turns: 12, turn_represents: '3 months',
    factions: [makeBlankFaction()],
    coalitions: {},
    victory: { coalition_orbital_dominance: 0.65, individual_conditions_required: true, individual_conditions: {} },
    crisis_events: { library: 'default_2030' },
  }
}

function rebuildCoalitions(factions: ScenarioFactionDetail[], existing: ScenarioDetail['coalitions']): ScenarioDetail['coalitions'] {
  const ids = Array.from(new Set(factions.map((f) => f.coalition_id).filter(Boolean))) as string[]
  const result: ScenarioDetail['coalitions'] = {}
  ids.forEach((cid) => {
    result[cid] = existing[cid] ?? { member_ids: [], shared_intel: true, hegemony_pool: true }
    result[cid] = { ...result[cid], member_ids: factions.filter((f) => f.coalition_id === cid).map((f) => f.faction_id) }
  })
  return result
}

function FactionRow({ faction, index, onChange, onRemove }: {
  faction: ScenarioFactionDetail
  index: number
  onChange: (patch: Partial<ScenarioFactionDetail>) => void
  onRemove: () => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ borderBottom: '1px solid #00d4ff0a', paddingBottom: 8, marginBottom: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 10, color: '#334155', ...MONO, minWidth: 16 }}>{index + 1}.</span>
        <input value={faction.name} onChange={(e) => onChange({ name: e.target.value })}
          style={{ ...INPUT_S, flex: 1 }} placeholder="Faction name" />
        <select value={faction.archetype} onChange={(e) => onChange({ archetype: e.target.value })}
          style={{ ...INPUT_S }}>
          {ARCHETYPES.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <input type="number" value={faction.budget_per_turn} onChange={(e) => onChange({ budget_per_turn: Number(e.target.value) })}
          style={{ ...INPUT_S, width: 54 }} min={0} title="Budget/turn" />
        <button onClick={() => setOpen((v) => !v)} style={{ ...INPUT_S, cursor: 'pointer', padding: '3px 8px', color: open ? '#00d4ff' : '#334155' }}>
          {open ? '▲' : '▼'}
        </button>
        <button onClick={onRemove} style={{ ...INPUT_S, cursor: 'pointer', padding: '3px 8px', color: '#ff4499', borderColor: '#ff449933' }}>✕</button>
      </div>

      {open && (
        <div style={{ marginTop: 8, paddingLeft: 24, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ fontSize: 10, color: '#475569', ...MONO, minWidth: 100 }}>Faction ID</span>
            <input value={faction.faction_id} onChange={(e) => onChange({ faction_id: e.target.value })}
              style={{ ...INPUT_S, flex: 1 }} placeholder="auto-generated from name if blank" />
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ fontSize: 10, color: '#475569', ...MONO, minWidth: 100 }}>Agent type</span>
            <select value={faction.agent_type} onChange={(e) => onChange({ agent_type: e.target.value })} style={{ ...INPUT_S }}>
              <option value="web">Human (web)</option>
              <option value="rule_based">AI — Rule-based</option>
              <option value="ai_commander">AI — Commander</option>
            </select>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ fontSize: 10, color: '#475569', ...MONO, minWidth: 100 }}>Coalition ID</span>
            <input value={faction.coalition_id ?? ''} onChange={(e) => onChange({ coalition_id: e.target.value || undefined })}
              style={{ ...INPUT_S, flex: 1 }} placeholder="leave blank for none" />
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ fontSize: 10, color: '#475569', ...MONO, minWidth: 100 }}>Loyalty</span>
            <input type="range" min={0} max={1} step={0.1} value={faction.coalition_loyalty ?? 0.5}
              onChange={(e) => onChange({ coalition_loyalty: Number(e.target.value) })} style={{ flex: 1 }} />
            <span style={{ fontSize: 10, color: '#64748b', ...MONO, minWidth: 28 }}>{((faction.coalition_loyalty ?? 0.5) * 100).toFixed(0)}%</span>
          </div>
          <div style={{ marginTop: 4 }}>
            <div style={{ fontSize: 10, color: '#475569', ...MONO, marginBottom: 4 }}>STARTING ASSETS</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '4px 12px' }}>
              {ASSET_KEYS.map((k) => (
                <div key={k} style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                  <span style={{ fontSize: 9, color: '#475569', ...MONO, minWidth: 90 }}>{k}</span>
                  <input type="number" min={0} value={faction.starting_assets[k] ?? 0}
                    onChange={(e) => onChange({ starting_assets: { ...faction.starting_assets, [k]: Number(e.target.value) } })}
                    style={{ ...INPUT_S, width: 44 }} />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ScenarioEditorTab() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [detail, setDetail] = useState<ScenarioDetail | null>(null)
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)

  const isNew = selectedId === '__new__'

  useEffect(() => {
    listScenarios().then(setScenarios).catch(() => setError('Failed to load scenarios'))
  }, [])

  function handleSelect(id: string) {
    setError(null); setStatus(null); setConfirmDelete(false)
    setSelectedId(id)
    if (id === '__new__') { setDetail(makeBlankDetail()); return }
    if (!id) { setDetail(null); return }
    getScenario(id).then(setDetail).catch((e) => setError(String(e)))
  }

  function patchDetail(patch: Partial<ScenarioDetail>) {
    setDetail((prev) => prev ? { ...prev, ...patch } : prev)
  }

  function updateFaction(idx: number, patch: Partial<ScenarioFactionDetail>) {
    if (!detail) return
    const factions = detail.factions.map((f, i) => i === idx ? { ...f, ...patch } : f)
    patchDetail({ factions, coalitions: rebuildCoalitions(factions, detail.coalitions) })
  }

  function removeFaction(idx: number) {
    if (!detail) return
    const factions = detail.factions.filter((_, i) => i !== idx)
    patchDetail({ factions, coalitions: rebuildCoalitions(factions, detail.coalitions) })
  }

  function addFaction() {
    if (!detail) return
    patchDetail({ factions: [...detail.factions, makeBlankFaction()] })
  }

  async function handleSave() {
    if (!detail) return
    setSaving(true); setError(null); setStatus(null)
    try {
      const coalitions = rebuildCoalitions(detail.factions, detail.coalitions)
      const payload = { ...detail, coalitions }
      if (isNew) {
        const res = await createScenario(payload)
        const updated = await listScenarios()
        setScenarios(updated)
        setSelectedId(res.scenario_id)
        setStatus('Scenario created.')
      } else {
        await updateScenario(selectedId, payload)
        const updated = await listScenarios()
        setScenarios(updated)
        setStatus('Changes saved.')
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!selectedId || isNew) return
    try {
      await deleteScenario(selectedId)
      const updated = await listScenarios()
      setScenarios(updated)
      setSelectedId(''); setDetail(null); setConfirmDelete(false)
    } catch (e) {
      setError(String(e))
    }
  }

  const inputFull: React.CSSProperties = { ...INPUT_S, width: '100%', padding: '6px 10px', fontSize: 12, marginBottom: 6 }

  return (
    <div style={{ width: '100%', maxWidth: 700 }}>
      {/* Selector row */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
        <select value={selectedId} onChange={(e) => handleSelect(e.target.value)}
          style={{ ...inputFull, marginBottom: 0, flex: 1 }}>
          <option value="">— select scenario to edit —</option>
          {scenarios.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          <option value="__new__">[ + NEW SCENARIO ]</option>
        </select>
        {selectedId && !isNew && (
          confirmDelete ? (
            <>
              <button className="btn-primary" onClick={() => void handleDelete()}
                style={{ fontSize: 10, padding: '4px 12px', borderColor: '#ff4499', color: '#ff4499', whiteSpace: 'nowrap' }}>
                CONFIRM
              </button>
              <button className="btn-primary" onClick={() => setConfirmDelete(false)}
                style={{ fontSize: 10, padding: '4px 12px' }}>
                CANCEL
              </button>
            </>
          ) : (
            <button className="btn-primary" onClick={() => setConfirmDelete(true)}
              style={{ fontSize: 10, padding: '4px 12px', borderColor: '#ff449966', color: '#ff4499', whiteSpace: 'nowrap' }}>
              DELETE
            </button>
          )
        )}
      </div>

      {error && <div style={{ color: '#ff4499', fontSize: 11, marginBottom: 10, ...MONO }}>{error}</div>}
      {status && <div style={{ color: '#00ff88', fontSize: 11, marginBottom: 10, ...MONO }}>{status}</div>}

      {detail && (
        <>
          {/* Basic info */}
          <div className="panel" style={{ marginBottom: 12 }}>
            <div className="panel-title">BASIC INFO</div>
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '4px 12px', alignItems: 'center' }}>
              {([
                ['Name', 'name', 'text'],
                ['Description', 'description', 'text'],
                ['Turn count', 'turns', 'number'],
                ['Turn represents', 'turn_represents', 'text'],
              ] as const).map(([label, key, type]) => (
                <React.Fragment key={key}>
                  <span style={{ fontSize: 10, color: '#475569', ...MONO }}>{label}</span>
                  <input type={type} value={String(detail[key as keyof ScenarioDetail] ?? '')}
                    onChange={(e) => patchDetail({ [key]: type === 'number' ? Number(e.target.value) : e.target.value } as Partial<ScenarioDetail>)}
                    style={{ ...INPUT_S, width: '100%', padding: '4px 8px' }} min={type === 'number' ? 1 : undefined} />
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Factions */}
          <div className="panel" style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div className="panel-title" style={{ marginBottom: 0 }}>FACTIONS</div>
              <button className="btn-primary" onClick={addFaction} style={{ fontSize: 10, padding: '2px 12px' }}>+ ADD</button>
            </div>
            {detail.factions.length === 0 && (
              <div style={{ fontSize: 11, color: '#334155', ...MONO, textAlign: 'center', padding: 12 }}>NO FACTIONS — ADD ONE</div>
            )}
            {detail.factions.map((f, i) => (
              <FactionRow key={i} faction={f} index={i}
                onChange={(patch) => updateFaction(i, patch)}
                onRemove={() => removeFaction(i)} />
            ))}
          </div>

          {/* Coalitions summary */}
          {Object.keys(rebuildCoalitions(detail.factions, detail.coalitions)).length > 0 && (
            <div className="panel" style={{ marginBottom: 12 }}>
              <div className="panel-title">COALITIONS</div>
              {Object.entries(rebuildCoalitions(detail.factions, detail.coalitions)).map(([cid, c]) => (
                <div key={cid} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '4px 0', borderBottom: '1px solid #00d4ff08' }}>
                  <span style={{ fontSize: 11, color: '#e2e8f0', flex: 1, ...MONO }}>{cid}</span>
                  <span style={{ fontSize: 10, color: '#475569', ...MONO }}>{c.member_ids.length} member{c.member_ids.length !== 1 ? 's' : ''}: {c.member_ids.join(', ')}</span>
                  <label style={{ fontSize: 10, color: '#64748b', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <input type="checkbox" checked={c.shared_intel}
                      onChange={(e) => patchDetail({ coalitions: { ...detail.coalitions, [cid]: { ...c, shared_intel: e.target.checked } } })} />
                    shared intel
                  </label>
                  <label style={{ fontSize: 10, color: '#64748b', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <input type="checkbox" checked={c.hegemony_pool}
                      onChange={(e) => patchDetail({ coalitions: { ...detail.coalitions, [cid]: { ...c, hegemony_pool: e.target.checked } } })} />
                    hegemony pool
                  </label>
                </div>
              ))}
            </div>
          )}

          {/* Victory conditions */}
          <div className="panel" style={{ marginBottom: 16 }}>
            <div className="panel-title">VICTORY CONDITIONS</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 10, color: '#475569', ...MONO, minWidth: 160 }}>Orbital dominance threshold</span>
              <input type="range" min={0.5} max={0.9} step={0.05}
                value={detail.victory.coalition_orbital_dominance}
                onChange={(e) => patchDetail({ victory: { ...detail.victory, coalition_orbital_dominance: Number(e.target.value) } })}
                style={{ flex: 1 }} />
              <span style={{ fontSize: 11, color: '#00d4ff', ...MONO, minWidth: 36 }}>
                {Math.round(detail.victory.coalition_orbital_dominance * 100)}%
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 8 }}>
              <span style={{ fontSize: 10, color: '#475569', ...MONO, minWidth: 160 }}>Individual conditions required</span>
              <input type="checkbox" checked={detail.victory.individual_conditions_required}
                onChange={(e) => patchDetail({ victory: { ...detail.victory, individual_conditions_required: e.target.checked } })} />
            </div>
          </div>

          <button className="btn-primary" onClick={() => void handleSave()} disabled={saving} style={{ width: '100%' }}>
            {saving ? 'SAVING...' : isNew ? '[ CREATE SCENARIO ]' : '[ SAVE CHANGES ]'}
          </button>
        </>
      )}
    </div>
  )
}

// ── How To Play tab ───────────────────────────────────────────────────────────
const SECTION: React.CSSProperties = { marginBottom: 20 }
const RULE_LABEL: React.CSSProperties = { fontSize: 10, color: '#00d4ff99', letterSpacing: 2, ...MONO, marginBottom: 6 }
const BODY: React.CSSProperties = { fontSize: 11, color: '#94a3b8', lineHeight: 1.75 }
const ROW: React.CSSProperties = { display: 'flex', gap: 10, padding: '5px 0', borderBottom: '1px solid #00d4ff08', alignItems: 'flex-start' }
const KEY: React.CSSProperties = { fontSize: 10, color: '#00d4ff', ...MONO, minWidth: 130, flexShrink: 0, paddingTop: 1 }
const VAL: React.CSSProperties = { fontSize: 11, color: '#94a3b8', lineHeight: 1.65 }

function HowToPlayTab() {
  return (
    <div style={{ width: '100%', maxWidth: 700, display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* Overview */}
      <div className="panel">
        <div className="panel-title">OVERVIEW</div>
        <p style={BODY}>
          Astrakon is a turn-based orbital strategy simulation. Two coalitions of spacefaring factions compete
          to achieve <span style={{ color: '#00d4ff' }}>orbital dominance</span> — measured as the fraction of
          total deployed satellite nodes controlled by a coalition. Exceed the victory threshold before your
          opponent and the game ends. If neither side reaches the threshold, the coalition with higher
          dominance when turns expire wins.
        </p>
        <p style={{ ...BODY, marginTop: 8 }}>
          Each faction has its own budget, archetype, and starting assets. Factions within a coalition share
          intelligence and contribute to a common dominance score, but compete independently in operations.
        </p>
      </div>

      {/* Orbital Shells */}
      <div className="panel">
        <div className="panel-title">ORBITAL SHELLS</div>
        <p style={{ ...BODY, marginBottom: 10 }}>
          The operational theater is divided into four orbital shells, each with distinct strategic value and
          delta-V cost to reach.
        </p>
        {[
          ['LEO  ·  9.4 km/s', 'Low Earth Orbit. Cheap to access, easy to contest. Dense with ISR and SDA nodes. High debris risk — a Kessler event here blocks the shell entirely.'],
          ['MEO  ·  +1.5 km/s', 'Medium Earth Orbit. The navigation and GNSS hub. Moderate maneuver cost. Less contested but strategically critical for precision operations.'],
          ['GEO  ·  +1.8 km/s', 'Geostationary Orbit. Scarce slots with permanent line-of-sight. Persistent comms and early-warning assets sit here. High delta-V to reach and vacate.'],
          ['CIS  ·  +0.7 km/s', 'Cislunar space including L1, L2, L4, L5, and lunar orbit. Frontier territory — dynamic access windows and extreme range from Earth. Controls future logistics chokepoints.'],
        ].map(([label, desc]) => (
          <div key={label} style={ROW}>
            <span style={KEY}>{label}</span>
            <span style={VAL}>{desc}</span>
          </div>
        ))}
        <p style={{ ...BODY, marginTop: 10, color: '#64748b' }}>
          Access windows open and close each turn. A shell marked CLOSED cannot receive new assets that turn.
          Kessler debris (debris index ≥ 0.80) renders a shell impassable — existing nodes are destroyed.
        </p>
      </div>

      {/* Delta-V Tab */}
      <div className="panel">
        <div className="panel-title">THE DELTA-V TAB</div>
        <p style={{ ...BODY, marginBottom: 10 }}>
          The game map has two views. The <span style={{ color: '#00d4ff' }}>ORBITAL</span> tab shows where assets are
          positioned spatially. The <span style={{ color: '#00d4ff' }}>DELTA-V</span> tab answers a different
          question: <em style={{ color: '#e2e8f0' }}>how expensive is it to project force between shells?</em>
        </p>
        <p style={{ ...BODY, marginBottom: 14 }}>
          The graph arranges shells as a vertical cost ladder — Earth at the bottom, cislunar at the top.
          Each edge is labeled with the incremental delta-V required to maneuver between adjacent shells.
          Edge color encodes cost tier:
        </p>
        {[
          ['Green  ·  ≤ 1.0 km/s', 'Low cost. Rapid redeployment or reinforcement is viable.'],
          ['Yellow  ·  1.0–2.0 km/s', 'Moderate cost. Maneuver is possible but consumes meaningful budget.'],
          ['Red  ·  > 2.0 km/s', 'High cost. Sustained presence here requires upfront investment — you cannot cheaply surge or retreat.'],
        ].map(([label, desc]) => (
          <div key={label} style={ROW}>
            <span style={KEY}>{label}</span>
            <span style={VAL}>{desc}</span>
          </div>
        ))}

        <div style={{ ...RULE_LABEL, marginTop: 16 }}>COST STRUCTURE AND WHAT IT MEANS</div>
        {[
          ['LEO  →  MEO  (1.5 km/s)', 'Affordable but not free. Factions that flood LEO early can pivot upward, but MEO competition requires real budget commitment. LEO is the easiest shell to contest — and the easiest to lose.'],
          ['MEO  →  GEO  (1.8 km/s)', 'The most expensive single hop in the theater. GEO nodes are hard to reach and hard to replace. A faction that establishes GEO presence early gains a structural advantage: adversaries must pay 1.8 km/s to match them, while the GEO holder pays nothing to hold.'],
          ['GEO  →  CIS  (0.7 km/s)', 'The cheapest hop. Cislunar is surprisingly accessible if you already hold GEO — the gate to the frontier is cheap once you\'re in geostationary. But reaching CIS from LEO requires passing through the expensive MEO→GEO crossing first.'],
        ].map(([label, desc]) => (
          <div key={label} style={ROW}>
            <span style={KEY}>{label}</span>
            <span style={VAL}>{desc}</span>
          </div>
        ))}

        <div style={{ ...RULE_LABEL, marginTop: 16 }}>READING THE GRAPH STRATEGICALLY</div>
        <p style={BODY}>
          Each node displays a <span style={{ color: '#00d4ff' }}>faction presence bar</span> — a stacked color
          strip showing each coalition's share of nodes in that shell. Nodes pulse when their shell's access
          window is open. Kessler-blocked shells render red with a BLOCKED indicator.
        </p>
        <p style={{ ...BODY, marginTop: 8 }}>
          Clicking a node highlights it and dims all others, syncing selection with the ORBITAL tab — both
          views show the same selection state, so you can pivot between spatial context and cost analysis
          without losing your focus.
        </p>
        <p style={{ ...BODY, marginTop: 8 }}>
          Use the Delta-V tab to identify leverage points: a coalition that controls the MEO→GEO crossing
          makes it expensive for adversaries to reach the two highest-value shells. A dominant CIS presence
          built on a weak GEO foundation is brittle — your opponent only needs to contest GEO to cut off
          your logistics corridor.
        </p>
      </div>

      {/* Setup */}
      <div className="panel" style={SECTION}>
        <div className="panel-title">SETUP</div>
        <div style={RULE_LABEL}>SCENARIO</div>
        <p style={{ ...BODY, marginBottom: 10 }}>
          Select a pre-built scenario or one you have created in the Scenario Editor. Each scenario defines
          the factions, their starting assets, the number of turns, and the orbital dominance threshold needed
          to win.
        </p>
        <div style={RULE_LABEL}>CONFIGURE FACTIONS</div>
        {[
          ['Human (web)', 'You control this faction\'s decisions each turn through the game interface.'],
          ['AI — Rule-based', 'A scripted agent follows archetype-specific heuristics. Fast and predictable. Good for filling out a coalition or running AI-vs-AI simulations.'],
          ['AI — Commander', 'A language-model agent reasons through the situation and generates orders. Slower per turn but exhibits more adaptive, emergent behavior.'],
        ].map(([label, desc]) => (
          <div key={label} style={ROW}>
            <span style={KEY}>{label}</span>
            <span style={VAL}>{desc}</span>
          </div>
        ))}
        <div style={{ ...ROW, marginTop: 10 }}>
          <span style={KEY}>Advisor</span>
          <span style={VAL}>
            Available for Human factions. An AI Commander analyzes the current game state and suggests
            investment and operational priorities before you submit orders. Advisory text appears in the
            game interface. It does not submit orders on your behalf.
          </span>
        </div>
        <p style={{ ...BODY, marginTop: 10, color: '#64748b' }}>
          At least one faction must be set to Human to start a game. Use <span style={{ color: '#f59e0b' }}>WATCH AI vs AI</span> to
          run a fully automated simulation as a spectator.
        </p>
      </div>

      {/* Turn Phases */}
      <div className="panel">
        <div className="panel-title">TURN PHASES</div>
        <p style={{ ...BODY, marginBottom: 10 }}>Each turn resolves in three sequential phases:</p>
        {[
          ['1 · INVEST', 'Allocate your budget across asset categories. Nodes extend your presence in a shell. EW jammers suppress enemy sensors. SDA sensors reveal adversary estimates. ASAT weapons enable strike options. Launch capacity sets the maximum new assets you can field next turn.'],
          ['2 · OPERATIONS', 'Issue operational orders — deploy assets to shells, activate jammers, or declare ASAT strikes. Kinetic strikes against a shell are announced and resolved next turn; deniable operations are covert. Orders are submitted simultaneously across all factions.'],
          ['3 · RESPONSE', 'Respond to declared threats before they resolve. You may attempt intercepts, reposition assets, or accept the incoming strike. Coalition partners\' intelligence is shared — adversary node estimates update based on SDA coverage.'],
        ].map(([label, desc]) => (
          <div key={label} style={ROW}>
            <span style={{ ...KEY, minWidth: 130 }}>{label}</span>
            <span style={VAL}>{desc}</span>
          </div>
        ))}
      </div>

      {/* Assets */}
      <div className="panel">
        <div className="panel-title">ASSETS</div>
        {[
          ['Nodes (LEO/MEO/GEO/CIS)', 'Satellite nodes deployed in a shell. Node count is the primary input to dominance calculation. Nodes can be destroyed by ASAT strikes or Kessler events.'],
          ['ASAT — Kinetic', 'Declared strike capability. Target shell is announced on declaration; strike resolves the following turn. Defender has one turn to respond. Generates debris, raising Kessler risk.'],
          ['ASAT — Deniable', 'Covert strike capability. No prior announcement. Resolves immediately with no defender response window. Lower debris generation.'],
          ['EW Jammers', 'Electronic warfare assets that degrade enemy SDA sensors in the same or lower shells. Jammed sensors report no adversary node data.'],
          ['SDA Sensors', 'Space Domain Awareness assets. Each sensor in a shell reveals adversary node counts in that shell and adjacent shells. Without SDA coverage, you see only estimates.'],
          ['Launch Capacity', 'Sets the ceiling on how many new assets can be fielded per turn across all shells. Higher capacity enables faster build-up and recovery after losses.'],
        ].map(([label, desc]) => (
          <div key={label} style={ROW}>
            <span style={KEY}>{label}</span>
            <span style={VAL}>{desc}</span>
          </div>
        ))}
      </div>

      {/* Dominance & Victory */}
      <div className="panel">
        <div className="panel-title">DOMINANCE {'&'} VICTORY</div>
        <p style={BODY}>
          Orbital dominance is the share of all deployed nodes controlled by a coalition, weighted by shell.
          The dominance strip at the bottom of the game map shows each coalition's current score and
          turn-over-turn delta.
        </p>
        <p style={{ ...BODY, marginTop: 8 }}>
          A coalition wins immediately when its dominance crosses the scenario's victory threshold (default 60%).
          If neither coalition reaches the threshold by the final turn, the higher score wins. The
          dominance timeline in the OPS tab shows the full trajectory across all turns.
        </p>
      </div>

      {/* Escalation */}
      <div className="panel">
        <div className="panel-title">ESCALATION LADDER</div>
        <p style={{ ...BODY, marginBottom: 10 }}>
          Crisis events and ASAT strikes raise the escalation rung. Higher rungs unlock more destructive
          options but risk triggering irreversible outcomes.
        </p>
        {[
          ['RUNG 0', 'Peacetime competition. Covert operations only. No declared strikes authorized.'],
          ['RUNG 1', 'Signaling. Deniable operations ongoing. Kinetic options are on the table but not yet exercised.'],
          ['RUNG 2', 'Reversible escalation. First declared ASAT strikes. Debris accumulation begins. De-escalation still possible.'],
          ['RUNG 3', 'Active hostilities. Multiple kinetic exchanges. Kessler risk elevated. Coalition cohesion begins to strain.'],
          ['RUNG 4', 'Full orbital conflict. Sustained strikes across shells. Kessler events likely. Faction defection risk increases.'],
          ['RUNG 5', 'Uncontrolled escalation. Runaway debris, multi-shell Kessler cascade possible. Game end may be forced.'],
        ].map(([label, desc]) => (
          <div key={label} style={ROW}>
            <span style={{ ...KEY, minWidth: 80, color: label === 'RUNG 0' ? '#00ff88' : label === 'RUNG 1' ? '#00d4ff' : label === 'RUNG 2' ? '#f59e0b' : label === 'RUNG 3' ? '#f97316' : '#ef4444' }}>{label}</span>
            <span style={VAL}>{desc}</span>
          </div>
        ))}
      </div>

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
        {tab === 'SCENARIO EDITOR' && <ScenarioEditorTab />}
        {tab === 'HOW TO PLAY' && <HowToPlayTab />}
      </div>
    </div>
  )
}
