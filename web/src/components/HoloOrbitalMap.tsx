// web/src/components/HoloOrbitalMap.tsx
import { useMemo } from 'react'
import type { GameState, FactionState } from '../types'

export const TILT_FACTOR = 0.45
const CX = 130
const CY = 130
const DOT_CAP = 8; void DOT_CAP

const RINGS = [
  { label: 'LEO', r: 48,  sw: 1,   dash: undefined as string | undefined, nodeKey: 'leo_nodes' as const, icon: '◎', shell: 'leo' as const },
  { label: 'MEO', r: 70,  sw: 1.5, dash: undefined as string | undefined, nodeKey: 'meo_nodes' as const, icon: '⊕', shell: 'meo' as const },
  { label: 'GEO', r: 97,  sw: 3,   dash: undefined as string | undefined, nodeKey: 'geo_nodes' as const, icon: '≋', shell: 'geo' as const },
  { label: 'CIS', r: 115, sw: 1.5, dash: '4,4',                           nodeKey: 'cislunar_nodes' as const, icon: '☽', shell: 'cislunar' as const },
] as const

const LAGRANGE = [
  { label: 'L1', angle: 0,                    icon: '◆' },
  { label: 'L2', angle: Math.PI,              icon: '◆' },
  { label: 'L4', angle: Math.PI / 2,          icon: '▲' },
  { label: 'L5', angle: (3 * Math.PI) / 2,   icon: '▲' },
]

// 100 hardcoded star positions across viewBox (-45 55 350 210 → x: -45..305, y: 55..265)
const STARS = [
  {x:-12,y:68,r:0.4},{x:203,y:91,r:0.6},{x:47,y:159,r:0.3},{x:287,y:72,r:0.5},
  {x:134,y:63,r:0.4},{x:31,y:204,r:0.7},{x:261,y:183,r:0.4},{x:89,y:241,r:0.3},
  {x:194,y:248,r:0.6},{x:-29,y:127,r:0.5},{x:302,y:134,r:0.4},{x:167,y:216,r:0.3},
  {x:78,y:88,r:0.8},{x:243,y:215,r:0.5},{x:14,y:175,r:0.4},{x:321,y:199,r:0.6},
  {x:112,y:230,r:0.3},{x:56,y:131,r:0.5},{x:271,y:103,r:0.4},{x:188,y:74,r:0.7},
  {x:-38,y:244,r:0.3},{x:146,y:192,r:0.4},{x:39,y:58,r:0.6},{x:224,y:171,r:0.3},
  {x:295,y:249,r:0.5},{x:4,y:99,r:0.4},{x:175,y:132,r:0.3},{x:68,y:197,r:0.7},
  {x:251,y:60,r:0.4},{x:120,y:117,r:0.5},{x:-20,y:163,r:0.3},{x:313,y:88,r:0.6},
  {x:95,y:74,r:0.4},{x:239,y:237,r:0.5},{x:157,y:258,r:0.3},{x:22,y:219,r:0.4},
  {x:280,y:152,r:0.7},{x:52,y:249,r:0.3},{x:201,y:113,r:0.5},{x:139,y:78,r:0.4},
  {x:-35,y:184,r:0.6},{x:319,y:162,r:0.4},{x:82,y:202,r:0.3},{x:264,y:91,r:0.5},
  {x:178,y:239,r:0.4},{x:34,y:142,r:0.7},{x:247,y:196,r:0.3},{x:110,y:63,r:0.5},
  {x:291,y:211,r:0.4},{x:163,y:155,r:0.3},{x:-18,y:73,r:0.6},{x:326,y:236,r:0.4},
  {x:75,y:173,r:0.5},{x:218,y:57,r:0.3},{x:143,y:224,r:0.7},{x:11,y:248,r:0.4},
  {x:275,y:181,r:0.5},{x:98,y:110,r:0.3},{x:232,y:138,r:0.4},{x:59,y:91,r:0.6},
  {x:187,y:201,r:0.3},{x:-28,y:107,r:0.5},{x:305,y:74,r:0.4},{x:151,y:99,r:0.7},
  {x:43,y:222,r:0.3},{x:267,y:149,r:0.5},{x:116,y:186,r:0.4},{x:335,y:119,r:0.3},
  {x:72,y:143,r:0.6},{x:208,y:231,r:0.4},{x:131,y:57,r:0.5},{x:-41,y:197,r:0.3},
  {x:297,y:117,r:0.7},{x:65,y:259,r:0.4},{x:221,y:92,r:0.5},{x:156,y:174,r:0.3},
  {x:25,y:80,r:0.4},{x:283,y:241,r:0.6},{x:103,y:229,r:0.3},{x:242,y:67,r:0.5},
  {x:174,y:118,r:0.4},{x:-14,y:238,r:0.7},{x:309,y:193,r:0.3},{x:87,y:157,r:0.5},
  {x:198,y:183,r:0.4},{x:46,y:168,r:0.3},{x:257,y:214,r:0.6},{x:128,y:248,r:0.4},
  {x:336,y:81,r:0.5},{x:17,y:133,r:0.3},{x:279,y:58,r:0.7},{x:93,y:83,r:0.4},
  {x:229,y:163,r:0.5},{x:164,y:91,r:0.3},{x:-32,y:149,r:0.4},{x:318,y:227,r:0.6},
  {x:55,y:116,r:0.4},{x:190,y:259,r:0.5},{x:142,y:140,r:0.3},{x:276,y:200,r:0.6},
]

type TextAnchor = 'start' | 'end' | 'middle'
type DomBaseline = 'hanging' | 'auto' | 'middle'

function ellipsePoint(r: number, angle: number) {
  return { x: CX + r * Math.cos(angle), y: CY + r * TILT_FACTOR * Math.sin(angle) }
}

function factionColor(fid: string, gs: GameState): string {
  if (fid === gs.human_faction_id) return '#00ff88'
  const entry = Object.entries(gs.coalition_states).find(([, cs]) => cs.member_ids.includes(fid))
  if (!entry) return '#00d4ff'
  return gs.coalition_colors[entry[0]] === 'green' ? '#00ff88' : '#ff4499'
}

function labelAnchor(angle: number): { textAnchor: TextAnchor; dominantBaseline: DomBaseline } {
  const cos = Math.cos(angle)
  const sin = Math.sin(angle)
  return {
    textAnchor: cos > 0.25 ? 'start' : cos < -0.25 ? 'end' : 'middle',
    dominantBaseline: sin > 0.25 ? 'hanging' : sin < -0.25 ? 'auto' : 'middle',
  }
}

interface Props {
  gameState: GameState
  prevFactionStates: Record<string, FactionState> | null
  humanAdversaryEstimates: Record<string, {
    leo_nodes: number; meo_nodes: number; geo_nodes: number; cislunar_nodes: number
    asat_kinetic: number; asat_deniable: number; ew_jammers: number; sda_sensors: number
    relay_nodes: number; launch_capacity: number
  }>
  selectedShell?: string | null
  selectedFaction?: string | null
  onShellHover?: (shell: string | null) => void
  onFactionHover?: (faction: string | null) => void
}

export default function HoloOrbitalMap({
  gameState, prevFactionStates, humanAdversaryEstimates,
  selectedShell, selectedFaction, onShellHover, onFactionHover,
}: Props) {
  void prevFactionStates
  void humanAdversaryEstimates
  void onFactionHover
  const factions = useMemo(() => Object.entries(gameState.faction_states), [gameState])
  const angleStep = (Math.PI * 2) / Math.max(factions.length, 1)

  return (
    <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="panel-title">◆ ORBITAL MAP</div>
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        <svg viewBox="-45 55 350 210" preserveAspectRatio="xMidYMid meet"
          style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}>

          <defs>
            <radialGradient id="gravity-well" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#1a3a5c" />
              <stop offset="50%" stopColor="#040d1a" />
              <stop offset="100%" stopColor="#010508" />
            </radialGradient>
          </defs>

          {/* Background: gravity well gradient */}
          <rect x="-45" y="55" width="350" height="210" fill="url(#gravity-well)" />

          {/* Star field */}
          <g opacity={0.15}>
            {STARS.map((s, i) => (
              <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="#ffffff" />
            ))}
          </g>

          {/* Orbital rings */}
          {RINGS.map(({ r, sw, dash, shell }) => {
            const open = gameState.access_windows?.[shell] ?? true
            const debris = gameState.debris_fields?.[shell] ?? 0
            const kessler = debris >= 0.8
            const isSelected = selectedShell === shell
            const ringColor = kessler ? '#ef4444' : isSelected ? '#00d4ffcc' : 'rgba(0,212,255,0.15)'
            const ringOpacity = open || kessler ? 1 : 0.2
            const animDur = kessler ? '1s' : '3s'

            return (
              <g key={r}
                onMouseEnter={() => onShellHover?.(shell)}
                onMouseLeave={() => onShellHover?.(null)}
                style={{ cursor: 'pointer' }}>
                <ellipse cx={CX} cy={CY} rx={r} ry={r * TILT_FACTOR}
                  fill="none" stroke={ringColor} strokeWidth={sw}
                  strokeDasharray={dash} opacity={ringOpacity}>
                  {open && (
                    <animate attributeName="opacity"
                      values={`${ringOpacity * 0.5};${ringOpacity};${ringOpacity * 0.5}`}
                      dur={animDur} repeatCount="indefinite" />
                  )}
                </ellipse>

                {/* Debris overlay ellipse */}
                {debris >= 0.1 && (() => {
                  const debrisColor = kessler ? '#ef4444' : '#f97316'
                  const debrisOpacity = Math.min(debris * 0.6, 0.5)
                  return (
                    <ellipse cx={CX} cy={CY} rx={r} ry={r * TILT_FACTOR}
                      fill="none" stroke={debrisColor}
                      strokeWidth={kessler ? 3 : 1.5}
                      strokeDasharray="3,6"
                      opacity={debrisOpacity} />
                  )
                })()}

                {/* Shell mission icon at 12 o'clock (angle = -π/2) */}
                {(() => {
                  const pt = ellipsePoint(r, -Math.PI / 2)
                  const ringEntry = RINGS.find(ring => ring.r === r)!
                  const hasNodes = Object.values(gameState.faction_states).some(
                    (fs) => fs.assets[ringEntry.nodeKey] > 0
                  )
                  return (
                    <text x={pt.x} y={pt.y - 5} fill="rgba(0,212,255,1)"
                      fontSize={8} fontFamily="monospace" textAnchor="middle"
                      opacity={hasNodes ? 0.7 : 0.25}>
                      {ringEntry.icon}
                    </text>
                  )
                })()}
              </g>
            )
          })}

          {/* Lagrange markers on CIS ring (r=115) */}
          {LAGRANGE.map(({ label, angle, icon }) => {
            const pt = ellipsePoint(115, angle)
            return (
              <g key={label}>
                <text x={pt.x} y={pt.y} fill="rgba(0,212,255,0.35)"
                  fontSize={7} fontFamily="monospace" textAnchor="middle" dominantBaseline="middle">
                  {icon}
                </text>
                <text x={pt.x} y={pt.y + 7} fill="rgba(0,212,255,0.2)"
                  fontSize={5} fontFamily="monospace" textAnchor="middle">
                  {label}
                </text>
              </g>
            )
          })}

          {/* Moon at ~45° on CIS */}
          {(() => {
            const pt = ellipsePoint(115, Math.PI / 4)
            return (
              <circle cx={pt.x} cy={pt.y} r={2.5}
                fill="#334155" stroke="rgba(0,212,255,0.3)" strokeWidth={0.5} />
            )
          })()}

          {/* Earth */}
          <ellipse cx={CX} cy={CY} rx={12} ry={12 * TILT_FACTOR}
            fill="#020b18" stroke="rgba(0,212,255,0.5)" strokeWidth={1.5} />
          <text x={CX} y={CY + 1} fill="rgba(0,212,255,0.6)" fontSize={9}
            fontFamily="monospace" textAnchor="middle" dominantBaseline="middle">⊕</text>

          {/* Faction name labels — outside CIS ring (r=122) */}
          {factions.map(([fid, fs], idx) => {
            const angle = idx * angleStep
            const pt = ellipsePoint(122, angle)
            const { textAnchor, dominantBaseline } = labelAnchor(angle)
            const color = factionColor(fid, gameState)
            const label = fs.name.length > 12 ? fs.name.slice(0, 11) + '…' : fs.name
            const dimmed = selectedFaction !== null && selectedFaction !== fid
            return (
              <text key={`label-${fid}`} x={pt.x} y={pt.y} fill={color}
                fontSize={7} fontFamily="monospace"
                textAnchor={textAnchor} dominantBaseline={dominantBaseline}
                opacity={dimmed ? 0.25 : 0.85}>
                {label}
              </text>
            )
          })}

          {/* Faction nodes, kinetic animation — added in Task 7 */}
        </svg>
      </div>
    </div>
  )
}
