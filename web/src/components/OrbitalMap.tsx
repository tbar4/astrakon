// web/src/components/OrbitalMap.tsx
import { useMemo } from 'react'
import type { GameState, FactionState } from '../types'

interface Props {
  gameState: GameState
  coalitionDominance: Record<string, number>
  prevFactionStates: Record<string, FactionState> | null
}

const RINGS = [
  { label: 'LEO', r: 52, key: 'leo_nodes' as const },
  { label: 'MEO', r: 74, key: 'meo_nodes' as const },
  { label: 'GEO', r: 94, key: 'geo_nodes' as const },
  { label: 'CIS', r: 112, key: 'cislunar_nodes' as const },
]

const DOT_CAP = 8

interface NodeDelta {
  delta: number   // positive = added, negative = destroyed
  jammed: boolean
}

function factionColor(factionId: string, gameState: GameState): string {
  if (factionId === gameState.human_faction_id) return '#00ff88'
  const coalition = Object.entries(gameState.coalition_states).find(([, cs]) =>
    cs.member_ids.includes(factionId)
  )
  if (!coalition) return '#00d4ff'
  const cid = coalition[0]
  return gameState.coalition_colors[cid] === 'green' ? '#00ff88' : '#ff4499'
}

function computeNodeDelta(
  factionId: string,
  ringKey: 'leo_nodes' | 'meo_nodes' | 'geo_nodes' | 'cislunar_nodes',
  gameState: GameState,
  prevFactionStates: Record<string, FactionState> | null,
): NodeDelta {
  const curr = gameState.faction_states[factionId]
  const factionName = curr?.name.toLowerCase() ?? ''
  const log = gameState.turn_log.join(' ').toLowerCase()
  const jammed = !!(factionName && log.includes(factionName) && (log.includes('jam') || log.includes('[ew]')))

  if (!prevFactionStates || !curr) return { delta: 0, jammed }
  const prev = prevFactionStates[factionId]
  if (!prev) return { delta: 0, jammed }

  return { delta: curr.assets[ringKey] - prev.assets[ringKey], jammed }
}

function dotsOnRing(
  count: number,
  r: number,
  color: string,
  factionIdx: number,
  totalFactions: number,
  { delta, jammed }: NodeDelta,
) {
  const visible = Math.min(count, DOT_CAP)
  const angleStep = (Math.PI * 2) / Math.max(totalFactions, 1)
  const baseAngle = factionIdx * angleStep
  const spreadAngle = angleStep * 0.6
  const elements: React.ReactElement[] = []

  // How many of the visible dots are newly added
  const addedVisible = delta > 0 ? Math.min(delta, visible) : 0

  for (let i = 0; i < visible; i++) {
    const angle = baseAngle + (visible === 1 ? 0 : (i / (visible - 1) - 0.5) * spreadAngle)
    const cx = 130 + r * Math.cos(angle)
    const cy = 130 + r * Math.sin(angle)

    const isNew = i >= visible - addedVisible

    let stroke = 'none'
    let strokeWidth = 0
    let strokeDasharray: string | undefined

    if (jammed) {
      stroke = '#555555'; strokeWidth = 1.5; strokeDasharray = '2 2'
    } else if (isNew) {
      stroke = '#003399'; strokeWidth = 2
    }

    elements.push(
      <circle key={i} cx={cx} cy={cy} r={3} fill={color}
        stroke={stroke} strokeWidth={strokeWidth} strokeDasharray={strokeDasharray}
        style={{ filter: `drop-shadow(0 0 3px ${color})` }} />
    )
  }

  // Overflow badge (count > DOT_CAP)
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

  // Delta annotation (added or destroyed) when count exceeds DOT_CAP or nodes were destroyed
  if (delta !== 0) {
    const annotAngle = baseAngle - spreadAngle / 2 - 0.2
    const ax = 130 + (r + 10) * Math.cos(annotAngle)
    const ay = 130 + (r + 10) * Math.sin(annotAngle)
    const annotColor = delta > 0 ? '#003399' : '#990000'
    elements.push(
      <text key="annot" x={ax} y={ay} fill={annotColor}
        fontSize={7} fontFamily="monospace" textAnchor="middle" dominantBaseline="middle"
        style={{ fontWeight: 'bold' }}>
        {delta > 0 ? `+${delta}` : `${delta}`}
      </text>
    )
  }

  // Destroyed indicator: red ring around cluster position
  if (delta < 0) {
    const cx = 130 + r * Math.cos(baseAngle)
    const cy = 130 + r * Math.sin(baseAngle)
    elements.push(
      <circle key="destroyed-ring" cx={cx} cy={cy} r={6}
        fill="none" stroke="#990000" strokeWidth={1.5} strokeDasharray="2 2" />
    )
  }

  return elements
}

type TextAnchor = 'start' | 'end' | 'middle'
type DominantBaseline = 'hanging' | 'auto' | 'middle'

function factionLabelAnchor(angle: number): { textAnchor: TextAnchor; dominantBaseline: DominantBaseline } {
  const cos = Math.cos(angle)
  const sin = Math.sin(angle)
  const textAnchor: TextAnchor = cos > 0.25 ? 'start' : cos < -0.25 ? 'end' : 'middle'
  const dominantBaseline: DominantBaseline = sin > 0.25 ? 'hanging' : sin < -0.25 ? 'auto' : 'middle'
  return { textAnchor, dominantBaseline }
}

export default function OrbitalMap({ gameState, prevFactionStates }: Props) {
  const factions = useMemo(() => Object.entries(gameState.faction_states), [gameState])
  const threats = gameState.human_snapshot?.incoming_threats ?? []

  const angleStep = (Math.PI * 2) / Math.max(factions.length, 1)

  return (
    <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="panel-title">◆ ORBITAL MAP</div>
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        <svg viewBox="-50 -28 360 316" preserveAspectRatio="xMidYMid meet"
          style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}>
          {/* Rings */}
          {RINGS.map(({ r, label }) => (
            <g key={r}>
              <circle cx={130} cy={130} r={r} fill="none"
                stroke="rgba(0,212,255,0.12)" strokeWidth={1} />
              <text x={130 + r + 3} y={132} fill="rgba(0,212,255,0.2)"
                fontSize={6} fontFamily="monospace">{label}</text>
            </g>
          ))}

          {/* Earth */}
          <circle cx={130} cy={130} r={12} fill="#020b18" stroke="rgba(0,212,255,0.5)" strokeWidth={1.5} />
          <text x={130} y={134} fill="rgba(0,212,255,0.6)" fontSize={9}
            fontFamily="monospace" textAnchor="middle">⊕</text>

          {/* Faction name labels — outside CIS ring */}
          {factions.map(([fid, fs], idx) => {
            const angle = idx * angleStep
            const labelR = 122
            const lx = 130 + labelR * Math.cos(angle)
            const ly = 130 + labelR * Math.sin(angle)
            const { textAnchor, dominantBaseline } = factionLabelAnchor(angle)
            const color = factionColor(fid, gameState)
            const label = fs.name.length > 12 ? fs.name.slice(0, 11) + '…' : fs.name
            return (
              <text key={`label-${fid}`} x={lx} y={ly} fill={color}
                fontSize={7} fontFamily="monospace"
                textAnchor={textAnchor} dominantBaseline={dominantBaseline}
                style={{ opacity: 0.85 }}>
                {label}
              </text>
            )
          })}

          {/* Faction nodes */}
          {RINGS.map(({ r, key }) =>
            factions.map(([fid, fs], idx) => {
              const count = fs.assets[key]
              if (count === 0) return null
              const color = factionColor(fid, gameState)
              const nodeDelta = computeNodeDelta(fid, key, gameState, prevFactionStates)
              return (
                <g key={`${r}-${fid}`}>
                  {dotsOnRing(count, r, color, idx, factions.length, nodeDelta)}
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
    </div>
  )
}
