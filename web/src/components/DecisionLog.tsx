// web/src/components/DecisionLog.tsx
import { useState, useEffect } from 'react'
import { getHistory } from '../api/client'
import type { HistoryData } from '../api/client'

interface Props {
  sessionId: string
  scenarioName: string
  onClose: () => void
}

type LogTab = 'DECISIONS' | 'EVENTS' | 'DIVERGENCE' | 'TOKENS'

const MONO: React.CSSProperties = { fontFamily: 'Courier New' }

const PHASE_COLOR: Record<string, string> = {
  invest: '#00d4ff',
  operations: '#f59e0b',
  response: '#ff4499',
}

function phaseColor(phase: string) {
  return PHASE_COLOR[phase] ?? '#64748b'
}

function severityBar(s: number) {
  const filled = Math.round(s * 5)
  return '█'.repeat(filled) + '░'.repeat(5 - filled)
}

function exportJson(data: HistoryData, sessionId: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `astrakon-history-${sessionId.slice(0, 8)}.json`
  a.click()
  URL.revokeObjectURL(url)
}

export default function DecisionLog({ sessionId, scenarioName, onClose }: Props) {
  const [tab, setTab] = useState<LogTab>('DECISIONS')
  const [data, setData] = useState<HistoryData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterFaction, setFilterFaction] = useState('')
  const [filterTurn, setFilterTurn] = useState('')

  useEffect(() => {
    getHistory(sessionId)
      .then(setData)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [sessionId])

  const factions = data ? [...new Set(data.decisions.map((d) => d.faction_id))].sort() : []

  const filteredDecisions = data?.decisions.filter((d) => {
    if (filterFaction && d.faction_id !== filterFaction) return false
    if (filterTurn && String(d.turn) !== filterTurn) return false
    return true
  }) ?? []

  const filteredEvents = data?.events.filter((e) => {
    if (filterTurn && String(e.turn) !== filterTurn) return false
    return true
  }) ?? []

  // Group decisions by turn
  const decisionsByTurn = filteredDecisions.reduce<Record<number, typeof filteredDecisions>>((acc, d) => {
    ;(acc[d.turn] ??= []).push(d)
    return acc
  }, {})

  const eventsByTurn = filteredEvents.reduce<Record<number, typeof filteredEvents>>((acc, e) => {
    ;(acc[e.turn] ??= []).push(e)
    return acc
  }, {})

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 100,
      background: 'rgba(2,11,24,0.96)', display: 'flex', flexDirection: 'column',
    }}>
      {/* Header */}
      <div style={{
        padding: '10px 20px', borderBottom: '1px solid #00d4ff22',
        display: 'flex', alignItems: 'center', gap: 16, flexShrink: 0, background: '#020b18',
      }}>
        <span className="mono" style={{ color: '#00d4ff', fontSize: 12, letterSpacing: 3 }}>◆ DECISION LOG</span>
        <span className="mono" style={{ color: '#64748b', fontSize: 10 }}>·</span>
        <span className="mono" style={{ color: '#64748b', fontSize: 10 }}>{scenarioName}</span>
        <span style={{ flex: 1 }} />
        {data && (
          <button className="btn-primary" onClick={() => exportJson(data, sessionId)}
            style={{ fontSize: 10, padding: '2px 10px', borderColor: '#00ff88', color: '#00ff88' }}>
            EXPORT JSON
          </button>
        )}
        <button className="btn-primary" onClick={onClose}
          style={{ fontSize: 10, padding: '2px 10px', borderColor: '#334155', color: '#64748b' }}>
          ✕ CLOSE [L]
        </button>
      </div>

      {/* Tab bar + filters */}
      <div style={{
        padding: '0 20px', borderBottom: '1px solid #00d4ff11',
        display: 'flex', alignItems: 'center', gap: 16, flexShrink: 0, background: '#020b18',
      }}>
        <div style={{ display: 'flex', gap: 0 }}>
          {(['DECISIONS', 'EVENTS', 'DIVERGENCE', 'TOKENS'] as LogTab[]).map((t) => (
            <button key={t} onClick={() => setTab(t)} style={{
              background: 'none', border: 'none',
              borderBottom: tab === t ? '2px solid #00d4ff' : '2px solid transparent',
              color: tab === t ? '#00d4ff' : '#64748b',
              fontFamily: 'Courier New', fontSize: 10, letterSpacing: 2,
              padding: '8px 14px', cursor: 'pointer', marginBottom: -1,
            }}>{t}</button>
          ))}
        </div>
        <span style={{ flex: 1 }} />
        {/* Filters (shown for DECISIONS and EVENTS) */}
        {(tab === 'DECISIONS' || tab === 'EVENTS') && data && (
          <>
            <input placeholder="Turn #" value={filterTurn} onChange={(e) => setFilterTurn(e.target.value)}
              style={{ width: 60, ...MONO, background: '#020b18', border: '1px solid #00d4ff22', color: '#94a3b8', padding: '3px 8px', fontSize: 10, borderRadius: 2 }} />
            {tab === 'DECISIONS' && (
              <select value={filterFaction} onChange={(e) => setFilterFaction(e.target.value)}
                style={{ ...MONO, background: '#020b18', border: '1px solid #00d4ff22', color: '#94a3b8', padding: '3px 8px', fontSize: 10, borderRadius: 2 }}>
                <option value="">All Factions</option>
                {factions.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            )}
          </>
        )}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
        {loading && <div className="mono" style={{ color: '#64748b', fontSize: 11 }}>LOADING AUDIT DATA...</div>}
        {error && <div className="mono" style={{ color: '#ff4499', fontSize: 11 }}>{error}</div>}

        {/* DECISIONS tab */}
        {tab === 'DECISIONS' && data && (
          Object.keys(decisionsByTurn).length === 0
            ? <div className="mono" style={{ color: '#64748b', fontSize: 11, textAlign: 'center', marginTop: 40 }}>NO DECISIONS RECORDED</div>
            : Object.entries(decisionsByTurn)
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([turn, decisions]) => (
                  <div key={turn} style={{ marginBottom: 24 }}>
                    <div className="mono" style={{ fontSize: 10, color: '#00d4ff44', letterSpacing: 3, marginBottom: 10, borderBottom: '1px solid #00d4ff11', paddingBottom: 4 }}>
                      ── TURN {turn} ──────────────────────────────────
                    </div>
                    {decisions.map((d) => (
                      <div key={d.id} style={{ marginBottom: 12, padding: '10px 12px', background: 'rgba(0,212,255,0.03)', border: '1px solid #00d4ff0a', borderRadius: 3 }}>
                        <div style={{ display: 'flex', gap: 12, marginBottom: 6, alignItems: 'center' }}>
                          <span className="mono" style={{ fontSize: 10, color: phaseColor(d.phase), letterSpacing: 2 }}>{d.phase.toUpperCase()}</span>
                          <span className="mono" style={{ fontSize: 10, color: '#64748b' }}>{d.faction_id}</span>
                          <span style={{ flex: 1 }} />
                          <span className="mono" style={{ fontSize: 9, color: '#1e3a4a' }}>{new Date(d.timestamp).toLocaleTimeString()}</span>
                        </div>
                        {d.rationale && (
                          <div style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{d.rationale}</div>
                        )}
                      </div>
                    ))}
                  </div>
                ))
        )}

        {/* EVENTS tab */}
        {tab === 'EVENTS' && data && (
          Object.keys(eventsByTurn).length === 0
            ? <div className="mono" style={{ color: '#64748b', fontSize: 11, textAlign: 'center', marginTop: 40 }}>NO EVENTS RECORDED</div>
            : Object.entries(eventsByTurn)
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([turn, events]) => (
                  <div key={turn} style={{ marginBottom: 24 }}>
                    <div className="mono" style={{ fontSize: 10, color: '#f59e0b44', letterSpacing: 3, marginBottom: 10, borderBottom: '1px solid #f59e0b11', paddingBottom: 4 }}>
                      ── TURN {turn} ──────────────────────────────────
                    </div>
                    {events.map((e, i) => (
                      <div key={i} style={{ marginBottom: 10, padding: '8px 12px', background: 'rgba(245,158,11,0.03)', border: '1px solid #f59e0b0a', borderRadius: 3 }}>
                        <div style={{ display: 'flex', gap: 12, marginBottom: 4, alignItems: 'center' }}>
                          <span className="mono" style={{ fontSize: 10, color: '#f59e0b', letterSpacing: 1 }}>{severityBar(e.severity)} {e.event_type.toUpperCase()}</span>
                          <span style={{ flex: 1 }} />
                          <span className="mono" style={{ fontSize: 9, color: '#64748b' }}>triggered by {e.triggered_by}</span>
                        </div>
                        <div style={{ fontSize: 11, color: '#94a3b8' }}>{e.description}</div>
                      </div>
                    ))}
                  </div>
                ))
        )}

        {/* DIVERGENCE tab */}
        {tab === 'DIVERGENCE' && data && (
          data.divergences.length === 0
            ? <div className="mono" style={{ color: '#64748b', fontSize: 11, textAlign: 'center', marginTop: 40 }}>NO ADVISOR DIVERGENCES RECORDED</div>
            : data.divergences.map((d) => (
                <div key={d.id} style={{ marginBottom: 16, padding: '12px', background: 'rgba(245,158,11,0.03)', border: '1px solid #f59e0b11', borderRadius: 3 }}>
                  <div style={{ display: 'flex', gap: 12, marginBottom: 10, alignItems: 'center' }}>
                    <span className="mono" style={{ fontSize: 10, color: phaseColor(d.phase) }}>T{d.turn} · {d.phase.toUpperCase()}</span>
                    <span className="mono" style={{ fontSize: 10, color: '#64748b' }}>{d.faction_id}</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <div>
                      <div className="mono" style={{ fontSize: 9, color: '#f59e0b66', marginBottom: 4, letterSpacing: 2 }}>ADVISOR RECOMMENDED</div>
                      <pre style={{ fontSize: 10, color: '#64748b', whiteSpace: 'pre-wrap', ...MONO, margin: 0 }}>
                        {JSON.stringify(JSON.parse(d.recommendation_json), null, 2)}
                      </pre>
                    </div>
                    <div>
                      <div className="mono" style={{ fontSize: 9, color: '#00d4ff66', marginBottom: 4, letterSpacing: 2 }}>HUMAN DECIDED</div>
                      <pre style={{ fontSize: 10, color: '#64748b', whiteSpace: 'pre-wrap', ...MONO, margin: 0 }}>
                        {JSON.stringify(JSON.parse(d.final_decision_json), null, 2)}
                      </pre>
                    </div>
                  </div>
                </div>
              ))
        )}

        {/* TOKENS tab */}
        {tab === 'TOKENS' && data && (
          data.token_summary.length === 0
            ? <div className="mono" style={{ color: '#64748b', fontSize: 11, textAlign: 'center', marginTop: 40 }}>NO TOKEN DATA RECORDED</div>
            : (
              <div className="panel">
                <div className="panel-title">TOKEN USAGE BY FACTION</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 4rem 4rem 4rem 4rem', columnGap: 12, rowGap: 6 }}>
                  {['FACTION', 'ROLE', 'IN', 'OUT', 'CACHE-R', 'CACHE-W'].map((h) => (
                    <div key={h} className="mono" style={{ fontSize: 9, color: '#64748b', letterSpacing: 1, paddingBottom: 4, borderBottom: '1px solid #00d4ff11' }}>{h}</div>
                  ))}
                  {data.token_summary.map((row, i) => (
                    <>
                      <div key={`${i}-f`} style={{ fontSize: 10, color: '#94a3b8', ...MONO }}>{row.faction_id}</div>
                      <div key={`${i}-r`} style={{ fontSize: 10, color: '#64748b', ...MONO }}>{row.role}</div>
                      <div key={`${i}-in`} style={{ fontSize: 10, color: '#00d4ff', ...MONO, textAlign: 'right' }}>{row.input_tokens.toLocaleString()}</div>
                      <div key={`${i}-out`} style={{ fontSize: 10, color: '#00ff88', ...MONO, textAlign: 'right' }}>{row.output_tokens.toLocaleString()}</div>
                      <div key={`${i}-cr`} style={{ fontSize: 10, color: '#64748b', ...MONO, textAlign: 'right' }}>{row.cache_read_tokens.toLocaleString()}</div>
                      <div key={`${i}-cw`} style={{ fontSize: 10, color: '#64748b', ...MONO, textAlign: 'right' }}>{row.cache_creation_tokens.toLocaleString()}</div>
                    </>
                  ))}
                </div>
              </div>
            )
        )}
      </div>
    </div>
  )
}
