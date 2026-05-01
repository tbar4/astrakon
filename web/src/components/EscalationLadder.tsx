const RUNGS = [
  { label: 'PEACETIME', color: '#00ff88' },
  { label: 'CONTESTED', color: '#64748b' },
  { label: 'DEGRADED',  color: '#f59e0b' },
  { label: 'THRESHOLD', color: '#f97316' },
  { label: 'KINETIC',   color: '#ef4444' },
  { label: 'ESCALATORY',color: '#ff4499' },
]

interface Props {
  rung: number
}

export default function EscalationLadder({ rung }: Props) {
  return (
    <div style={{ padding: '8px 0' }}>
      <div style={{ fontFamily: 'Courier New', fontSize: 11, color: '#475569', letterSpacing: 2, marginBottom: 6 }}>
        ESCALATION
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {RUNGS.slice().reverse().map((r, i) => {
          const rungIdx = RUNGS.length - 1 - i
          const active = rungIdx === rung
          const past = rungIdx < rung
          return (
            <div key={rungIdx} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              opacity: past ? 0.4 : 1,
            }}>
              <div style={{
                width: 8, height: 8, borderRadius: 1, flexShrink: 0,
                background: active ? r.color : past ? r.color : 'transparent',
                border: `1px solid ${active || past ? r.color : '#334155'}`,
                boxShadow: active ? `0 0 6px ${r.color}` : 'none',
              }} />
              <span style={{
                fontFamily: 'Courier New', fontSize: 11,
                color: active ? r.color : past ? r.color : '#475569',
                letterSpacing: 1,
                fontWeight: active ? 700 : 400,
              }}>
                {rungIdx} — {r.label}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
