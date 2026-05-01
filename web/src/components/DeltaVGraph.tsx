// web/src/components/DeltaVGraph.tsx
import type { GameState } from '../types'

interface Props {
  gameState: GameState
  coalitionDominance: Record<string, number>
  selectedShell: string | null
  selectedFaction: string | null
  onShellClick: (shell: string | null) => void
  onFactionClick: (faction: string | null) => void
}

const DV_NODES = [
  { id: 'earth', label: 'EARTH', icon: '⊕',  shell: null       as null },
  { id: 'leo',   label: 'LEO',   icon: '◎',  shell: 'leo'      as const },
  { id: 'meo',   label: 'MEO',   icon: '⊕',  shell: 'meo'      as const },
  { id: 'geo',   label: 'GEO',   icon: '≋',  shell: 'geo'      as const },
  { id: 'cis',   label: 'CIS',   icon: '☽',  shell: 'cislunar' as const },
]

const DV_EDGES = [
  { from: 'earth', to: 'leo', dv: 9.4, label: '9.4 km/s (launch)' },
  { from: 'leo',   to: 'meo', dv: 1.5, label: '1.5 km/s' },
  { from: 'meo',   to: 'geo', dv: 1.8, label: '1.8 km/s' },
  { from: 'geo',   to: 'cis', dv: 0.7, label: '0.7 km/s' },
]

const SHELL_STRATEGIC: Record<string, string> = {
  leo: 'Cheapest shell to access and contest. Dense ISR and SDA coverage. High debris accumulation risk — a Kessler event here blocks the most active operational zone in the theater.',
  meo: 'Navigation and GNSS hub. Moderate maneuver cost keeps it less contested than LEO. Losing MEO degrades positioning precision for all coalition operations.',
  geo: 'Scarce slots with permanent equatorial line-of-sight. The most expensive single hop in theater. Factions that establish here early pay nothing to hold — adversaries pay 1.8 km/s to match.',
  cislunar: 'Frontier territory — L1/L2 gateways, L4/L5 staging, and lunar orbit. Surprisingly cheap from GEO but only reachable through it. Controls future logistics chokepoints. Access windows follow a 4-turn cycle.',
}

function accessReason(
  shell: string,
  open: boolean,
  kessler: boolean,
  debris: number,
  nextOpenTurn: number | null,
): string {
  if (kessler) {
    return `Debris cascade — field density at ${Math.round(debris * 100)}% has exceeded the safe operational threshold. Existing nodes are at risk of attrition each turn. Shell remains impassable until debris disperses naturally.`
  }
  if (debris >= 0.4 && open) {
    return `Window open but debris density is elevated at ${Math.round(debris * 100)}%. Operations are possible this turn. Continued ASAT use risks crossing the Kessler threshold and triggering a cascade.`
  }
  if (open) {
    switch (shell) {
      case 'leo':      return 'Orbital conjunction has cleared. Launch corridors are aligned and debris density is within safe limits — deployments to LEO can proceed this turn.'
      case 'meo':      return 'Transfer window is active. Hohmann trajectories to MEO are favorable this turn. Launch corridor will close and reopen on a short cycle.'
      case 'geo':      return 'Geostationary insertion corridor is available. Apogee kick burn timing is favorable. GEO windows are less predictable than LEO — use this turn if deployment is planned.'
      case 'cislunar': return 'Lunar transfer corridor is aligned. The 4-turn synodic cycle is at its favorable phase — trans-lunar injection burns are available this turn. Missing this window means waiting up to 4 turns for realignment.'
    }
  } else {
    switch (shell) {
      case 'leo':      return `Orbital conjunction in effect — active debris field is blocking the standard launch corridor. Ground tracks are unfavorable for insertion burns. Window clears next turn (T${nextOpenTurn}).`
      case 'meo':      return `Transfer window has closed — Hohmann trajectory angles are unfavorable for MEO insertion this turn. Launch must wait for the next orbital alignment (T${nextOpenTurn}).`
      case 'geo':      return 'Geostationary insertion timing is unfavorable — apogee kick burn window has passed for this turn. GEO access does not follow a fixed cycle; monitor for the next available corridor.'
      case 'cislunar': return `Lunar transfer window is closed — the 4-turn synodic cycle is in its unfavorable phase. Trans-lunar injection burns cannot be executed efficiently this turn. Next alignment at T${nextOpenTurn}.`
    }
  }
  return ''
}

const NODE_KEY_MAP: Record<string, 'leo_nodes' | 'meo_nodes' | 'geo_nodes' | 'cislunar_nodes'> = {
  leo: 'leo_nodes', meo: 'meo_nodes', geo: 'geo_nodes', cislunar: 'cislunar_nodes',
}

function dvColor(dv: number): string {
  if (dv <= 1.0) return '#00ff88'
  if (dv <= 2.0) return '#f59e0b'
  return '#ff4499'
}

export default function DeltaVGraph({
  gameState, coalitionDominance, selectedShell, selectedFaction, onShellClick, onFactionClick,
}: Props) {
  void coalitionDominance
  const factions = Object.entries(gameState.faction_states)

  function getFactionColor(fid: string): string {
    if (fid === gameState.human_faction_id) return '#00ff88'
    const entry = Object.entries(gameState.coalition_states).find(([, cs]) => cs.member_ids.includes(fid))
    if (!entry) return '#00d4ff'
    return gameState.coalition_colors[entry[0]] === 'green' ? '#00ff88' : '#ff4499'
  }

  return (
    <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '8px 12px' }}>
      <div className="panel-title">◆ DELTA-V GRAPH</div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {[...DV_NODES].reverse().map((node, reversedIdx) => {
          const nodeIdx = DV_NODES.length - 1 - reversedIdx
          const edge = DV_EDGES[nodeIdx - 1]
          const shell = node.shell
          const assetKey = shell ? NODE_KEY_MAP[shell] : null
          const open = shell ? (gameState.access_windows?.[shell] ?? true) : true
          const debris = shell ? (gameState.debris_fields?.[shell] ?? 0) : 0
          const kessler = debris >= 0.8
          const isSelected = shell && selectedShell === shell
          const nodeColor = kessler ? '#ef4444' : isSelected ? '#00d4ff' : 'rgba(0,212,255,0.8)'
          const dimmed = selectedShell !== null && !isSelected && shell !== null

          const totalNodes = assetKey
            ? factions.reduce((sum, [, fs]) => sum + (fs.assets[assetKey] ?? 0), 0)
            : 0

          // Access window annotation for the connector below this node
          const accessColor = kessler ? '#ef4444' : open ? '#00ff88' : '#64748b'
          const accessLabel = kessler ? 'KESSLER' : open ? 'OPEN' : 'CLOSED'
          const nextOpenTurn = (() => {
            if (!shell || open || kessler) return null
            switch (shell) {
              case 'leo': return gameState.turn + 1
              case 'meo': return gameState.turn + 1
              case 'cislunar': { const k = ((1 - (gameState.turn % 4)) + 4) % 4 || 4; return gameState.turn + k }
              default: return null
            }
          })()

          return (
            <div key={node.id} style={{
              flex: edge ? 1 : '0 0 auto',
              display: 'flex', flexDirection: 'column',
              minHeight: 0,
            }}>
              {/* Node box */}
              <div
                onClick={() => shell && onShellClick(selectedShell === shell ? null : shell)}
                style={{
                  border: `1px solid ${isSelected ? '#00d4ff' : 'rgba(0,212,255,0.2)'}`,
                  borderRadius: 3, padding: '6px 10px', cursor: shell ? 'pointer' : 'default',
                  background: isSelected ? 'rgba(0,212,255,0.08)' : 'transparent',
                  opacity: dimmed ? 0.35 : 1,
                  boxShadow: open && shell ? '0 0 6px rgba(0,212,255,0.1)' : 'none',
                  flexShrink: 0,
                }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontFamily: 'Courier New', fontSize: 13, color: nodeColor, letterSpacing: 1 }}>
                    {node.icon} {node.label}
                  </span>
                  {node.id === 'cis' && (
                    <span style={{ fontFamily: 'Courier New', fontSize: 11, color: '#475569' }}>
                      4 sub-positions: L1·L2·L4·L5
                    </span>
                  )}
                  {kessler && (
                    <span style={{ fontFamily: 'Courier New', fontSize: 10, color: '#ef4444', letterSpacing: 1 }}>
                      KESSLER
                    </span>
                  )}
                </div>

                {assetKey && totalNodes > 0 && (
                  <div style={{ display: 'flex', height: 5, borderRadius: 2, overflow: 'hidden', marginTop: 5 }}>
                    {factions.map(([fid, fs]) => {
                      const count = fs.assets[assetKey] ?? 0
                      if (count === 0) return null
                      const pct = (count / totalNodes) * 100
                      const color = getFactionColor(fid)
                      const fDimmed = selectedFaction !== null && selectedFaction !== fid
                      return (
                        <div key={fid}
                          style={{ width: `${pct}%`, background: color, opacity: fDimmed ? 0.25 : 1 }}
                          onClick={(e) => { e.stopPropagation(); onFactionClick(selectedFaction === fid ? null : fid) }}
                          title={`${fid}: ${count} nodes`}
                        />
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Connector — flex:1 fills the full gap, now with strategic context */}
              {edge && (
                <div style={{ flex: 1, display: 'flex', alignItems: 'stretch', paddingLeft: 21, minHeight: 48 }}>
                  <div style={{ width: 2, background: dvColor(edge.dv), flexShrink: 0 }} />
                  <div style={{ flex: 1, paddingLeft: 12, paddingTop: 8, paddingBottom: 8, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 6 }}>
                    {/* Cost + access status */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                      <span style={{
                        fontFamily: 'Courier New', fontSize: 12,
                        color: kessler ? '#ef4444' : dvColor(edge.dv),
                        letterSpacing: 1,
                      }}>
                        {kessler ? 'KESSLER — BLOCKED' : edge.label}
                      </span>
                      {shell && (
                        <span style={{ fontFamily: 'Courier New', fontSize: 12, color: accessColor }}>
                          ● {accessLabel}{nextOpenTurn ? ` · opens T${nextOpenTurn}` : ''}
                          {debris > 0 && !kessler && ` · debris ${Math.round(debris * 100)}%`}
                        </span>
                      )}
                    </div>
                    {/* Strategic importance */}
                    {shell && (
                      <p style={{ margin: 0, fontSize: 12, color: '#475569', lineHeight: 1.6, maxWidth: '90%' }}>
                        {SHELL_STRATEGIC[shell]}
                      </p>
                    )}
                    {/* Why open or closed this turn */}
                    {shell && (
                      <p style={{ margin: 0, fontSize: 12, color: open && !kessler ? '#00ff8899' : kessler ? '#ef444499' : '#64748b', lineHeight: 1.6, maxWidth: '90%' }}>
                        {accessReason(shell, open, kessler, debris, nextOpenTurn)}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
