// web/src/components/ForecastTab.tsx
import type { OperationForecast } from '../types'

interface Props {
  forecasts: OperationForecast[]
  factionNames: Record<string, string>
}

function accuracyGrade(forecast: OperationForecast): { grade: string; color: string } | null {
  if (!forecast.actual) return null
  const isCombat = forecast.action_type === 'task_assets'
    ? forecast.mission === 'intercept'
    : forecast.action_type === 'gray_zone'
  if (!isCombat) return null

  const delta = Math.abs(
    forecast.forecast.nodes_destroyed_estimate - forecast.actual.nodes_destroyed
  )
  const detectionPredicted = forecast.forecast.detection_prob >= 0.5
  const detectionMatched = detectionPredicted === forecast.actual.detected

  if (delta <= 1 && detectionMatched) return { grade: 'A', color: '#00ff88' }
  if (delta <= 2) return { grade: 'B', color: '#f59e0b' }
  return { grade: 'C', color: '#ff4499' }
}

const COL = {
  header: {
    fontFamily: 'Courier New', fontSize: 10, color: '#475569',
    letterSpacing: 1, padding: '4px 8px', borderBottom: '1px solid #00d4ff22',
    whiteSpace: 'nowrap' as const,
  },
  cell: {
    fontFamily: 'Courier New', fontSize: 11, color: '#94a3b8',
    padding: '4px 8px', borderBottom: '1px solid #00d4ff0a',
    whiteSpace: 'nowrap' as const,
  },
}

export default function ForecastTab({ forecasts, factionNames }: Props) {
  if (forecasts.length === 0) {
    return (
      <div style={{
        height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{ fontFamily: 'Courier New', fontSize: 11, color: '#334155', letterSpacing: 2, textAlign: 'center' }}>
          NO FORECAST DATA<br />
          <span style={{ fontSize: 10 }}>Execute an operation to begin tracking</span>
        </div>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '10px 14px' }}>
      <div className="panel-title" style={{ marginBottom: 8 }}>◆ FORECAST ACCURACY LEDGER</div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {['TURN', 'ACTION', 'TARGET', 'EST.NODES', 'ACTUAL', 'DETECTED', 'ATTRIBUTED', 'ACCURACY'].map(h => (
              <th key={h} style={COL.header}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {forecasts.map((fc, i) => {
            const targetName = factionNames[fc.target_faction_id] ?? fc.target_faction_id ?? '—'
            const action = fc.action_type === 'task_assets' ? (fc.mission || 'patrol') : fc.action_type
            const isCombatAction = fc.action_type === 'task_assets'
              ? fc.mission === 'intercept'
              : fc.action_type === 'gray_zone'
            const grade = accuracyGrade(fc)

            let estNodes: string
            if (!isCombatAction) estNodes = '—'
            else if (fc.forecast.nodes_destroyed_min !== fc.forecast.nodes_destroyed_max)
              estNodes = `${fc.forecast.nodes_destroyed_min}–${fc.forecast.nodes_destroyed_max}`
            else estNodes = String(fc.forecast.nodes_destroyed_estimate)

            const pendingCell = <span style={{ color: '#00d4ff44' }}>PENDING</span>
            const naCell = <span style={{ color: '#334155' }}>N/A</span>

            return (
              <tr key={i}>
                <td style={COL.cell}>{fc.turn}</td>
                <td style={{ ...COL.cell, color: '#00d4ff', textTransform: 'uppercase' as const }}>{action.replace('_', ' ')}</td>
                <td style={COL.cell}>{targetName}</td>
                <td style={COL.cell}>{estNodes}</td>
                <td style={COL.cell}>
                  {!isCombatAction ? naCell
                    : fc.pending ? pendingCell
                    : fc.actual ? String(fc.actual.nodes_destroyed)
                    : naCell}
                </td>
                <td style={COL.cell}>
                  {!isCombatAction ? naCell
                    : fc.pending ? pendingCell
                    : fc.actual
                      ? <span>
                          <span style={{ color: '#64748b' }}>{Math.round(fc.forecast.detection_prob * 100)}% → </span>
                          <span style={{ color: fc.actual.detected ? '#00ff88' : '#ff4499' }}>
                            {fc.actual.detected ? '✓' : '✗'}
                          </span>
                        </span>
                      : naCell}
                </td>
                <td style={COL.cell}>
                  {!isCombatAction ? naCell
                    : fc.pending ? pendingCell
                    : fc.actual
                      ? <span>
                          <span style={{ color: '#64748b' }}>{Math.round(fc.forecast.attribution_prob * 100)}% → </span>
                          <span style={{ color: fc.actual.attributed ? '#00ff88' : '#ff4499' }}>
                            {fc.actual.attributed ? '✓' : '✗'}
                          </span>
                        </span>
                      : naCell}
                </td>
                <td style={{ ...COL.cell, fontWeight: 700 }}>
                  {grade
                    ? <span style={{ color: grade.color }}>{grade.grade}</span>
                    : naCell}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
