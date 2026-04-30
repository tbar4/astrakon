import type {
  ScenarioSummary, ScenarioDetail, SessionSummary, AgentConfig, GameStateResponse, Recommendation, Phase
} from '../types'

const BASE = '/api'

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export async function listScenarios(): Promise<ScenarioSummary[]> {
  return json(await fetch(`${BASE}/scenarios`))
}

export async function listSessions(): Promise<SessionSummary[]> {
  return json(await fetch(`${BASE}/sessions`))
}

export async function createGame(
  scenarioId: string,
  agentConfig: AgentConfig[],
): Promise<GameStateResponse> {
  return json(
    await fetch(`${BASE}/game/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: scenarioId, agent_config: agentConfig }),
    }),
  )
}

export async function getState(sessionId: string): Promise<GameStateResponse> {
  return json(await fetch(`${BASE}/game/${sessionId}/state`))
}

export async function advance(sessionId: string): Promise<GameStateResponse> {
  return json(
    await fetch(`${BASE}/game/${sessionId}/advance`, { method: 'POST' }),
  )
}

export async function decide(
  sessionId: string,
  phase: string,
  decision: Record<string, unknown>,
): Promise<GameStateResponse> {
  return json(
    await fetch(`${BASE}/game/${sessionId}/decide`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phase, decision }),
    }),
  )
}

export async function getRecommendation(
  sessionId: string,
  phase: Phase,
): Promise<Recommendation | null> {
  const res = await fetch(`${BASE}/game/${sessionId}/recommend?phase=${phase}`)
  const body = await json<{ recommendation: Recommendation | null }>(res)
  return body.recommendation
}

export async function getResult(sessionId: string): Promise<unknown> {
  return json(await fetch(`${BASE}/game/${sessionId}/result`))
}

export interface HistoryData {
  decisions: Array<{ id: number; turn: number; phase: string; faction_id: string; decision_json: string; rationale: string; timestamp: string }>
  events: Array<{ id: number; turn: number; event_type: string; description: string; triggered_by: string; affected_factions: string; severity: number; timestamp: string }>
  divergences: Array<{ id: number; turn: number; phase: string; faction_id: string; recommendation_json: string; final_decision_json: string; timestamp: string }>
  token_summary: Array<{ faction_id: string; role: string; model: string; input_tokens: number; output_tokens: number; cache_read_tokens: number; cache_creation_tokens: number }>
}

export async function getHistory(sessionId: string): Promise<HistoryData> {
  return json(await fetch(`${BASE}/game/${sessionId}/history`))
}

export async function getScenario(scenarioId: string): Promise<ScenarioDetail> {
  return json(await fetch(`${BASE}/scenarios/${scenarioId}`))
}

export async function createScenario(detail: ScenarioDetail): Promise<{ scenario_id: string }> {
  return json(await fetch(`${BASE}/scenarios`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: detail.name,
      description: detail.description,
      turns: detail.turns,
      turn_represents: detail.turn_represents,
      coalitions: detail.coalitions,
      factions: detail.factions,
      victory: detail.victory,
      crisis_events_library: detail.crisis_events?.library ?? 'default_2030',
    }),
  }))
}

export async function updateScenario(scenarioId: string, detail: ScenarioDetail): Promise<{ scenario_id: string }> {
  return json(await fetch(`${BASE}/scenarios/${scenarioId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: detail.name,
      description: detail.description,
      turns: detail.turns,
      turn_represents: detail.turn_represents,
      coalitions: detail.coalitions,
      factions: detail.factions,
      victory: detail.victory,
      crisis_events_library: detail.crisis_events?.library ?? 'default_2030',
    }),
  }))
}

export async function deleteScenario(scenarioId: string): Promise<void> {
  const res = await fetch(`${BASE}/scenarios/${scenarioId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
}

export interface AarResult {
  text: string
  cached: boolean
  focus: string
  usage?: { input_tokens: number; output_tokens: number; cache_read_tokens: number; cache_creation_tokens: number }
}

export interface SavedAar {
  focus: string
  text: string
  created_at: string
}

export async function generateAar(sessionId: string, focus = '', force = false): Promise<AarResult> {
  return json(
    await fetch(`${BASE}/game/${sessionId}/aar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ focus, force }),
    }),
  )
}

export async function listAars(sessionId: string): Promise<SavedAar[]> {
  return json(await fetch(`${BASE}/game/${sessionId}/aars`))
}
