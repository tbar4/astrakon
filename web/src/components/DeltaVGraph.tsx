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
  { id: 'earth',    label: 'EARTH',   icon: '⊕',  shell: null        as null },
  { id: 'leo',      label: 'LEO',     icon: '◎',  shell: 'leo'       as const },
  { id: 'meo',      label: 'MEO',     icon: '⊕',  shell: 'meo'       as const },
  { id: 'geo',      label: 'GEO',     icon: '≋',  shell: 'geo'       as const },
  { id: 'cis',      label: 'CIS',     icon: '☽',  shell: 'cislunar'  as const },
]

const DV_EDGES = [
  { from: 'earth', to: 'leo', dv: 9.4, label: '9.4 km/s (launch)' },
  { from: 'leo',   to: 'meo', dv: 1.5, label: '1.5 km/s' },
  { from: 'meo',   to: 'geo', dv: 1.8, label: '1.8 km/s' },
  { from: 'geo',   to: 'cis', dv: 0.7, label: '0.7 km/s' },
]

function dvColor(dv: number): string {
  if (dv <= 1.0) return '#00ff88'
  if (dv <= 2.0) return '#f59e0b'
  return '#ff4499'
}

const NODE_KEY_MAP: Record<string, 'leo_nodes' | 'meo_nodes' | 'geo_nodes' | 'cislunar_nodes'> = {
  leo: 'leo_nodes', meo: 'meo_nodes', geo: 'geo_nodes', cislunar: 'cislunar_nodes',
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
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', minHeight: 0 }}>
        {[...DV_NODES].reverse().map((node, reversedIdx) => {
          const nodeIdx = DV_NODES.length - 1 - reversedIdx
          const edge = DV_EDGES[nodeIdx - 1]
          const shell = node.shell
          const assetKey = shell ? NODE_KEY_MAP[shell] : null
          const open = shell ? (gameState.access_windows?.[shell] ?? true) : true
          const debris = shell ? (gameState.debris_fields?.[shell] ?? 0) : 0
          const kessler = debris >= 0.8
          const isSelected = shell && selectedShell === shell
          const nodeColor = kessler ? '#ef4444' : isSelected ? '#00d4ff' : 'rgba(0,212,255,0.6)'
          const dimmed = selectedShell !== null && !isSelected && shell !== null

          const totalNodes = assetKey
            ? factions.reduce((sum, [, fs]) => sum + (fs.assets[assetKey] ?? 0), 0)
            : 0

          return (
            <div key={node.id}>
              {edge && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '2px 0' }}>
                  <div style={{ width: 2, height: 20, background: dvColor(edge.dv), marginLeft: 20, flexShrink: 0 }} />
                  <span style={{
                    fontFamily: 'Courier New', fontSize: 8,
                    color: kessler ? '#ef4444' : dvColor(edge.dv),
                    letterSpacing: 1,
                  }}>
                    {kessler ? 'KESSLER — BLOCKED' : edge.label}
                  </span>
                </div>
              )}

              <div
                onClick={() => shell && onShellClick(selectedShell === shell ? null : shell)}
                style={{
                  border: `1px solid ${isSelected ? '#00d4ff' : 'rgba(0,212,255,0.2)'}`,
                  borderRadius: 3, padding: '5px 8px', cursor: shell ? 'pointer' : 'default',
                  background: isSelected ? 'rgba(0,212,255,0.08)' : 'transparent',
                  opacity: dimmed ? 0.35 : 1,
                  boxShadow: open && shell ? `0 0 6px rgba(0,212,255,0.1)` : 'none',
                }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontFamily: 'Courier New', fontSize: 9, color: nodeColor, letterSpacing: 1 }}>
                    {node.icon} {node.label}
                  </span>
                  {node.id === 'cis' && (
                    <span style={{ fontFamily: 'Courier New', fontSize: 7, color: '#334155' }}>
                      4 sub-positions: L1·L2·L4·L5
                    </span>
                  )}
                  {kessler && (
                    <span style={{ fontFamily: 'Courier New', fontSize: 7, color: '#ef4444', letterSpacing: 1 }}>
                      KESSLER
                    </span>
                  )}
                </div>

                {assetKey && totalNodes > 0 && (
                  <div style={{ display: 'flex', height: 4, borderRadius: 2, overflow: 'hidden', marginTop: 4 }}>
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
            </div>
          )
        })}
      </div>
    </div>
  )
}
