// web/src/components/phase/OpsPanel.tsx
import { useState } from 'react'

interface Props {
  factionNames: Record<string, string>
  humanFactionId: string
  onSubmit: (decision: Record<string, unknown>) => void
  disabled: boolean
}

const ACTION_TYPES = [
  { key: 'task_assets', label: 'Task Assets', desc: 'Surveillance, patrol, or kinetic intercept' },
  { key: 'coordinate', label: 'Coordinate', desc: 'Synchronize with coalition ally (+SDA bonus)' },
  { key: 'gray_zone', label: 'Gray Zone', desc: 'Deniable activity — ASAT-deniable or EW jamming' },
  { key: 'alliance_move', label: 'Alliance Move', desc: 'Reinforce partner or shift alignment' },
  { key: 'signal', label: 'Signal', desc: 'Deliberate public or back-channel communication' },
] as const

const MISSIONS = [
  { key: 'sda_sweep', label: 'SDA Sweep — intelligence only' },
  { key: 'patrol', label: 'Patrol — shows resolve' },
  { key: 'intercept', label: 'Intercept — kinetic, arrives next turn' },
] as const

type ActionKey = typeof ACTION_TYPES[number]['key']

export default function OpsPanel({ factionNames, humanFactionId, onSubmit, disabled }: Props) {
  const [actionType, setActionType] = useState<ActionKey>('task_assets')
  const [target, setTarget] = useState('')
  const [mission, setMission] = useState('sda_sweep')
  const [rationale, setRationale] = useState('')

  const otherFactions = Object.entries(factionNames).filter(([fid]) => fid !== humanFactionId)

  function handleSubmit() {
    const params: Record<string, string> = {}
    if (actionType === 'task_assets') params.mission = mission
    onSubmit({
      operations: [{
        action_type: actionType,
        target_faction: target || undefined,
        parameters: params,
        rationale,
      }],
    })
  }

  return (
    <div>
      <div className="panel-title">◆ OPERATIONS PHASE</div>

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 9 }}>ACTION TYPE</div>
        {ACTION_TYPES.map(({ key, label, desc }) => (
          <label key={key} style={{
            display: 'flex', alignItems: 'flex-start', gap: 8,
            padding: '6px 0', borderBottom: '1px solid #00d4ff08', cursor: 'pointer',
          }}>
            <input
              type="radio" name="action" value={key}
              checked={actionType === key}
              onChange={() => setActionType(key)}
              disabled={disabled}
              style={{ marginTop: 2, accentColor: '#00d4ff' }}
            />
            <div>
              <div style={{ fontSize: 12, color: '#e2e8f0' }}>{label}</div>
              <div style={{ fontSize: 10, color: '#475569' }}>{desc}</div>
            </div>
          </label>
        ))}
      </div>

      {actionType === 'task_assets' && (
        <div style={{ marginBottom: 12 }}>
          <div className="panel-title" style={{ fontSize: 9 }}>MISSION</div>
          {MISSIONS.map(({ key, label }) => (
            <label key={key} style={{ display: 'flex', gap: 8, padding: '4px 0', cursor: 'pointer' }}>
              <input
                type="radio" name="mission" value={key}
                checked={mission === key}
                onChange={() => setMission(key)}
                disabled={disabled}
                style={{ accentColor: '#00d4ff' }}
              />
              <span style={{ fontSize: 11, color: '#94a3b8' }}>{label}</span>
            </label>
          ))}
        </div>
      )}

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 9 }}>TARGET FACTION (optional)</div>
        <select
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          disabled={disabled}
          style={{
            width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
            color: '#94a3b8', padding: '6px 8px', fontFamily: 'Courier New',
            fontSize: 11, borderRadius: 2,
          }}
        >
          <option value="">— none —</option>
          {otherFactions.map(([fid, name]) => (
            <option key={fid} value={fid}>{name}</option>
          ))}
        </select>
      </div>

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 9 }}>RATIONALE</div>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Operational rationale..."
          disabled={disabled}
          style={{
            width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
            color: '#94a3b8', padding: '6px 8px', fontFamily: 'system-ui',
            fontSize: 12, resize: 'vertical', minHeight: 60, borderRadius: 2,
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
        [ EXECUTE OPERATION ]
      </button>
    </div>
  )
}
