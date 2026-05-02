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

export interface NodeMeta {
  id: string
  name: string
  cost: number
  tier: number   // 1=trunk, 2=T1, 3=T2, 4=T3, 5=T4
  prereqs: string[]
  archetype_discount: string | null
}

const TRUNK_IDS = ['trunk_launch', 'trunk_capacity', 'trunk_budget', 'trunk_sda', 'trunk_resilience']

export const NODE_META: NodeMeta[] = [
  // Trunk
  { id: 'trunk_launch',     name: 'EFFICIENT LAUNCH',      cost: 2, tier: 1, prereqs: [],                      archetype_discount: null },
  { id: 'trunk_capacity',   name: 'INTEGRATED SYSTEMS',    cost: 2, tier: 1, prereqs: [],                      archetype_discount: null },
  { id: 'trunk_budget',     name: 'RESOURCE OPTIMIZATION', cost: 2, tier: 1, prereqs: [],                      archetype_discount: null },
  { id: 'trunk_sda',        name: 'SPACE DOMAIN AWARENESS',cost: 2, tier: 1, prereqs: [],                      archetype_discount: null },
  { id: 'trunk_resilience', name: 'HARDENED SYSTEMS',      cost: 2, tier: 1, prereqs: [],                      archetype_discount: null },
  // Kinetic — discount: mahanian
  { id: 'kin_ground_strike',    name: 'TERRESTRIAL STRIKE',   cost: 3, tier: 2, prereqs: ['_any_trunk'],           archetype_discount: 'mahanian' },
  { id: 'kin_da_asat',          name: 'DIRECT-ASCENT ASAT',   cost: 4, tier: 3, prereqs: ['kin_ground_strike'],    archetype_discount: 'mahanian' },
  { id: 'kin_deterrence',       name: 'DETERRENCE OPS',        cost: 4, tier: 3, prereqs: ['kin_ground_strike'],    archetype_discount: 'mahanian' },
  { id: 'kin_rapid_ascent',     name: 'RAPID ASCENT',          cost: 5, tier: 4, prereqs: ['kin_da_asat'],          archetype_discount: 'mahanian' },
  { id: 'kin_intercept_k',      name: 'KINETIC INTERCEPT',     cost: 5, tier: 4, prereqs: ['kin_deterrence'],       archetype_discount: 'mahanian' },
  { id: 'kin_cascade_doctrine', name: 'KESSLER DOCTRINE',      cost: 8, tier: 5, prereqs: ['kin_rapid_ascent'],     archetype_discount: 'mahanian' },
  // Non-Kinetic — discount: rogue_accelerationist
  { id: 'nk_dazzle',            name: 'LASER DAZZLE',          cost: 3, tier: 2, prereqs: ['_any_trunk'],           archetype_discount: 'rogue_accelerationist' },
  { id: 'nk_directed_energy',   name: 'DIRECTED ENERGY',       cost: 4, tier: 3, prereqs: ['nk_dazzle'],            archetype_discount: 'rogue_accelerationist' },
  { id: 'nk_debris_doctrine',   name: 'DEBRIS DOCTRINE',       cost: 4, tier: 3, prereqs: ['nk_dazzle'],            archetype_discount: 'rogue_accelerationist' },
  { id: 'nk_power_projection',  name: 'POWER PROJECTION',      cost: 5, tier: 4, prereqs: ['nk_directed_energy'],   archetype_discount: 'rogue_accelerationist' },
  { id: 'nk_precision_de',      name: 'PRECISION DE',          cost: 5, tier: 4, prereqs: ['nk_debris_doctrine'],   archetype_discount: 'rogue_accelerationist' },
  { id: 'nk_starfish',          name: 'STARFISH PRIME',        cost: 8, tier: 5, prereqs: ['nk_power_projection'],  archetype_discount: 'rogue_accelerationist' },
  // Electronic — discount: gray_zone
  { id: 'ew_jamming',           name: 'SIGNAL JAMMING',        cost: 3, tier: 2, prereqs: ['_any_trunk'],           archetype_discount: 'gray_zone' },
  { id: 'ew_wideband',          name: 'WIDE-BAND JAMMING',     cost: 4, tier: 3, prereqs: ['ew_jamming'],           archetype_discount: 'gray_zone' },
  { id: 'ew_spoofing',          name: 'GPS SPOOFING',          cost: 4, tier: 3, prereqs: ['ew_jamming'],           archetype_discount: 'gray_zone' },
  { id: 'ew_signature_mask',    name: 'SIGNATURE MASKING',     cost: 5, tier: 4, prereqs: ['ew_wideband'],          archetype_discount: 'gray_zone' },
  { id: 'ew_deep_influence',    name: 'DEEP INFLUENCE',        cost: 5, tier: 4, prereqs: ['ew_spoofing'],          archetype_discount: 'gray_zone' },
  { id: 'ew_full_spectrum',     name: 'FULL-SPECTRUM DENIAL',  cost: 8, tier: 5, prereqs: ['ew_signature_mask'],    archetype_discount: 'gray_zone' },
  // Cyber — discount: commercial_broker
  { id: 'cyber_intrusion',      name: 'CMD LINK INTRUSION',    cost: 3, tier: 2, prereqs: ['_any_trunk'],           archetype_discount: 'commercial_broker' },
  { id: 'com_market',           name: 'MARKET DOMINANCE',      cost: 4, tier: 3, prereqs: ['cyber_intrusion'],      archetype_discount: 'commercial_broker' },
  { id: 'com_revenue',          name: 'CAPACITY REVENUE',      cost: 4, tier: 3, prereqs: ['cyber_intrusion'],      archetype_discount: 'commercial_broker' },
  { id: 'com_network',          name: 'ORBITAL NETWORK',       cost: 5, tier: 4, prereqs: ['com_market'],           archetype_discount: 'commercial_broker' },
  { id: 'com_economics',        name: 'SCALE ECONOMICS',       cost: 5, tier: 4, prereqs: ['com_revenue'],          archetype_discount: 'commercial_broker' },
  { id: 'cyber_darknet',        name: 'SPACE DARKNET',         cost: 8, tier: 5, prereqs: ['com_network'],          archetype_discount: 'commercial_broker' },
]

const NODE_BY_ID = Object.fromEntries(NODE_META.map(n => [n.id, n]))

// One column per threat category with its node IDs in layout order
const TREES: { label: string; color: string; t1: string; t2: [string, string]; t3: [string, string]; t4: string }[] = [
  { label: 'KINETIC',      color: '#ff4499', t1: 'kin_ground_strike', t2: ['kin_da_asat',        'kin_deterrence'],    t3: ['kin_rapid_ascent',    'kin_intercept_k'],   t4: 'kin_cascade_doctrine' },
  { label: 'NON-KINETIC',  color: '#f59e0b', t1: 'nk_dazzle',         t2: ['nk_directed_energy', 'nk_debris_doctrine'],t3: ['nk_power_projection', 'nk_precision_de'],   t4: 'nk_starfish'          },
  { label: 'ELECTRONIC',   color: '#00d4ff', t1: 'ew_jamming',         t2: ['ew_wideband',        'ew_spoofing'],       t3: ['ew_signature_mask',   'ew_deep_influence'], t4: 'ew_full_spectrum'     },
  { label: 'CYBER',        color: '#4ade80', t1: 'cyber_intrusion',    t2: ['com_market',         'com_revenue'],       t3: ['com_network',         'com_economics'],     t4: 'cyber_darknet'        },
]

// SVG layout constants
const NW = 130, NH = 38
const HALF_GAP = 72       // must be > NW/2 = 65 to prevent box overlap
const SVG_W = 1400
const TRUNK_Y = 55
const T1_Y = 185
const T2_Y = 305
const T3_Y = 430
const T4_Y = 558
const SVG_H = 630
const COL_X = [175, 525, 875, 1225]
const TRUNK_CX = [175, 445, 700, 955, 1225]

function prereqsMet(node: NodeMeta, unlocked: string[]): boolean {
  const hasAnyTrunk = TRUNK_IDS.some(id => unlocked.includes(id))
  return node.prereqs.every(p => p === '_any_trunk' ? hasAnyTrunk : unlocked.includes(p))
}

function effectiveCost(node: NodeMeta, archetype: string): number {
  if (node.archetype_discount && node.archetype_discount === archetype) {
    return Math.max(1, node.cost - 1)
  }
  return node.cost
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
  if (!prereqsMet(meta, unlocked)) return '#64748b'
  if (rdPoints < effectiveCost(meta, humanArchetype)) return '#64748b'
  return '#f59e0b'
}

interface NodeBoxProps {
  id: string; cx: number; cy: number
  phase: string; unlocked: string[]; pending: string[]
  rdPoints: number; humanArchetype: string
  treeColor: string
  onQueueToggle: (id: string) => void
}

function NodeBox({ id, cx, cy, phase, unlocked, pending, rdPoints, humanArchetype, treeColor, onQueueToggle }: NodeBoxProps) {
  const color = nodeColor(id, phase, unlocked, pending, rdPoints, humanArchetype)
  const meta = NODE_BY_ID[id]
  if (!meta) return null
  const clickable = color === '#f59e0b' || color === '#00d4ff'
  const isUnlocked = unlocked.includes(id)
  const isPending = pending.includes(id)
  const cost = effectiveCost(meta, humanArchetype)
  const discounted = meta.archetype_discount === humanArchetype && cost < meta.cost
  const isT4 = meta.tier === 5

  const label = isPending ? 'QUEUED'
    : isUnlocked ? '✓ UNLOCKED'
    : discounted ? `${cost} pts ★`
    : `${cost} pts`

  const borderColor = isT4 ? (clickable ? treeColor : '#475569') : color
  const borderWidth = isT4 ? 2 : (clickable ? 2 : 1.5)

  return (
    <g
      onClick={clickable ? () => onQueueToggle(id) : undefined}
      style={{ cursor: clickable ? 'pointer' : 'default' }}
    >
      <rect
        x={cx - NW / 2} y={cy - NH / 2} width={NW} height={NH}
        fill="rgba(2,11,24,0.92)"
        stroke={borderColor} strokeWidth={borderWidth}
        strokeDasharray={isT4 && !isUnlocked && !isPending ? '5 3' : undefined}
        rx={2}
      />
      {(clickable || isUnlocked || isPending) && (
        <rect
          x={cx - NW / 2} y={cy - NH / 2} width={NW} height={NH}
          fill={color} fillOpacity={isUnlocked ? 0.08 : 0.06} rx={2}
        />
      )}
      <text x={cx} y={cy - 5} textAnchor="middle" fill={color}
        fontSize={9} fontFamily="Courier New" letterSpacing={0}>
        {meta.name}
      </text>
      <text x={cx} y={cy + 10} textAnchor="middle"
        fill={color} fillOpacity={0.9} fontSize={9} fontFamily="Courier New">
        {label}
      </text>
      {discounted && !isUnlocked && !isPending && (
        <text x={cx + NW / 2 - 3} y={cy - NH / 2 + 8} textAnchor="end"
          fill={treeColor} fontSize={7} fontFamily="Courier New" opacity={0.7}>
          DISC
        </text>
      )}
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
    return unlocked.includes(fromId) ? '#00ff8866' : '#334155'
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
        <span className="mono" style={{ fontSize: 9, color: '#334155', marginLeft: 8 }}>
          ★ = archetype discount
        </span>
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
          {/* Trunk rail and connectors */}
          <line
            x1={TRUNK_CX[0]} y1={TRUNK_Y + NH / 2 + 8}
            x2={TRUNK_CX[4]} y2={TRUNK_Y + NH / 2 + 8}
            stroke="#334155" strokeWidth={1}
          />
          {COL_X.map(cx => (
            <line key={cx}
              x1={cx} y1={TRUNK_Y + NH / 2 + 8}
              x2={cx} y2={T1_Y - NH / 2 - 6}
              stroke="#334155" strokeWidth={1}
            />
          ))}

          {/* Trunk nodes */}
          {TRUNK_IDS.map((id, i) => (
            <NodeBox key={id} id={id} cx={TRUNK_CX[i]} cy={TRUNK_Y}
              phase={currentPhase} unlocked={unlocked} pending={pendingUnlocks}
              rdPoints={rdPoints} humanArchetype={humanArchetype}
              treeColor="#94a3b8"
              onQueueToggle={onQueueToggle}
            />
          ))}

          {/* Threat-category columns */}
          {TREES.map((tree, colIdx) => {
            const cx = COL_X[colIdx]
            const { label, color, t1, t2, t3, t4 } = tree
            const [t2a, t2b] = t2
            const [t3a, t3b] = t3

            return (
              <g key={tree.label}>
                {/* Column label */}
                <text x={cx} y={T1_Y - NH / 2 - 16}
                  textAnchor="middle" fill={color}
                  fontSize={9} fontFamily="Courier New" letterSpacing={2} opacity={0.8}>
                  {label}
                </text>

                {/* T1 → T2 connectors */}
                <line x1={cx} y1={T1_Y + NH / 2} x2={cx - HALF_GAP} y2={T2_Y - NH / 2 - 4}
                  stroke={lineColor(t1)} strokeWidth={1.5} />
                <line x1={cx} y1={T1_Y + NH / 2} x2={cx + HALF_GAP} y2={T2_Y - NH / 2 - 4}
                  stroke={lineColor(t1)} strokeWidth={1.5} />

                {/* T2 → T3 connectors */}
                <line x1={cx - HALF_GAP} y1={T2_Y + NH / 2} x2={cx - HALF_GAP} y2={T3_Y - NH / 2 - 4}
                  stroke={lineColor(t2a)} strokeWidth={1.5} />
                <line x1={cx + HALF_GAP} y1={T2_Y + NH / 2} x2={cx + HALF_GAP} y2={T3_Y - NH / 2 - 4}
                  stroke={lineColor(t2b)} strokeWidth={1.5} />

                {/* T3a → T4 connector (left branch feeds T4) */}
                <line x1={cx - HALF_GAP} y1={T3_Y + NH / 2} x2={cx} y2={T4_Y - NH / 2 - 4}
                  stroke={lineColor(t3a)} strokeWidth={1.5} />

                {/* T1 node */}
                <NodeBox id={t1} cx={cx} cy={T1_Y}
                  phase={currentPhase} unlocked={unlocked} pending={pendingUnlocks}
                  rdPoints={rdPoints} humanArchetype={humanArchetype} treeColor={color}
                  onQueueToggle={onQueueToggle}
                />

                {/* T2 nodes */}
                <NodeBox id={t2a} cx={cx - HALF_GAP} cy={T2_Y}
                  phase={currentPhase} unlocked={unlocked} pending={pendingUnlocks}
                  rdPoints={rdPoints} humanArchetype={humanArchetype} treeColor={color}
                  onQueueToggle={onQueueToggle}
                />
                <NodeBox id={t2b} cx={cx + HALF_GAP} cy={T2_Y}
                  phase={currentPhase} unlocked={unlocked} pending={pendingUnlocks}
                  rdPoints={rdPoints} humanArchetype={humanArchetype} treeColor={color}
                  onQueueToggle={onQueueToggle}
                />

                {/* T3 nodes */}
                <NodeBox id={t3a} cx={cx - HALF_GAP} cy={T3_Y}
                  phase={currentPhase} unlocked={unlocked} pending={pendingUnlocks}
                  rdPoints={rdPoints} humanArchetype={humanArchetype} treeColor={color}
                  onQueueToggle={onQueueToggle}
                />
                <NodeBox id={t3b} cx={cx + HALF_GAP} cy={T3_Y}
                  phase={currentPhase} unlocked={unlocked} pending={pendingUnlocks}
                  rdPoints={rdPoints} humanArchetype={humanArchetype} treeColor={color}
                  onQueueToggle={onQueueToggle}
                />

                {/* T4 capstone node */}
                <NodeBox id={t4} cx={cx} cy={T4_Y}
                  phase={currentPhase} unlocked={unlocked} pending={pendingUnlocks}
                  rdPoints={rdPoints} humanArchetype={humanArchetype} treeColor={color}
                  onQueueToggle={onQueueToggle}
                />
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}
