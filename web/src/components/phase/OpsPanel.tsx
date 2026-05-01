// web/src/components/phase/OpsPanel.tsx
import { useState, useEffect, useRef } from 'react'
import type { OperationPreview } from '../../types'

interface Props {
  factionNames: Record<string, string>
  humanFactionId: string
  asatKinetic: number
  sessionId: string
  onSubmit: (decision: Record<string, unknown>, forecast?: Record<string, unknown>) => void
  disabled: boolean
  mapTarget?: string | null
  onClearMapTarget?: () => void
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

function PreviewRows({ preview }: { preview: OperationPreview }) {
  const rows: [string, string][] = []
  if (preview.dv_cost > 0) {
    rows.push(['DV COST', `-${preview.dv_cost.toFixed(1)}`])
    rows.push(['DV REMAINING', preview.dv_remaining.toFixed(1)])
  }
  if (preview.target_shell) rows.push(['TARGET SHELL', preview.target_shell.toUpperCase()])
  if (preview.nodes_destroyed_min === preview.nodes_destroyed_max) {
    rows.push(['EST. NODES', `${preview.nodes_destroyed_estimate}`])
  } else {
    rows.push(['EST. NODES', `${preview.nodes_destroyed_min}–${preview.nodes_destroyed_max}`])
  }
  if (preview.detection_prob > 0) rows.push(['DETECTED', `${Math.round(preview.detection_prob * 100)}%`])
  if (preview.attribution_prob > 0) rows.push(['ATTRIBUTED', `${Math.round(preview.attribution_prob * 100)}%`])
  if (preview.escalation_delta > 0)
    rows.push(['ESCALATION', `→ RNG ${preview.escalation_rung_new}`])
  if (preview.debris_estimate > 0)
    rows.push(['DEBRIS', `+${(preview.debris_estimate * 100).toFixed(0)}%`])
  if (preview.transit_turns > 0)
    rows.push(['TRANSIT', preview.transit_turns === 1 ? '1 TURN' : '2 TURNS'])
  else if (preview.dv_cost === 0 && rows.length > 0)
    rows.push(['TIMING', 'IMMEDIATE'])

  if (rows.length === 0) return null

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '2px 12px' }}>
      {rows.map(([label, value]) => (
        <span key={label + '-row'} style={{ display: 'contents' }}>
          <span style={{ fontSize: 11, color: '#475569', fontFamily: 'Courier New' }}>{label}</span>
          <span style={{ fontSize: 11, color: '#e2e8f0', fontFamily: 'Courier New' }}>{value}</span>
        </span>
      ))}
    </div>
  )
}

export default function OpsPanel({
  factionNames, humanFactionId, asatKinetic, sessionId,
  onSubmit, disabled, mapTarget, onClearMapTarget,
}: Props) {
  const [actionType, setActionType] = useState<ActionKey>('task_assets')
  const [target, setTarget] = useState('')
  const [mission, setMission] = useState('sda_sweep')
  const [rationale, setRationale] = useState('')
  const [preview, setPreview] = useState<OperationPreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (mapTarget != null) setTarget(mapTarget)
  }, [mapTarget])

  const otherFactions = Object.entries(factionNames).filter(([fid]) => fid !== humanFactionId)
  const effectiveTarget = mapTarget ?? target

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      setPreviewLoading(true)
      try {
        const res = await fetch(`/api/game/${sessionId}/preview`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action_type: actionType,
            mission: actionType === 'task_assets' ? mission : '',
            target_faction_id: effectiveTarget || '',
          }),
        })
        if (res.ok) setPreview(await res.json())
      } finally {
        setPreviewLoading(false)
      }
    }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [actionType, effectiveTarget, mission, sessionId])

  function handleSubmit() {
    const params: Record<string, string> = {}
    if (actionType === 'task_assets') params.mission = mission
    const forecastPayload = preview ? {
      action_type: actionType,
      mission: actionType === 'task_assets' ? mission : '',
      target_faction_id: effectiveTarget || '',
      forecast: preview,
    } : undefined
    onSubmit(
      {
        operations: [{
          action_type: actionType,
          target_faction: effectiveTarget || undefined,
          parameters: params,
          rationale,
        }],
      },
      forecastPayload,
    )
  }

  return (
    <div>
      <div className="panel-title">◆ OPERATIONS PHASE</div>

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 11 }}>ACTION TYPE</div>
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
              style={{ marginTop: 3, accentColor: '#00d4ff' }}
            />
            <div>
              <div style={{ fontSize: 13, color: '#e2e8f0' }}>{label}</div>
              <div style={{ fontSize: 12, color: '#475569' }}>{desc}</div>
            </div>
          </label>
        ))}
      </div>

      {actionType === 'task_assets' && (
        <div style={{ marginBottom: 12 }}>
          <div className="panel-title" style={{ fontSize: 11 }}>MISSION</div>
          {MISSIONS.map(({ key, label }) => {
            const noAsats = key === 'intercept' && asatKinetic === 0
            return (
              <label key={key} style={{ display: 'flex', gap: 8, padding: '4px 0', cursor: noAsats ? 'not-allowed' : 'pointer', opacity: noAsats ? 0.4 : 1 }}>
                <input
                  type="radio" name="mission" value={key}
                  checked={mission === key}
                  onChange={() => setMission(key)}
                  disabled={disabled || noAsats}
                  style={{ accentColor: '#00d4ff' }}
                />
                <span style={{ fontSize: 13, color: '#94a3b8' }}>
                  {label}{noAsats ? ' — no kinetic ASATs' : ''}
                </span>
              </label>
            )
          })}
        </div>
      )}

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 11 }}>
          TARGET FACTION {!mapTarget && <span style={{ color: '#334155' }}>(optional — or click map)</span>}
        </div>
        {mapTarget ? (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '6px 8px', border: '1px solid #f59e0b66', borderRadius: 2,
            background: 'rgba(245,158,11,0.06)',
          }}>
            <span style={{ fontFamily: 'Courier New', fontSize: 13, color: '#f59e0b', letterSpacing: 1 }}>
              ◎ {factionNames[mapTarget] ?? mapTarget}
            </span>
            <button
              onClick={() => { onClearMapTarget?.(); setTarget('') }}
              disabled={disabled}
              style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 14, padding: '0 4px', lineHeight: 1 }}
            >
              ×
            </button>
          </div>
        ) : (
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            disabled={disabled}
            style={{
              width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
              color: '#94a3b8', padding: '6px 8px', fontFamily: 'Courier New',
              fontSize: 13, borderRadius: 2,
            }}
          >
            <option value="">— none —</option>
            {otherFactions.map(([fid, name]) => (
              <option key={fid} value={fid}>{name}</option>
            ))}
          </select>
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 11 }}>RATIONALE</div>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Operational rationale..."
          disabled={disabled}
          style={{
            width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
            color: '#94a3b8', padding: '6px 8px', fontFamily: 'system-ui',
            fontSize: 13, resize: 'vertical', minHeight: 60, borderRadius: 2,
            boxSizing: 'border-box',
          }}
        />
      </div>

      {preview && (
        <div style={{
          marginBottom: 12, border: '1px solid rgba(0,212,255,0.2)',
          borderRadius: 2, padding: '8px 10px', background: 'rgba(0,212,255,0.04)',
        }}>
          <div className="panel-title" style={{ fontSize: 11, marginBottom: 6, color: '#00d4ff' }}>
            ◆ ESTIMATED OUTCOME {previewLoading && <span style={{ color: '#334155' }}>…</span>}
          </div>
          {!preview.available ? (
            <div style={{ color: '#f59e0b', fontSize: 12, fontFamily: 'Courier New' }}>
              [BLOCKED] {preview.unavailable_reason}
            </div>
          ) : preview.effect_summary ? (
            <div style={{ color: '#94a3b8', fontSize: 12, fontFamily: 'Courier New' }}>
              {preview.effect_summary}
            </div>
          ) : (
            <PreviewRows preview={preview} />
          )}
        </div>
      )}

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
