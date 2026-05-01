// web/src/components/MapTabContainer.tsx
import { useState } from 'react'
import type { GameState, FactionState, FactionAssets, CombatEvent } from '../types'
import type { TurnSnapshot } from '../store/gameStore'
import DominanceStrip from './DominanceStrip'
import OpsTab from './OpsTab'
import HoloOrbitalMap from './HoloOrbitalMap'
import DeltaVGraph from './DeltaVGraph'
import TrendsTab from './TrendsTab'
import TechTreePanel from './TechTreePanel'
import ForecastTab from './ForecastTab'
import type { OperationForecast } from '../types'

type Tab = 'orbital' | 'deltav' | 'ops' | 'trends' | 'log' | 'tech' | 'forecast'

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
  factionState: FactionState
  turn: number
  totalTurns: number
  tensionLevel: number
  cumulativeAdded: Partial<Record<keyof FactionAssets, number>>
  cumulativeDestroyed: Partial<Record<keyof FactionAssets, number>>
  isJammed: boolean
  targetingMode?: boolean
  lockedFaction?: string | null
  onFactionClick?: (factionId: string) => void
  pendingTechUnlocks?: string[]
  onQueueTech?: (id: string) => void
  rdPoints?: number
  combatEvents?: CombatEvent[]
  arcOpacity?: number
  forecasts?: OperationForecast[]
}

const TAB_LABELS: { id: Tab; label: string }[] = [
  { id: 'orbital', label: 'ORBITAL' },
  { id: 'deltav',  label: 'DELTA-V' },
  { id: 'ops',     label: 'OPS' },
  { id: 'trends',  label: 'TRENDS' },
  { id: 'log',     label: 'LOG' },
  { id: 'tech',    label: 'TECH' },
  { id: 'forecast', label: 'FORECAST' },
]

export default function MapTabContainer({
  gameState, coalitionDominance, turnHistory, prevFactionStates, humanAdversaryEstimates,
  factionState, turn, totalTurns, tensionLevel, cumulativeAdded, cumulativeDestroyed, isJammed,
  targetingMode, lockedFaction, onFactionClick,
  pendingTechUnlocks = [], onQueueTech = () => {}, rdPoints = 0,
  combatEvents, arcOpacity, forecasts = [],
}: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('orbital')
  const [selectedShell, setSelectedShell] = useState<string | null>(null)
  const [selectedFaction, setSelectedFaction] = useState<string | null>(null)

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Tab bar */}
      <div style={{
        display: 'flex', flexShrink: 0,
        borderBottom: '1px solid #00d4ff22', background: '#020b18',
      }}>
        {TAB_LABELS.map(({ id, label }) => (
          <button key={id} onClick={() => setActiveTab(id)} style={{
            fontFamily: 'Courier New', fontSize: 12, letterSpacing: 2,
            padding: '5px 14px', border: 'none', cursor: 'pointer',
            borderBottom: activeTab === id ? '2px solid #00d4ff' : '2px solid transparent',
            color: activeTab === id ? '#00d4ff' : '#64748b',
            background: 'none',
          }}>
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {activeTab === 'orbital' && (
          <HoloOrbitalMap
            gameState={gameState}
            prevFactionStates={prevFactionStates}
            humanAdversaryEstimates={humanAdversaryEstimates}
            selectedShell={selectedShell}
            selectedFaction={selectedFaction}
            onShellHover={setSelectedShell}
            onFactionHover={setSelectedFaction}
            targetingMode={targetingMode}
            lockedFaction={lockedFaction}
            onFactionClick={onFactionClick}
            combatEvents={combatEvents}
            arcOpacity={arcOpacity}
          />
        )}
        {activeTab === 'deltav' && (
          <DeltaVGraph
            gameState={gameState}
            coalitionDominance={coalitionDominance}
            selectedShell={selectedShell}
            selectedFaction={selectedFaction}
            onShellClick={setSelectedShell}
            onFactionClick={setSelectedFaction}
          />
        )}
        {activeTab === 'ops' && (
          <OpsTab
            gameState={gameState}
            coalitionDominance={coalitionDominance}
            turnHistory={turnHistory}
            factionState={factionState}
            turn={turn}
            totalTurns={totalTurns}
            tensionLevel={tensionLevel}
            cumulativeAdded={cumulativeAdded}
            cumulativeDestroyed={cumulativeDestroyed}
            isJammed={isJammed}
          />
        )}
        {activeTab === 'trends' && (
          <TrendsTab
            gameState={gameState}
            turnHistory={turnHistory}
          />
        )}
        {activeTab === 'log' && (
          <div style={{ height: '100%', overflowY: 'auto', padding: '10px 14px' }}>
            {gameState.turn_log.length === 0 ? (
              <div className="mono" style={{ color: '#475569', fontSize: 10, textAlign: 'center', marginTop: 40, letterSpacing: 2 }}>
                NO LOG ENTRIES THIS TURN
              </div>
            ) : (
              gameState.turn_log.map((entry, i) => (
                <div key={i} style={{
                  fontFamily: 'Courier New', fontSize: 12, color: '#94a3b8',
                  lineHeight: 1.7, padding: '4px 0',
                  borderBottom: i < gameState.turn_log.length - 1 ? '1px solid #00d4ff0f' : 'none',
                }}>
                  <span style={{ color: '#475569', marginRight: 10, userSelect: 'none' }}>
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span style={{
                    color: entry.startsWith('[') ? '#00d4ff' : '#94a3b8',
                  }}>{entry}</span>
                </div>
              ))
            )}
          </div>
        )}
        {activeTab === 'tech' && (
          <TechTreePanel
            gameState={gameState}
            factionState={gameState.faction_states[gameState.human_faction_id]}
            currentPhase={gameState.current_phase as string}
            rdPoints={rdPoints}
            pendingUnlocks={pendingTechUnlocks}
            onQueueToggle={onQueueTech}
          />
        )}
        {activeTab === 'forecast' && (
          <ForecastTab
            forecasts={forecasts}
            factionNames={Object.fromEntries(
              Object.entries(gameState.faction_states).map(([fid, fs]) => [fid, fs.name])
            )}
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
