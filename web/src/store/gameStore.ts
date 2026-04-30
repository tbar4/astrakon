import { create } from 'zustand'
import type { GameState, FactionState, FactionAssets, Recommendation } from '../types'

type AssetKey = keyof FactionAssets

const ASSET_KEYS: AssetKey[] = [
  'leo_nodes', 'meo_nodes', 'geo_nodes', 'cislunar_nodes',
  'asat_kinetic', 'asat_deniable', 'ew_jammers', 'sda_sensors', 'launch_capacity',
]

export interface TurnSnapshot {
  turn: number
  dominance: Record<string, number>
  tension: number
}

interface GameStore {
  sessionId: string | null
  gameState: GameState | null
  prevFactionStates: Record<string, FactionState> | null
  cumulativeAdded: Partial<Record<AssetKey, number>>
  cumulativeDestroyed: Partial<Record<AssetKey, number>>
  turnHistory: TurnSnapshot[]
  coalitionDominance: Record<string, number>
  recommendation: Recommendation | null
  isLoading: boolean
  error: string | null
  showSummary: boolean

  setSession: (sessionId: string, state: GameState, dominance: Record<string, number>) => void
  setGameState: (state: GameState, dominance: Record<string, number>) => void
  setRecommendation: (rec: Recommendation | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setShowSummary: (show: boolean) => void
  reset: () => void
}

export const useGameStore = create<GameStore>((set) => ({
  sessionId: null,
  gameState: null,
  prevFactionStates: null,
  cumulativeAdded: {},
  cumulativeDestroyed: {},
  turnHistory: [],
  coalitionDominance: {},
  recommendation: null,
  isLoading: false,
  error: null,
  showSummary: false,

  setSession: (sessionId, state, dominance) =>
    set({ sessionId, gameState: state, prevFactionStates: null, cumulativeAdded: {}, cumulativeDestroyed: {}, turnHistory: [], coalitionDominance: dominance }),

  setGameState: (state, dominance) =>
    set((prev) => {
      const isTurnBoundary = state.turn > (prev.gameState?.turn ?? 0)

      let cumulativeAdded = prev.cumulativeAdded
      let cumulativeDestroyed = prev.cumulativeDestroyed
      let turnHistory = prev.turnHistory

      if (isTurnBoundary && prev.gameState) {
        // Snapshot the completed turn before overwriting
        turnHistory = [
          ...turnHistory,
          { turn: prev.gameState.turn, dominance: prev.coalitionDominance, tension: prev.gameState.tension_level },
        ]

        const humanId = prev.gameState.human_faction_id
        const prevFs = prev.gameState.faction_states[humanId]
        const currFs = state.faction_states[humanId]
        if (prevFs && currFs) {
          cumulativeAdded = { ...cumulativeAdded }
          cumulativeDestroyed = { ...cumulativeDestroyed }
          for (const key of ASSET_KEYS) {
            const diff = currFs.assets[key] - prevFs.assets[key]
            if (diff > 0) cumulativeAdded[key] = (cumulativeAdded[key] ?? 0) + diff
            else if (diff < 0) cumulativeDestroyed[key] = (cumulativeDestroyed[key] ?? 0) + Math.abs(diff)
          }
        }
      }

      return {
        prevFactionStates: isTurnBoundary ? prev.gameState?.faction_states ?? null : prev.prevFactionStates,
        gameState: state,
        coalitionDominance: dominance,
        cumulativeAdded,
        cumulativeDestroyed,
        turnHistory,
      }
    }),

  setRecommendation: (rec) => set({ recommendation: rec }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setShowSummary: (show) => set({ showSummary: show }),
  reset: () => set({
    sessionId: null, gameState: null, prevFactionStates: null,
    cumulativeAdded: {}, cumulativeDestroyed: {}, turnHistory: [],
    coalitionDominance: {}, recommendation: null, isLoading: false, error: null, showSummary: false,
  }),
}))
