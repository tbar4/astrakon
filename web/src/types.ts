export type Phase = 'invest' | 'operations' | 'response'

export interface FactionAssets {
  leo_nodes: number
  meo_nodes: number
  geo_nodes: number
  cislunar_nodes: number
  asat_kinetic: number
  asat_deniable: number
  ew_jammers: number
  sda_sensors: number
  launch_capacity: number
}

export interface FactionState {
  faction_id: string
  name: string
  budget_per_turn: number
  current_budget: number
  assets: FactionAssets
  coalition_id: string | null
  coalition_loyalty: number
  deferred_returns: Array<{ turn_due: number; category: string; amount: number }>
  deterrence_score: number
  disruption_score: number
  market_share: number
  joint_force_effectiveness: number
}

export interface CoalitionState {
  coalition_id: string
  member_ids: string[]
  hegemony_score: number
}

export interface AdversaryEstimate {
  leo_nodes: number
  meo_nodes: number
  geo_nodes: number
  cislunar_nodes: number
  asat_kinetic: number
}

export interface GameStateSnapshot {
  turn: number
  phase: Phase
  faction_id: string
  faction_state: FactionState
  ally_states: Record<string, FactionState>
  adversary_estimates: Record<string, AdversaryEstimate>
  coalition_states: Record<string, CoalitionState>
  available_actions: string[]
  turn_log_summary: string
  tension_level: number
  debris_level: number
  joint_force_effectiveness: number
  incoming_threats: Array<{ attacker: string; declared_turn: number }>
  faction_names: Record<string, string>
}

export interface GameState {
  session_id: string
  scenario_id: string
  scenario_name: string
  turn: number
  total_turns: number
  current_phase: Phase | 'game_over'
  phase_decisions: Record<string, string>
  faction_states: Record<string, FactionState>
  coalition_states: Record<string, CoalitionState>
  tension_level: number
  debris_level: number
  turn_log: string[]
  events: Array<{
    event_id: string
    event_type: string
    description: string
    severity: number
    affected_factions: string[]
  }>
  human_faction_id: string
  human_snapshot: GameStateSnapshot | null
  use_advisor: boolean
  game_over: boolean
  awaiting_next_turn: boolean
  result: {
    turns_completed: number
    winner_coalition: string | null
    final_dominance: Record<string, number>
  } | null
  error: string | null
  victory_threshold: number
  coalition_colors: Record<string, string>
}

export interface GameStateResponse {
  state: GameState
  coalition_dominance: Record<string, number>
}

export interface ScenarioFaction {
  faction_id: string
  name: string
  archetype: string
  agent_type: string
}

export interface ScenarioSummary {
  id: string
  name: string
  description: string
  turns: number
  factions: ScenarioFaction[]
}

export interface AgentConfig {
  faction_id: string
  agent_type: 'web' | 'rule_based' | 'ai_commander'
  use_advisor: boolean
}

export interface InvestmentDecision {
  investment: {
    r_and_d?: number
    constellation?: number
    meo_deployment?: number
    geo_deployment?: number
    cislunar_deployment?: number
    launch_capacity?: number
    commercial?: number
    influence_ops?: number
    education?: number
    covert?: number
    diplomacy?: number
    rationale: string
  }
}

export interface OperationsDecision {
  operations: Array<{
    action_type: string
    target_faction?: string
    parameters?: Record<string, string>
    rationale: string
  }>
}

export interface ResponseDecision {
  response: {
    escalate: boolean
    retaliate: boolean
    target_faction?: string
    public_statement: string
    rationale: string
  }
}

export interface Recommendation {
  phase: Phase
  strategic_rationale: string
  top_recommendation: {
    investment?: InvestmentDecision['investment']
    operations?: OperationsDecision['operations']
    response?: ResponseDecision['response']
  }
}
