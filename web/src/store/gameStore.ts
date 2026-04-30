import { create } from 'zustand'
import type { GameState, FactionState, Recommendation } from '../types'

interface GameStore {
  sessionId: string | null
  gameState: GameState | null
  prevFactionStates: Record<string, FactionState> | null
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
  coalitionDominance: {},
  recommendation: null,
  isLoading: false,
  error: null,
  showSummary: false,

  setSession: (sessionId, state, dominance) =>
    set({ sessionId, gameState: state, prevFactionStates: null, coalitionDominance: dominance }),

  setGameState: (state, dominance) =>
    set((prev) => ({
      // Only snapshot on turn boundary — phase transitions within a turn don't count
      prevFactionStates: state.turn > (prev.gameState?.turn ?? 0)
        ? prev.gameState?.faction_states ?? null
        : prev.prevFactionStates,
      gameState: state,
      coalitionDominance: dominance,
    })),

  setRecommendation: (rec) => set({ recommendation: rec }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setShowSummary: (show) => set({ showSummary: show }),
  reset: () => set({
    sessionId: null, gameState: null, prevFactionStates: null, coalitionDominance: {},
    recommendation: null, isLoading: false, error: null, showSummary: false,
  }),
}))
