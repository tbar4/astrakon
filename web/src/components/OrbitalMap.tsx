// web/src/components/OrbitalMap.tsx
import { useMemo } from 'react'
import type { GameState } from '../types'

interface Props {
  gameState: GameState
  coalitionDominance: Record<string, number>
}

const RINGS = [
  { label: 'LEO', r: 52, key: 'leo_nodes' as const },
  { label: 'MEO', r: 74, key: 'meo_nodes' as const },
  { label: 'GEO', r: 94, key: 'geo_nodes' as const },
  { label: 'CIS', r: 112, key: 'cislunar_nodes' as const },
]

const DOT_CAP = 8

function factionColor(factionId: string, gameState: GameState): string {
  if (factionId === gameState.human_faction_id) return '#00ff88'
  const coalition = Object.entries(gameState.coalition_states).find(([, cs]) =>
    cs.member_ids.includes(factionId)
  )
  if (!coalition) return '#00d4ff'
  const cid = coalition[0]
  return gameState.coalition_colors[cid] === 'green' ? '#00ff88' : '#ff4499'
}

function dotsOnRing(count: number, r: number, color: string, factionIdx: number, totalFactions: number) {
  const visible = Math.min(count, DOT_CAP)
  const angleStep = (Math.PI * 2) / Math.max(totalFactions, 1)
  const baseAngle = factionIdx * angleStep
  const spreadAngle = angleStep * 0.6
  const elements: React.ReactElement[] = []

  for (let i = 0; i < visible; i++) {
    const angle = baseAngle + (visible === 1 ? 0 : (i / (visible - 1) - 0.5) * spreadAngle)
    const cx = 130 + r * Math.cos(angle)
    const cy = 130 + r * Math.sin(angle)
    elements.push(
      <circle key={i} cx={cx} cy={cy} r={3} fill={color}
        style={{ filter: `drop-shadow(0 0 3px ${color})` }} />
    )
  }

  if (count > DOT_CAP) {
    const angle = baseAngle + spreadAngle / 2 + 0.15
    const cx = 130 + r * Math.cos(angle)
    const cy = 130 + r * Math.sin(angle)
    elements.push(
      <text key="badge" x={cx} y={cy} fill={color}
        fontSize={8} fontFamily="monospace" textAnchor="middle" dominantBaseline="middle">
        ×{count}
      </text>
    )
  }
  return elements
}

export default function OrbitalMap({ gameState }: Props) {
  const factions = useMemo(() => Object.entries(gameState.faction_states), [gameState])
  const threats = gameState.human_snapshot?.incoming_threats ?? []

  return (
    <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="panel-title">◆ ORBITAL MAP</div>
      <svg viewBox="0 0 260 260" style={{ flex: 1, width: '100%' }}>
        {/* Rings */}
        {RINGS.map(({ r, label }) => (
          <g key={r}>
            <circle cx={130} cy={130} r={r} fill="none"
              stroke="rgba(0,212,255,0.12)" strokeWidth={1} />
            <text x={130 + r + 3} y={132} fill="rgba(0,212,255,0.35)"
              fontSize={7} fontFamily="monospace">{label}</text>
          </g>
        ))}

        {/* Earth */}
        <circle cx={130} cy={130} r={12} fill="#020b18" stroke="rgba(0,212,255,0.5)" strokeWidth={1.5} />
        <text x={130} y={134} fill="rgba(0,212,255,0.6)" fontSize={9}
          fontFamily="monospace" textAnchor="middle">⊕</text>

        {/* Faction nodes */}
        {RINGS.map(({ r, key }) =>
          factions.map(([fid, fs], idx) => {
            const count = fs.assets[key]
            if (count === 0) return null
            const color = factionColor(fid, gameState)
            return (
              <g key={`${r}-${fid}`}>
                {dotsOnRing(count, r, color, idx, factions.length)}
              </g>
            )
          })
        )}

        {/* Kinetic threat indicators */}
        {threats.map((_t, i) => (
          <g key={i}>
            <circle cx={130} cy={130} r={RINGS[0].r}
              fill="none" stroke="rgba(255,68,153,0.6)" strokeWidth={2}
              strokeDasharray="4 4">
              <animateTransform attributeName="transform" type="rotate"
                from="0 130 130" to="360 130 130" dur="4s" repeatCount="indefinite" />
            </circle>
            <text x={130} y={50} fill="#ff4499" fontSize={8}
              fontFamily="monospace" textAnchor="middle">
              ⚠ KINETIC APPROACH
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}
