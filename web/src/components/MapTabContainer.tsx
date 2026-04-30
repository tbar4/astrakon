// web/src/components/MapTabContainer.tsx
import { useState } from 'react'
import type { GameState, FactionState } from '../types'
import type { TurnSnapshot } from '../store/gameStore'
import DominanceStrip from './DominanceStrip'
import OpsTab from './OpsTab'
import AARPanel from './AARPanel'

type Tab = 'orbital' | 'deltav' | 'ops' | 'aar'

interface Props {
  gameState: GameState
  coalitionDominance: Record<string, number>
  turnHistory: TurnSnapshot[]
  prevFactionStates: Record<string, FactionState> | null
  humanAdversaryEstimates: Record<string, {
    leo_nodes: number; meo_nodes: number; geo_nodes: number;
    cislunar_nodes: number; asat_kinetic: number; asat_deniable: number;
    ew_jammers: number; sda_sensors: number; relay_nodes: number; launch_capacity: number
  }>
}

const TAB_LABELS: { id: Tab; label: string }[] = [
  { id: 'orbital', label: 'ORBITAL' },
  { id: 'deltav',  label: 'DELTA-V' },
  { id: 'ops',     label: 'OPS' },
  { id: 'aar',     label: 'AAR' },
]

export default function MapTabContainer({
  gameState, coalitionDominance, turnHistory, prevFactionStates, humanAdversaryEstimates,
}: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('orbital')
  const [selectedShell, setSelectedShell] = useState<string | null>(null)
  const [selectedFaction, setSelectedFaction] = useState<string | null>(null)

  // selectedShell, selectedFaction, setSelectedShell, setSelectedFaction will be wired to child components in later tasks
  void selectedShell
  void setSelectedShell
  void selectedFaction
  void setSelectedFaction
  void prevFactionStates
  void humanAdversaryEstimates

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Tab bar */}
      <div style={{
        display: 'flex', flexShrink: 0,
        borderBottom: '1px solid #00d4ff22', background: '#020b18',
      }}>
        {TAB_LABELS.map(({ id, label }) => (
          <button key={id} onClick={() => setActiveTab(id)} style={{
            fontFamily: 'Courier New', fontSize: 10, letterSpacing: 2,
            padding: '5px 14px', border: 'none', cursor: 'pointer',
            borderBottom: activeTab === id ? '2px solid #00d4ff' : '2px solid transparent',
            color: activeTab === id ? '#00d4ff' : '#334155',
            background: 'none',
          }}>
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {activeTab === 'orbital' && (
          <div className="panel" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontFamily: 'Courier New', fontSize: 10, color: '#334155' }}>
              ORBITAL MAP — LOADING
            </span>
          </div>
        )}
        {activeTab === 'deltav' && (
          <div className="panel" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontFamily: 'Courier New', fontSize: 10, color: '#334155' }}>
              DELTA-V GRAPH — LOADING
            </span>
          </div>
        )}
        {activeTab === 'ops' && (
          <OpsTab
            gameState={gameState}
            coalitionDominance={coalitionDominance}
            turnHistory={turnHistory}
          />
        )}
        {activeTab === 'aar' && (
          <AARPanel
            gameState={gameState}
            coalitionDominance={coalitionDominance}
            turnHistory={turnHistory}
          />
        )}
      </div>

      {/* Persistent dominance strip */}
      <DominanceStrip
        coalitionDominance={coalitionDominance}
        turnHistory={turnHistory}
        coalitionColors={gameState.coalition_colors}
        victoryThreshold={gameState.victory_threshold}
      />
    </div>
  )
}
