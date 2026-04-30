import type {
  ScenarioSummary, SessionSummary, AgentConfig, GameStateResponse, Recommendation, Phase
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

export async function generateAar(sessionId: string): Promise<string> {
  const body = await json<{ text: string }>(
    await fetch(`${BASE}/game/${sessionId}/aar`, { method: 'POST' }),
  )
  return body.text
}
