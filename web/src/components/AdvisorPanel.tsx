// web/src/components/AdvisorPanel.tsx
import type { Recommendation, Phase } from '../types'

interface Props {
  recommendation: Recommendation | null
  phase: Phase
  warnings?: string[]
  onAccept: () => void
  onDismiss: () => void
}

interface Section {
  header: string | null
  body: string
}

function parseRationale(text: string): Section[] {
  // Match ALL-CAPS headers followed by colon (section titles the AI uses)
  const re = /\b([A-Z][A-Z0-9\s\-—\/]{2,}):/g
  const matches: Array<{ header: string; index: number; end: number }> = []
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    matches.push({ header: m[1].trim(), index: m.index, end: m.index + m[0].length })
  }

  if (matches.length === 0) return [{ header: null, body: text }]

  const sections: Section[] = []
  if (matches[0].index > 0) {
    const pre = text.slice(0, matches[0].index).trim()
    if (pre) sections.push({ header: null, body: pre })
  }
  for (let i = 0; i < matches.length; i++) {
    const bodyStart = matches[i].end
    const bodyEnd = i + 1 < matches.length ? matches[i + 1].index : text.length
    const body = text.slice(bodyStart, bodyEnd).trim()
    sections.push({ header: matches[i].header, body })
  }
  return sections.filter((s) => s.body.length > 0)
}

function formatActionSummary(phase: Phase, rec: Recommendation['top_recommendation']): string {
  if (phase === 'invest' && rec.investment) {
    const top = Object.entries(rec.investment)
      .filter(([k, v]) => k !== 'rationale' && typeof v === 'number' && (v as number) > 0)
      .sort(([, a], [, b]) => (b as number) - (a as number))
      .slice(0, 3)
      .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${((v as number) * 100).toFixed(0)}%`)
    return top.join('  ·  ')
  }
  if (phase === 'operations' && rec.operations?.[0]) {
    const op = rec.operations[0]
    return `${op.action_type.replace(/_/g, ' ')}${op.target_faction ? ` → ${op.target_faction}` : ''}`
  }
  if (phase === 'response' && rec.response) {
    return rec.response.escalate
      ? `ESCALATE${rec.response.retaliate ? ` + RETALIATE → ${rec.response.target_faction ?? '?'}` : ''}`
      : 'STAND DOWN'
  }
  return ''
}

export default function AdvisorPanel({ recommendation: rec, phase, warnings = [], onAccept, onDismiss }: Props) {
  if (!rec) return null

  const summary = formatActionSummary(phase, rec.top_recommendation)
  const sections = parseRationale(rec.strategic_rationale)
  const hasCorrected = warnings.length > 0

  return (
    <div style={{
      border: `1px solid ${hasCorrected ? 'rgba(251,146,60,0.5)' : 'rgba(245,158,11,0.35)'}`,
      borderRadius: 4,
      marginBottom: 12,
      background: 'rgba(245,158,11,0.04)',
      overflow: 'hidden',
    }}>
      {/* Header bar */}
      <div style={{
        padding: '8px 12px',
        borderBottom: '1px solid rgba(245,158,11,0.2)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'rgba(245,158,11,0.08)',
      }}>
        <span className="mono" style={{ fontSize: 10, letterSpacing: 3, color: '#f59e0b' }}>◆ AI ADVISOR</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-primary" onClick={onAccept}
            style={{ fontSize: 10, padding: '3px 14px', borderColor: '#f59e0b', color: '#f59e0b' }}>
            ACCEPT
          </button>
          <button className="btn-primary" onClick={onDismiss}
            style={{ fontSize: 10, padding: '3px 14px', borderColor: '#334155', color: '#64748b' }}>
            DISMISS
          </button>
        </div>
      </div>

      {/* Sanitization warnings */}
      {hasCorrected && (
        <div style={{
          padding: '6px 12px',
          borderBottom: '1px solid rgba(251,146,60,0.25)',
          background: 'rgba(251,146,60,0.06)',
        }}>
          <div className="mono" style={{ fontSize: 9, letterSpacing: 2, color: '#fb923c', marginBottom: 4 }}>
            ⚠ ADVISOR CORRECTION
          </div>
          {warnings.map((w, i) => (
            <div key={i} style={{ fontSize: 11, color: '#fb923c99', fontFamily: 'Courier New', lineHeight: 1.5 }}>
              · {w}
            </div>
          ))}
        </div>
      )}

      {/* Recommended action summary */}
      {summary && (
        <div style={{
          padding: '8px 12px',
          borderBottom: '1px solid rgba(245,158,11,0.15)',
          background: 'rgba(245,158,11,0.06)',
        }}>
          <span style={{ fontSize: 9, color: '#f59e0b66', letterSpacing: 2, fontFamily: 'Courier New' }}>RECOMMENDED ACTION  </span>
          <span className="mono" style={{ fontSize: 12, color: '#fbbf24' }}>{summary.toUpperCase()}</span>
        </div>
      )}

      {/* Structured rationale sections */}
      <div style={{ padding: '8px 12px', maxHeight: 280, overflowY: 'auto' }}>
        {sections.map((section, i) => (
          <div key={i} style={{ marginBottom: section.header ? 10 : 6 }}>
            {section.header && (
              <div className="mono" style={{
                fontSize: 9,
                letterSpacing: 2,
                color: '#f59e0b',
                marginBottom: 3,
                paddingBottom: 2,
                borderBottom: '1px solid rgba(245,158,11,0.2)',
              }}>
                {section.header}
              </div>
            )}
            <div style={{
              fontSize: 11,
              color: '#94a3b8',
              lineHeight: 1.55,
              whiteSpace: 'pre-wrap',
            }}>
              {section.body}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
