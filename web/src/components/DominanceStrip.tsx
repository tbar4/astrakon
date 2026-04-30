// web/src/components/DominanceStrip.tsx
import type { TurnSnapshot } from '../store/gameStore'

interface Props {
  coalitionDominance: Record<string, number>
  turnHistory: TurnSnapshot[]
  coalitionColors: Record<string, string>
  victoryThreshold: number
}

export default function DominanceStrip({ coalitionDominance, turnHistory, coalitionColors, victoryThreshold }: Props) {
  const entries = Object.entries(coalitionDominance)
  const prevDominance = turnHistory.length >= 2
    ? turnHistory[turnHistory.length - 2].dominance
    : null

  return (
    <div style={{
      height: 28, display: 'flex', alignItems: 'center', gap: 16,
      padding: '0 12px', borderTop: '1px solid #00d4ff11',
      background: '#020b18', flexShrink: 0,
    }}>
      {entries.map(([cid, dom]) => {
        const color = coalitionColors[cid] === 'green' ? '#00ff88' : '#ff4499'
        const barWidth = Math.min(100, dom * 100)
        const prevDom = prevDominance?.[cid] ?? null
        const delta = prevDom !== null ? dom - prevDom : null
        const atThreshold = dom >= victoryThreshold

        return (
          <div key={cid} style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}>
            <div style={{ width: 60, height: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{
                height: '100%', width: `${barWidth}%`,
                background: color, transition: 'width 0.5s',
                boxShadow: atThreshold ? `0 0 6px ${color}` : 'none',
              }} />
            </div>
            <span style={{ fontFamily: 'Courier New', fontSize: 9, color, letterSpacing: 1 }}>
              {cid}
            </span>
            <span style={{ fontFamily: 'Courier New', fontSize: 9, color }}>
              {(dom * 100).toFixed(1)}%
            </span>
            {delta !== null && Math.abs(delta) > 0.0001 && (
              <span style={{ fontFamily: 'Courier New', fontSize: 8, color: delta > 0 ? '#00ff88' : '#ff4499' }}>
                {delta > 0 ? '+' : ''}{(delta * 100).toFixed(1)}%
              </span>
            )}
          </div>
        )
      })}
      <span style={{ fontFamily: 'Courier New', fontSize: 8, color: '#334155', letterSpacing: 1, whiteSpace: 'nowrap' }}>
        WIN: {(victoryThreshold * 100).toFixed(0)}%
      </span>
    </div>
  )
}
