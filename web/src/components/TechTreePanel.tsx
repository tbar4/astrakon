// web/src/components/TechTreePanel.tsx
import type { GameState, FactionState } from '../types'

interface Props {
  gameState: GameState
  factionState: FactionState
  currentPhase: string
  rdPoints: number
  pendingUnlocks: string[]
  onQueueToggle: (nodeId: string) => void
}

const TRUNK_IDS = ['trunk_launch', 'trunk_capacity', 'trunk_budget']

export interface NodeMeta {
  id: string
  name: string
  cost: number
  tier: 1 | 2 | 3
  prereqs: string[]
  archetype: string | null
}

export const NODE_META: NodeMeta[] = [
  { id: 'trunk_launch',   name: 'EFFICIENT LAUNCH',      cost: 2, tier: 1, prereqs: [], archetype: null },
  { id: 'trunk_capacity', name: 'INTEGRATED SYSTEMS',    cost: 2, tier: 1, prereqs: [], archetype: null },
  { id: 'trunk_budget',   name: 'RESOURCE OPTIMIZATION', cost: 2, tier: 1, prereqs: [], archetype: null },
  { id: 'mah_strike',     name: 'KINETIC DOCTRINE',      cost: 3, tier: 2, prereqs: ['_any_trunk'], archetype: 'mahanian' },
  { id: 'mah_deterrence', name: 'DETERRENCE OPS',        cost: 3, tier: 2, prereqs: ['_any_trunk'], archetype: 'mahanian' },
  { id: 'mah_escalation', name: 'ESCALATION RESPONSE',   cost: 5, tier: 3, prereqs: ['mah_strike'], archetype: 'mahanian' },
  { id: 'mah_projection', name: 'POWER PROJECTION',      cost: 5, tier: 3, prereqs: ['mah_deterrence'], archetype: 'mahanian' },
  { id: 'com_market',     name: 'MARKET DOMINANCE',      cost: 3, tier: 2, prereqs: ['_any_trunk'], archetype: 'commercial_broker' },
  { id: 'com_revenue',    name: 'CAPACITY REVENUE',      cost: 3, tier: 2, prereqs: ['_any_trunk'], archetype: 'commercial_broker' },
  { id: 'com_network',    name: 'ORBITAL NETWORK',       cost: 5, tier: 3, prereqs: ['com_market'], archetype: 'commercial_broker' },
  { id: 'com_economics',  name: 'SCALE ECONOMICS',       cost: 5, tier: 3, prereqs: ['com_revenue'], archetype: 'commercial_broker' },
  { id: 'gz_masking',     name: 'SIGNATURE MASKING',     cost: 3, tier: 2, prereqs: ['_any_trunk'], archetype: 'gray_zone' },
  { id: 'gz_jamming',     name: 'WIDE-BAND JAMMING',     cost: 3, tier: 2, prereqs: ['_any_trunk'], archetype: 'gray_zone' },
  { id: 'gz_ghost',       name: 'GHOST PRESENCE',        cost: 5, tier: 3, prereqs: ['gz_masking'], archetype: 'gray_zone' },
  { id: 'gz_influence',   name: 'DEEP INFLUENCE',        cost: 5, tier: 3, prereqs: ['gz_jamming'], archetype: 'gray_zone' },
  { id: 'rog_debris',     name: 'DEBRIS DOCTRINE',       cost: 3, tier: 2, prereqs: ['_any_trunk'], archetype: 'rogue_accelerationist' },
  { id: 'rog_ascent',     name: 'RAPID ASCENT',          cost: 3, tier: 2, prereqs: ['_any_trunk'], archetype: 'rogue_accelerationist' },
  { id: 'rog_cascade',    name: 'KESSLER CASCADE',       cost: 5, tier: 3, prereqs: ['rog_debris'], archetype: 'rogue_accelerationist' },
  { id: 'rog_shock',      name: 'SHOCK STRIKE',          cost: 5, tier: 3, prereqs: ['rog_ascent'], archetype: 'rogue_accelerationist' },
]

const NODE_BY_ID = Object.fromEntries(NODE_META.map(n => [n.id, n]))

const ARCHETYPE_ORDER = ['mahanian', 'commercial_broker', 'gray_zone', 'rogue_accelerationist']
const ARCHETYPE_LABELS: Record<string, string> = {
  mahanian: 'MAHANIAN',
  commercial_broker: 'COMMERCIAL',
  gray_zone: 'GRAY ZONE',
  rogue_accelerationist: 'ROGUE',
}

const BRANCH_NODES: Record<string, [[string, string], [string, string]]> = {
  mahanian: [['mah_strike', 'mah_deterrence'], ['mah_escalation', 'mah_projection']],
  commercial_broker: [['com_market', 'com_revenue'], ['com_network', 'com_economics']],
  gray_zone: [['gz_masking', 'gz_jamming'], ['gz_ghost', 'gz_influence']],
  rogue_accelerationist: [['rog_debris', 'rog_ascent'], ['rog_cascade', 'rog_shock']],
}

const NW = 136, NH = 40
const TRUNK_Y = 75
const T2_Y = 220
const T3_Y = 360
const HALF_GAP = 76          // must be > NW/2 (68) to avoid box overlap
const COL_X = [150, 450, 750, 1050]
const TRUNK_CX = [300, 600, 900]
const SVG_W = 1200
const SVG_H = 450

function prereqsMet(node: NodeMeta, unlocked: string[]): boolean {
  const hasAnyTrunk = TRUNK_IDS.some(id => unlocked.includes(id))
  return node.prereqs.every(p => p === '_any_trunk' ? hasAnyTrunk : unlocked.includes(p))
}

function nodeColor(
  id: string, phase: string, unlocked: string[], pending: string[],
  rdPoints: number, humanArchetype: string
): string {
  if (pending.includes(id)) return '#00d4ff'
  if (unlocked.includes(id)) return '#00ff88'
  const meta = NODE_BY_ID[id]
  if (!meta) return '#7f8ea0'
  if (phase !== 'invest') return '#7f8ea0'
  if (meta.archetype && meta.archetype !== humanArchetype) return '#7f8ea0'
  if (!prereqsMet(meta, unlocked)) return '#94a3b8'
  if (rdPoints < meta.cost) return '#94a3b8'
  return '#f59e0b'
}

interface NodeBoxProps {
  id: string; cx: number; cy: number
  phase: string; unlocked: string[]; pending: string[]
  rdPoints: number; humanArchetype: string
  onQueueToggle: (id: string) => void
}

function NodeBox({ id, cx, cy, phase, unlocked, pending, rdPoints, humanArchetype, onQueueToggle }: NodeBoxProps) {
  const color = nodeColor(id, phase, unlocked, pending, rdPoints, humanArchetype)
  const meta = NODE_BY_ID[id]
  if (!meta) return null
  const clickable = color === '#f59e0b' || color === '#00d4ff'
  const label = pending.includes(id)
    ? 'QUEUED' : unlocked.includes(id)
    ? '✓ UNLOCKED' : `${meta.cost} pts`
  return (
    <g
      onClick={clickable ? () => onQueueToggle(id) : undefined}
      style={{ cursor: clickable ? 'pointer' : 'default' }}
    >
      <rect
        x={cx - NW / 2} y={cy - NH / 2} width={NW} height={NH}
        fill="rgba(2,11,24,0.92)" stroke={color} strokeWidth={clickable ? 2 : 1.5} rx={2}
      />
      {clickable && (
        <rect
          x={cx - NW / 2} y={cy - NH / 2} width={NW} height={NH}
          fill={color} fillOpacity={0.06} rx={2}
        />
      )}
      <text x={cx} y={cy - 5} textAnchor="middle" fill={color}
        fontSize={10} fontFamily="Courier New">
        {meta.name}
      </text>
      <text x={cx} y={cy + 10} textAnchor="middle"
        fill={color} fillOpacity={0.9} fontSize={10} fontFamily="Courier New">
        {label}
      </text>
    </g>
  )
}

export default function TechTreePanel({
  gameState: _gameState, factionState, currentPhase, rdPoints, pendingUnlocks, onQueueToggle
}: Props) {
  const unlocked = factionState.unlocked_techs ?? []
  const humanArchetype = factionState.archetype ?? ''

  const rdColor = rdPoints < 0 ? '#ff4499' : rdPoints === 0 ? '#f59e0b' : '#00d4ff'

  function lineColor(fromId: string): string {
    if (unlocked.includes(fromId)) return '#00ff8899'
    return '#64748b99'
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
      <div style={{
        padding: '6px 16px', display: 'flex', alignItems: 'center', gap: 12,
        borderBottom: '1px solid #00d4ff11', flexShrink: 0,
      }}>
        <span className="mono" style={{ fontSize: 11, color: '#64748b', letterSpacing: 2 }}>R&D:</span>
        <span className="mono" style={{ fontSize: 14, color: rdColor, letterSpacing: 2, fontWeight: 'bold' }}>
          {rdPoints} pts
        </span>
        {rdPoints < 0 && (
          <span className="mono" style={{ fontSize: 9, color: '#ff4499' }}>OVERDRAWN</span>
        )}
        {currentPhase === 'invest' && (
          <span className="mono" style={{ fontSize: 9, color: '#475569', marginLeft: 'auto' }}>
            CLICK AMBER NODES TO QUEUE
          </span>
        )}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        <svg
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          style={{ width: '100%', maxWidth: SVG_W, display: 'block', margin: '0 auto' }}
        >
          <line
            x1={COL_X[0]} y1={TRUNK_Y + NH / 2 + 8}
            x2={COL_X[3]} y2={TRUNK_Y + NH / 2 + 8}
            stroke="#64748b66" strokeWidth={1}
          />

          {COL_X.map(cx => (
            <line key={cx}
              x1={cx} y1={TRUNK_Y + NH / 2 + 8}
              x2={cx} y2={T2_Y - NH / 2 - 6}
              stroke="#64748b66" strokeWidth={1}
            />
          ))}

          {['trunk_launch', 'trunk_capacity', 'trunk_budget'].map((id, i) => (
            <NodeBox key={id} id={id} cx={TRUNK_CX[i]} cy={TRUNK_Y}
              phase={currentPhase} unlocked={unlocked} pending={pendingUnlocks}
              rdPoints={rdPoints} humanArchetype={humanArchetype}
              onQueueToggle={onQueueToggle}
            />
          ))}

          {ARCHETYPE_ORDER.map((arch, colIdx) => {
            const cx = COL_X[colIdx]
            const isOwn = arch === humanArchetype
            const [[leftT2, rightT2], [leftT3, rightT3]] = BRANCH_NODES[arch]

            return (
              <g key={arch}>
                <text x={cx} y={T2_Y - NH / 2 - 14}
                  textAnchor="middle" fill={isOwn ? '#cbd5e1' : '#7f8ea0'}
                  fontSize={10} fontFamily="Courier New" letterSpacing={2}>
                  {ARCHETYPE_LABELS[arch]}
                </text>

                {isOwn ? (
                  <>
                    <line
                      x1={cx - HALF_GAP} y1={T2_Y + NH / 2}
                      x2={cx - HALF_GAP} y2={T3_Y - NH / 2 - 4}
                      stroke={lineColor(leftT2)} strokeWidth={1.5}
                    />
                    <line
                      x1={cx + HALF_GAP} y1={T2_Y + NH / 2}
                      x2={cx + HALF_GAP} y2={T3_Y - NH / 2 - 4}
                      stroke={lineColor(rightT2)} strokeWidth={1.5}
                    />

                    <NodeBox id={leftT2}  cx={cx - HALF_GAP} cy={T2_Y}
                      phase={currentPhase} unlocked={unlocked} pending={pendingUnlocks}
                      rdPoints={rdPoints} humanArchetype={humanArchetype}
                      onQueueToggle={onQueueToggle}
                    />
                    <NodeBox id={rightT2} cx={cx + HALF_GAP} cy={T2_Y}
                      phase={currentPhase} unlocked={unlocked} pending={pendingUnlocks}
                      rdPoints={rdPoints} humanArchetype={humanArchetype}
                      onQueueToggle={onQueueToggle}
                    />
                    <NodeBox id={leftT3}  cx={cx - HALF_GAP} cy={T3_Y}
                      phase={currentPhase} unlocked={unlocked} pending={pendingUnlocks}
                      rdPoints={rdPoints} humanArchetype={humanArchetype}
                      onQueueToggle={onQueueToggle}
                    />
                    <NodeBox id={rightT3} cx={cx + HALF_GAP} cy={T3_Y}
                      phase={currentPhase} unlocked={unlocked} pending={pendingUnlocks}
                      rdPoints={rdPoints} humanArchetype={humanArchetype}
                      onQueueToggle={onQueueToggle}
                    />
                  </>
                ) : (
                  <g>
                    <rect
                      x={cx - HALF_GAP - NW / 2 - 8} y={T2_Y - NH / 2}
                      width={2 * (HALF_GAP + NW / 2) + 16} height={T3_Y - T2_Y + NH}
                      fill="rgba(2,11,24,0.6)" stroke="#64748baa" strokeWidth={1}
                      strokeDasharray="4 3" rx={3}
                    />
                    <text x={cx} y={(T2_Y + T3_Y) / 2 - 8}
                      textAnchor="middle" fill="#94a3b8" fontSize={11}
                      fontFamily="Courier New" letterSpacing={3}>
                      ◆ CLASSIFIED
                    </text>
                    <text x={cx} y={(T2_Y + T3_Y) / 2 + 8}
                      textAnchor="middle" fill="#64748b" fontSize={9}
                      fontFamily="Courier New" letterSpacing={1}>
                      INTEL DENIED
                    </text>
                  </g>
                )}
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}
