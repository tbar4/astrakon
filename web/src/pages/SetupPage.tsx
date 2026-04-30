// web/src/pages/SetupPage.tsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { listScenarios, createGame, advance } from '../api/client'
import { useGameStore } from '../store/gameStore'
import type { ScenarioSummary, AgentConfig } from '../types'

export default function SetupPage() {
  const navigate = useNavigate()
  const { setSession, setGameState, setLoading, isLoading } = useGameStore()
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [agentConfig, setAgentConfig] = useState<AgentConfig[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listScenarios().then((s) => {
      setScenarios(s)
      if (s.length > 0) {
        setSelectedId(s[0].id)
        initConfig(s[0])
      }
    }).catch(() => setError('Failed to load scenarios — is the API server running?'))
  }, [])

  function initConfig(scenario: ScenarioSummary) {
    const config: AgentConfig[] = scenario.factions.map((f, i) => ({
      faction_id: f.faction_id,
      agent_type: i === 0 ? 'web' : 'rule_based',
      use_advisor: false,
    }))
    setAgentConfig(config)
  }

  function handleScenarioChange(id: string) {
    setSelectedId(id)
    const s = scenarios.find((s) => s.id === id)
    if (s) initConfig(s)
  }

  function setAgentType(factionId: string, type: AgentConfig['agent_type']) {
    setAgentConfig((prev) =>
      prev.map((c) => c.faction_id === factionId ? { ...c, agent_type: type } : c)
    )
  }

  function setUseAdvisor(factionId: string, use: boolean) {
    setAgentConfig((prev) =>
      prev.map((c) => c.faction_id === factionId ? { ...c, use_advisor: use } : c)
    )
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
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 40 }}>
      <div style={{ marginBottom: 32, textAlign: 'center' }}>
        <div className="mono" style={{ fontSize: 28, color: '#00d4ff', letterSpacing: 8 }}>◆ ASTRAKON ◆</div>
        <div className="mono" style={{ fontSize: 11, color: '#00d4ff66', letterSpacing: 3, marginTop: 6 }}>ORBITAL STRATEGY SIMULATION</div>
      </div>

      {error && (
        <div className="panel" style={{ borderColor: '#ff4499', color: '#ff4499', marginBottom: 20, fontSize: 12 }}>
          {error}
        </div>
      )}

      <div className="panel" style={{ width: '100%', maxWidth: 600 }}>
        <div className="panel-title">SELECT SCENARIO</div>
        <select
          value={selectedId}
          onChange={(e) => handleScenarioChange(e.target.value)}
          style={{
            width: '100%', background: '#020b18', border: '1px solid #00d4ff33',
            color: '#94a3b8', padding: '8px 12px', fontFamily: 'Courier New',
            fontSize: 12, marginBottom: 8, borderRadius: 2,
          }}
        >
          {scenarios.map((s) => (
            <option key={s.id} value={s.id}>{s.name} ({s.turns} turns)</option>
          ))}
        </select>
        {selected && (
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 20 }}>{selected.description}</div>
        )}

        {selected && (
          <>
            <div className="panel-title" style={{ marginTop: 16 }}>CONFIGURE FACTIONS</div>
            {selected.factions.map((f) => {
              const cfg = agentConfig.find((c) => c.faction_id === f.faction_id)
              if (!cfg) return null
              return (
                <div key={f.faction_id} style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '8px 0', borderBottom: '1px solid #00d4ff11',
                }}>
                  <div style={{ flex: 1, fontSize: 12, color: '#e2e8f0' }}>{f.name}</div>
                  <select
                    value={cfg.agent_type}
                    onChange={(e) => setAgentType(f.faction_id, e.target.value as AgentConfig['agent_type'])}
                    style={{
                      background: '#020b18', border: '1px solid #00d4ff33',
                      color: '#94a3b8', padding: '4px 8px', fontFamily: 'Courier New',
                      fontSize: 11, borderRadius: 2,
                    }}
                  >
                    <option value="web">Human (web)</option>
                    <option value="rule_based">AI — Rule-based</option>
                    <option value="ai_commander">AI — Commander</option>
                  </select>
                  {cfg.agent_type === 'web' && (
                    <label style={{ fontSize: 11, color: '#64748b', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <input
                        type="checkbox"
                        checked={cfg.use_advisor}
                        onChange={(e) => setUseAdvisor(f.faction_id, e.target.checked)}
                      />
                      advisor
                    </label>
                  )}
                </div>
              )
            })}
          </>
        )}

        <button
          className="btn-primary"
          onClick={handleStart}
          disabled={isLoading || !selectedId}
          style={{ marginTop: 24, width: '100%' }}
        >
          {isLoading ? 'INITIALIZING...' : '[ LAUNCH SIMULATION ]'}
        </button>
      </div>
    </div>
  )
}
