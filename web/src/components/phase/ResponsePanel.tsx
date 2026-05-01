// web/src/components/phase/ResponsePanel.tsx
import { useState } from 'react'

interface Props {
  factionNames: Record<string, string>
  humanFactionId: string
  turnLogSummary: string
  onSubmit: (decision: Record<string, unknown>) => void
  disabled: boolean
}

export default function ResponsePanel({ factionNames, humanFactionId, turnLogSummary, onSubmit, disabled }: Props) {
  const [escalate, setEscalate] = useState(false)
  const [retaliate, setRetaliate] = useState(false)
  const [targetFaction, setTargetFaction] = useState('')
  const [statement, setStatement] = useState('')
  const [rationale, setRationale] = useState('')

  const otherFactions = Object.entries(factionNames).filter(([fid]) => fid !== humanFactionId)

  function handleSubmit() {
    onSubmit({
      response: {
        escalate,
        retaliate: escalate && retaliate,
        target_faction: (escalate && retaliate && targetFaction) ? targetFaction : undefined,
        public_statement: statement,
        rationale,
      },
    })
  }

  return (
    <div>
      <div className="panel-title">◆ RESPONSE PHASE</div>

      {turnLogSummary && (
        <div style={{
          background: '#0a0a14', border: '1px solid #00d4ff11',
          padding: '8px 10px', fontSize: 12, color: '#475569',
          fontFamily: 'Courier New', marginBottom: 12, borderRadius: 2,
          whiteSpace: 'pre-line',
        }}>
          {turnLogSummary}
        </div>
      )}

      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'flex', gap: 10, cursor: 'pointer', alignItems: 'center' }}>
          <input
            type="checkbox" checked={escalate}
            onChange={(e) => { setEscalate(e.target.checked); if (!e.target.checked) setRetaliate(false) }}
            disabled={disabled}
            style={{ accentColor: '#ff4499', width: 16, height: 16 }}
          />
          <div>
            <div style={{ fontSize: 13, color: escalate ? '#ff4499' : '#94a3b8' }}>ESCALATE</div>
            <div style={{ fontSize: 12, color: '#475569' }}>Raises tension +15% · unlocks harder actions next turn</div>
          </div>
        </label>

        {escalate && (
          <div style={{ marginTop: 10, paddingLeft: 26 }}>
            <label style={{ display: 'flex', gap: 10, cursor: 'pointer', alignItems: 'center', marginBottom: 8 }}>
              <input
                type="checkbox" checked={retaliate}
                onChange={(e) => setRetaliate(e.target.checked)}
                disabled={disabled}
                style={{ accentColor: '#ff4499', width: 14, height: 14 }}
              />
              <span style={{ fontSize: 13, color: retaliate ? '#ff4499' : '#64748b' }}>Retaliate against faction</span>
            </label>
            {retaliate && (
              <select
                value={targetFaction}
                onChange={(e) => setTargetFaction(e.target.value)}
                disabled={disabled}
                style={{
                  width: '100%', background: '#020b18', border: '1px solid #ff449933',
                  color: '#94a3b8', padding: '6px 8px', fontFamily: 'Courier New',
                  fontSize: 13, borderRadius: 2,
                }}
              >
                <option value="">— select target —</option>
                {otherFactions.map(([fid, name]) => (
                  <option key={fid} value={fid}>{name}</option>
                ))}
              </select>
            )}
          </div>
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 11 }}>PUBLIC STATEMENT (optional)</div>
        <input
          type="text"
          value={statement}
          onChange={(e) => setStatement(e.target.value)}
          placeholder="Official statement to release..."
          disabled={disabled}
          style={{
            width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
            color: '#94a3b8', padding: '6px 8px', fontFamily: 'system-ui',
            fontSize: 13, borderRadius: 2, boxSizing: 'border-box',
          }}
        />
      </div>

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 11 }}>RATIONALE</div>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Strategic rationale for your response..."
          disabled={disabled}
          style={{
            width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
            color: '#94a3b8', padding: '6px 8px', fontFamily: 'system-ui',
            fontSize: 13, resize: 'vertical', minHeight: 60, borderRadius: 2,
            boxSizing: 'border-box',
          }}
        />
      </div>

      <button
        className="btn-primary"
        onClick={handleSubmit}
        disabled={disabled || !rationale.trim()}
        style={{ width: '100%' }}
      >
        [ SUBMIT RESPONSE ]
      </button>
    </div>
  )
}
