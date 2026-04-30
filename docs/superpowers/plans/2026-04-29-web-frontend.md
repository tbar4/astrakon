# Astrakon Web Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Vite + React SPA that drives the Astrakon game through a sci-fi command-center interface with a live orbital map, per-phase decision panels, and a turn summary overlay.

**Architecture:** Single-page app with React Router (3 routes: Setup, Game, Result). Zustand manages game state. All server communication goes through typed fetch wrappers in `api/client.ts`. The backend API must be running at `http://localhost:8000` (from the backend plan).

**Tech Stack:** Vite 5, React 19, TypeScript 5, React Router v7, Zustand 5, Tailwind CSS v4.

**Prerequisite:** Complete `2026-04-29-web-backend.md` first. The frontend calls `http://localhost:8000/api/*`.

---

## File Map

| File | Purpose |
|------|---------|
| `web/package.json` | Node deps |
| `web/vite.config.ts` | Vite + proxy config (dev: proxy /api to :8000) |
| `web/tsconfig.json` | TypeScript config |
| `web/tailwind.config.ts` | Tailwind dark theme |
| `web/index.html` | Entry HTML |
| `web/src/main.tsx` | React root mount |
| `web/src/App.tsx` | React Router setup |
| `web/src/types.ts` | TypeScript types matching backend Pydantic models |
| `web/src/api/client.ts` | Typed fetch wrappers for all 8 endpoints |
| `web/src/store/gameStore.ts` | Zustand store |
| `web/src/pages/SetupPage.tsx` | Scenario selection + agent config |
| `web/src/pages/GamePage.tsx` | Main command center (3-column layout) |
| `web/src/pages/ResultPage.tsx` | Winner display + AAR |
| `web/src/components/OrbitalMap.tsx` | SVG orbital visualization |
| `web/src/components/FactionSidebar.tsx` | Assets, budget, deferred returns, metrics |
| `web/src/components/DominanceRail.tsx` | Coalition dominance bars + event feed |
| `web/src/components/TurnSummary.tsx` | End-of-turn overlay |
| `web/src/components/LoadingOverlay.tsx` | Full-screen scanner overlay during requests |
| `web/src/components/AdvisorPanel.tsx` | AI recommendation panel |
| `web/src/components/phase/InvestPanel.tsx` | Budget allocation UI |
| `web/src/components/phase/OpsPanel.tsx` | Operation selection UI |
| `web/src/components/phase/ResponsePanel.tsx` | Escalation/response UI |

---

## Task 1: Project scaffold

**Files:**
- Create: `web/package.json`
- Create: `web/vite.config.ts`
- Create: `web/tsconfig.json`
- Create: `web/tailwind.config.ts`
- Create: `web/index.html`

- [ ] **Step 1: Create `web/package.json`**

```json
{
  "name": "astrakon-web",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.0.0",
    "zustand": "^5.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/vite": "^4.0.0",
    "typescript": "^5.7.0",
    "vite": "^6.0.0"
  }
}
```

- [ ] **Step 2: Create `web/vite.config.ts`**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    outDir: '../web/dist',
  },
})
```

- [ ] **Step 3: Create `web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create `web/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>ASTRAKON</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Install dependencies**

```bash
cd /Users/tbarnes/projects/agents/web && npm install
```

Expected: `added N packages` with no errors.

- [ ] **Step 6: Verify dev server starts**

```bash
cd /Users/tbarnes/projects/agents/web && npm run dev
```

Expected: `VITE v6.x.x ready in Xms` and `Local: http://localhost:5173/`

Stop with Ctrl+C.

- [ ] **Step 7: Commit**

```bash
cd /Users/tbarnes/projects/agents
git add web/package.json web/package-lock.json web/vite.config.ts web/tsconfig.json web/index.html
git commit -m "feat: scaffold Vite + React + Tailwind frontend"
```

---

## Task 2: TypeScript types and API client

**Files:**
- Create: `web/src/types.ts`
- Create: `web/src/api/client.ts`

- [ ] **Step 1: Create `web/src/types.ts`**

```typescript
// web/src/types.ts

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
  coalition_dominance: Record<string, float>
}

// Fix TypeScript — 'float' doesn't exist in TS, use number
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
```

- [ ] **Step 2: Create `web/src/api/client.ts`**

```typescript
// web/src/api/client.ts
import type {
  ScenarioSummary, AgentConfig, GameStateResponse, Recommendation, Phase
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

export async function generateAar(sessionId: string): Promise<string> {
  const body = await json<{ text: string }>(
    await fetch(`${BASE}/game/${sessionId}/aar`, { method: 'POST' }),
  )
  return body.text
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
cd /Users/tbarnes/projects/agents
git add web/src/types.ts web/src/api/client.ts
git commit -m "feat: add TypeScript types and API client"
```

---

## Task 3: Zustand store and App routing

**Files:**
- Create: `web/src/store/gameStore.ts`
- Create: `web/src/main.tsx`
- Create: `web/src/App.tsx`
- Create: `web/src/index.css`

- [ ] **Step 1: Create `web/src/index.css`** (global Tailwind + sci-fi base styles)

```css
@import "tailwindcss";

:root {
  --color-bg: #020b18;
  --color-accent: #00d4ff;
  --color-green: #00ff88;
  --color-red: #ff4499;
  --color-border: rgba(0, 212, 255, 0.2);
}

body {
  background-color: var(--color-bg);
  color: #94a3b8;
  font-family: system-ui, sans-serif;
  margin: 0;
}

.mono { font-family: 'Courier New', monospace; }

.glow-cyan { box-shadow: 0 0 8px rgba(0, 212, 255, 0.4); }
.glow-green { box-shadow: 0 0 8px rgba(0, 255, 136, 0.4); }
.glow-red   { box-shadow: 0 0 8px rgba(255, 68, 153, 0.4); }

.panel {
  background: rgba(2, 11, 24, 0.9);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 12px;
}

.panel-title {
  font-family: 'Courier New', monospace;
  font-size: 10px;
  letter-spacing: 3px;
  color: var(--color-accent);
  text-transform: uppercase;
  margin-bottom: 10px;
}

.btn-primary {
  background: rgba(0, 212, 255, 0.15);
  border: 1px solid var(--color-accent);
  color: var(--color-accent);
  padding: 8px 20px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  letter-spacing: 2px;
  cursor: pointer;
  border-radius: 2px;
  transition: background 0.2s;
}

.btn-primary:hover {
  background: rgba(0, 212, 255, 0.25);
}

.btn-primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
```

- [ ] **Step 2: Create `web/src/store/gameStore.ts`**

```typescript
// web/src/store/gameStore.ts
import { create } from 'zustand'
import type { GameState, Recommendation, Phase } from '../types'

interface GameStore {
  sessionId: string | null
  gameState: GameState | null
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
  coalitionDominance: {},
  recommendation: null,
  isLoading: false,
  error: null,
  showSummary: false,

  setSession: (sessionId, state, dominance) =>
    set({ sessionId, gameState: state, coalitionDominance: dominance }),

  setGameState: (state, dominance) =>
    set({ gameState: state, coalitionDominance: dominance }),

  setRecommendation: (rec) => set({ recommendation: rec }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setShowSummary: (show) => set({ showSummary: show }),
  reset: () => set({
    sessionId: null, gameState: null, coalitionDominance: {},
    recommendation: null, isLoading: false, error: null, showSummary: false,
  }),
}))
```

- [ ] **Step 3: Create `web/src/main.tsx`**

```typescript
// web/src/main.tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 4: Create `web/src/App.tsx`**

```typescript
// web/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import SetupPage from './pages/SetupPage'
import GamePage from './pages/GamePage'
import ResultPage from './pages/ResultPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<SetupPage />} />
        <Route path="/game/:sessionId" element={<GamePage />} />
        <Route path="/result/:sessionId" element={<ResultPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 6: Commit**

```bash
cd /Users/tbarnes/projects/agents
git add web/src/
git commit -m "feat: add Zustand store and React Router app shell"
```

---

## Task 4: SetupPage

**Files:**
- Create: `web/src/pages/SetupPage.tsx`

- [ ] **Step 1: Create `web/src/pages/SetupPage.tsx`**

```typescript
// web/src/pages/SetupPage.tsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { listScenarios, createGame, advance } from '../api/client'
import { useGameStore } from '../store/gameStore'
import type { ScenarioSummary, AgentConfig } from '../types'

export default function SetupPage() {
  const navigate = useNavigate()
  const { setSession, setGameState, setLoading, isLoading } = useGameStore()
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [agentConfig, setAgentConfig] = useState<AgentConfig[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listScenarios().then((s) => {
      setScenarios(s)
      if (s.length > 0) {
        setSelectedId(s[0].id)
        initConfig(s[0])
      }
    }).catch(() => setError('Failed to load scenarios — is the API server running?'))
  }, [])

  function initConfig(scenario: ScenarioSummary) {
    const config: AgentConfig[] = scenario.factions.map((f, i) => ({
      faction_id: f.faction_id,
      agent_type: i === 0 ? 'web' : 'rule_based',
      use_advisor: false,
    }))
    setAgentConfig(config)
  }

  function handleScenarioChange(id: string) {
    setSelectedId(id)
    const s = scenarios.find((s) => s.id === id)
    if (s) initConfig(s)
  }

  function setAgentType(factionId: string, type: AgentConfig['agent_type']) {
    setAgentConfig((prev) =>
      prev.map((c) => c.faction_id === factionId ? { ...c, agent_type: type } : c)
    )
  }

  function setUseAdvisor(factionId: string, use: boolean) {
    setAgentConfig((prev) =>
      prev.map((c) => c.faction_id === factionId ? { ...c, use_advisor: use } : c)
    )
  }

  async function handleStart() {
    if (!selectedId || agentConfig.filter((c) => c.agent_type === 'web').length !== 1) {
      setError('Exactly one faction must be set to "Human (web)"')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const created = await createGame(selectedId, agentConfig)
      setSession(created.state.session_id, created.state, created.coalition_dominance)
      const advanced = await advance(created.state.session_id)
      setGameState(advanced.state, advanced.coalition_dominance)
      navigate(`/game/${created.state.session_id}`)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  const selected = scenarios.find((s) => s.id === selectedId)

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 40 }}>
      <div style={{ marginBottom: 32, textAlign: 'center' }}>
        <div className="mono" style={{ fontSize: 28, color: '#00d4ff', letterSpacing: 8 }}>◆ ASTRAKON ◆</div>
        <div className="mono" style={{ fontSize: 11, color: '#00d4ff66', letterSpacing: 3, marginTop: 6 }}>ORBITAL STRATEGY SIMULATION</div>
      </div>

      {error && (
        <div className="panel" style={{ borderColor: '#ff4499', color: '#ff4499', marginBottom: 20, fontSize: 12 }}>
          {error}
        </div>
      )}

      <div className="panel" style={{ width: '100%', maxWidth: 600 }}>
        <div className="panel-title">SELECT SCENARIO</div>
        <select
          value={selectedId}
          onChange={(e) => handleScenarioChange(e.target.value)}
          style={{
            width: '100%', background: '#020b18', border: '1px solid #00d4ff33',
            color: '#94a3b8', padding: '8px 12px', fontFamily: 'Courier New',
            fontSize: 12, marginBottom: 8, borderRadius: 2,
          }}
        >
          {scenarios.map((s) => (
            <option key={s.id} value={s.id}>{s.name} ({s.turns} turns)</option>
          ))}
        </select>
        {selected && (
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 20 }}>{selected.description}</div>
        )}

        {selected && (
          <>
            <div className="panel-title" style={{ marginTop: 16 }}>CONFIGURE FACTIONS</div>
            {selected.factions.map((f) => {
              const cfg = agentConfig.find((c) => c.faction_id === f.faction_id)
              if (!cfg) return null
              return (
                <div key={f.faction_id} style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '8px 0', borderBottom: '1px solid #00d4ff11',
                }}>
                  <div style={{ flex: 1, fontSize: 12, color: '#e2e8f0' }}>{f.name}</div>
                  <select
                    value={cfg.agent_type}
                    onChange={(e) => setAgentType(f.faction_id, e.target.value as AgentConfig['agent_type'])}
                    style={{
                      background: '#020b18', border: '1px solid #00d4ff33',
                      color: '#94a3b8', padding: '4px 8px', fontFamily: 'Courier New',
                      fontSize: 11, borderRadius: 2,
                    }}
                  >
                    <option value="web">Human (web)</option>
                    <option value="rule_based">AI — Rule-based</option>
                    <option value="ai_commander">AI — Commander</option>
                  </select>
                  {cfg.agent_type === 'web' && (
                    <label style={{ fontSize: 11, color: '#64748b', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <input
                        type="checkbox"
                        checked={cfg.use_advisor}
                        onChange={(e) => setUseAdvisor(f.faction_id, e.target.checked)}
                      />
                      advisor
                    </label>
                  )}
                </div>
              )
            })}
          </>
        )}

        <button
          className="btn-primary"
          onClick={handleStart}
          disabled={isLoading || !selectedId}
          style={{ marginTop: 24, width: '100%' }}
        >
          {isLoading ? 'INITIALIZING...' : '[ LAUNCH SIMULATION ]'}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Start API server and dev server, navigate to http://localhost:5173**

In terminal 1:
```bash
cd /Users/tbarnes/projects/agents && python run_api.py
```

In terminal 2:
```bash
cd /Users/tbarnes/projects/agents/web && npm run dev
```

Expected: Setup page shows with scenario dropdown and faction list.

- [ ] **Step 4: Commit**

```bash
cd /Users/tbarnes/projects/agents
git add web/src/pages/SetupPage.tsx
git commit -m "feat: add SetupPage with scenario selection and agent config"
```

---

## Task 5: OrbitalMap component

**Files:**
- Create: `web/src/components/OrbitalMap.tsx`

- [ ] **Step 1: Create `web/src/components/OrbitalMap.tsx`**

```typescript
// web/src/components/OrbitalMap.tsx
import { useMemo } from 'react'
import type { GameState } from '../types'

interface Props {
  gameState: GameState
  coalitionDominance: Record<string, number>
}

const RINGS = [
  { label: 'LEO', r: 52, key: 'leo_nodes' as const },
  { label: 'MEO', r: 74, key: 'meo_nodes' as const },
  { label: 'GEO', r: 94, key: 'geo_nodes' as const },
  { label: 'CIS', r: 112, key: 'cislunar_nodes' as const },
]

const DOT_CAP = 8

function factionColor(factionId: string, gameState: GameState): string {
  if (factionId === gameState.human_faction_id) return '#00ff88'
  const coalition = Object.entries(gameState.coalition_states).find(([, cs]) =>
    cs.member_ids.includes(factionId)
  )
  if (!coalition) return '#00d4ff'
  const cid = coalition[0]
  return gameState.coalition_colors[cid] === 'green' ? '#00ff88' : '#ff4499'
}

function dotsOnRing(count: number, r: number, color: string, factionIdx: number, totalFactions: number) {
  const visible = Math.min(count, DOT_CAP)
  const angleStep = (Math.PI * 2) / Math.max(totalFactions, 1)
  const baseAngle = factionIdx * angleStep
  const spreadAngle = angleStep * 0.6
  const elements: JSX.Element[] = []

  for (let i = 0; i < visible; i++) {
    const angle = baseAngle + (visible === 1 ? 0 : (i / (visible - 1) - 0.5) * spreadAngle)
    const cx = 130 + r * Math.cos(angle)
    const cy = 130 + r * Math.sin(angle)
    elements.push(
      <circle key={i} cx={cx} cy={cy} r={3} fill={color}
        style={{ filter: `drop-shadow(0 0 3px ${color})` }} />
    )
  }

  if (count > DOT_CAP) {
    const angle = baseAngle + spreadAngle / 2 + 0.15
    const cx = 130 + r * Math.cos(angle)
    const cy = 130 + r * Math.sin(angle)
    elements.push(
      <text key="badge" x={cx} y={cy} fill={color}
        fontSize={8} fontFamily="monospace" textAnchor="middle" dominantBaseline="middle">
        ×{count}
      </text>
    )
  }
  return elements
}

export default function OrbitalMap({ gameState }: Props) {
  const factions = useMemo(() => Object.entries(gameState.faction_states), [gameState])
  const threats = gameState.human_snapshot?.incoming_threats ?? []

  return (
    <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="panel-title">◆ ORBITAL MAP</div>
      <svg viewBox="0 0 260 260" style={{ flex: 1, width: '100%' }}>
        {/* Rings */}
        {RINGS.map(({ r, label }) => (
          <g key={r}>
            <circle cx={130} cy={130} r={r} fill="none"
              stroke="rgba(0,212,255,0.12)" strokeWidth={1} />
            <text x={130 + r + 3} y={132} fill="rgba(0,212,255,0.35)"
              fontSize={7} fontFamily="monospace">{label}</text>
          </g>
        ))}

        {/* Earth */}
        <circle cx={130} cy={130} r={12} fill="#020b18" stroke="rgba(0,212,255,0.5)" strokeWidth={1.5} />
        <text x={130} y={134} fill="rgba(0,212,255,0.6)" fontSize={9}
          fontFamily="monospace" textAnchor="middle">⊕</text>

        {/* Faction nodes */}
        {RINGS.map(({ r, key }) =>
          factions.map(([fid, fs], idx) => {
            const count = fs.assets[key]
            if (count === 0) return null
            const color = factionColor(fid, gameState)
            return (
              <g key={`${r}-${fid}`}>
                {dotsOnRing(count, r, color, idx, factions.length)}
              </g>
            )
          })
        )}

        {/* Kinetic threat indicators */}
        {threats.map((t, i) => (
          <g key={i}>
            <circle cx={130} cy={130} r={RINGS[0].r}
              fill="none" stroke="rgba(255,68,153,0.6)" strokeWidth={2}
              strokeDasharray="4 4">
              <animateTransform attributeName="transform" type="rotate"
                from="0 130 130" to="360 130 130" dur="4s" repeatCount="indefinite" />
            </circle>
            <text x={130} y={50} fill="#ff4499" fontSize={8}
              fontFamily="monospace" textAnchor="middle">
              ⚠ KINETIC APPROACH
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd /Users/tbarnes/projects/agents
git add web/src/components/OrbitalMap.tsx
git commit -m "feat: add OrbitalMap SVG component with faction nodes and threat indicators"
```

---

## Task 6: FactionSidebar and DominanceRail

**Files:**
- Create: `web/src/components/FactionSidebar.tsx`
- Create: `web/src/components/DominanceRail.tsx`

- [ ] **Step 1: Create `web/src/components/FactionSidebar.tsx`**

```typescript
// web/src/components/FactionSidebar.tsx
import type { FactionState } from '../types'

interface Props {
  factionState: FactionState
  turn: number
  totalTurns: number
  tensionLevel: number
}

export default function FactionSidebar({ factionState: fs, turn, totalTurns, tensionLevel }: Props) {
  const jfe = fs.joint_force_effectiveness
  const jfeColor = jfe >= 0.8 ? '#00ff88' : jfe >= 0.5 ? '#f59e0b' : '#ff4499'

  const assets = [
    ['LEO Nodes', fs.assets.leo_nodes, '1×'],
    ['MEO Nodes', fs.assets.meo_nodes, '2×'],
    ['GEO Nodes', fs.assets.geo_nodes, '3×'],
    ['Cislunar', fs.assets.cislunar_nodes, '4×'],
    ['ASAT-K', fs.assets.asat_kinetic, '—'],
    ['ASAT-D', fs.assets.asat_deniable, '—'],
    ['EW Jammers', fs.assets.ew_jammers, '—'],
    ['SDA Sensors', fs.assets.sda_sensors, '—'],
    ['Launch Cap.', fs.assets.launch_capacity, '—'],
  ] as const

  return (
    <div className="panel" style={{ height: '100%', overflowY: 'auto' }}>
      <div className="panel-title">◆ {fs.name}</div>

      <div className="mono" style={{ fontSize: 10, color: '#64748b', marginBottom: 8 }}>
        T{turn}/{totalTurns} · TENSION {(tensionLevel * 100).toFixed(0)}%
      </div>

      <div style={{ marginBottom: 10 }}>
        {assets.map(([label, val, weight]) => (
          <div key={label} style={{
            display: 'flex', justifyContent: 'space-between',
            fontSize: 11, padding: '2px 0', borderBottom: '1px solid #00d4ff08',
          }}>
            <span style={{ color: '#64748b' }}>{label}</span>
            <span style={{ color: '#e2e8f0', fontFamily: 'Courier New' }}>{val}</span>
            <span style={{ color: '#334155', fontSize: 10 }}>{weight}</span>
          </div>
        ))}
      </div>

      <div style={{ fontSize: 11, padding: '6px 0', borderTop: '1px solid #00d4ff11' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ color: '#64748b' }}>Budget</span>
          <span style={{ color: '#00ff88', fontFamily: 'Courier New' }}>{fs.current_budget} pts</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ color: '#64748b' }}>Deterrence</span>
          <span style={{ color: '#00d4ff', fontFamily: 'Courier New' }}>{fs.deterrence_score.toFixed(0)}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
          <span style={{ color: '#64748b' }}>Mkt Share</span>
          <span style={{ color: '#00d4ff', fontFamily: 'Courier New' }}>{(fs.market_share * 100).toFixed(1)}%</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: '#64748b' }}>Joint Force</span>
          <span style={{ color: jfeColor, fontFamily: 'Courier New' }}>{(jfe * 100).toFixed(0)}%</span>
        </div>
      </div>

      {fs.deferred_returns.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div className="panel-title" style={{ fontSize: 9 }}>PENDING RETURNS</div>
          {fs.deferred_returns.map((r, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between',
              fontSize: 10, color: '#64748b', padding: '1px 0',
            }}>
              <span>{r.category === 'r_and_d' ? 'R&D' : 'Education'}</span>
              <span style={{ fontFamily: 'Courier New' }}>{r.amount} pts → T{r.turn_due}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create `web/src/components/DominanceRail.tsx`**

```typescript
// web/src/components/DominanceRail.tsx
import type { GameState } from '../types'

interface Props {
  gameState: GameState
  coalitionDominance: Record<string, number>
}

export default function DominanceRail({ gameState, coalitionDominance }: Props) {
  const { coalition_states, coalition_colors, victory_threshold, events, turn_log } = gameState

  return (
    <div className="panel" style={{ height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <div className="panel-title">◆ DOMINANCE</div>
        {Object.entries(coalition_states).map(([cid, cs]) => {
          const dom = coalitionDominance[cid] ?? 0
          const color = coalition_colors[cid] === 'green' ? '#00ff88' : '#ff4499'
          const barWidth = Math.min(100, dom * 100)
          const gap = dom - victory_threshold
          return (
            <div key={cid} style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 3 }}>
                <span className="mono" style={{ color }}>{cid}</span>
                <span className="mono" style={{ color }}>{(dom * 100).toFixed(1)}%</span>
              </div>
              <div style={{ height: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${barWidth}%`,
                  background: color, transition: 'width 0.5s',
                  boxShadow: `0 0 6px ${color}`,
                }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, marginTop: 2 }}>
                <span style={{ color: '#334155' }}>{cs.member_ids.join(', ')}</span>
                <span style={{ color: gap >= 0 ? '#00ff88' : '#ff4499' }}>
                  {gap >= 0 ? '+' : ''}{(gap * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          )
        })}
        <div style={{ fontSize: 9, color: '#334155', borderTop: '1px solid #00d4ff11', paddingTop: 6 }}>
          WIN THRESHOLD: {(victory_threshold * 100).toFixed(0)}%
        </div>
      </div>

      {events.length > 0 && (
        <div>
          <div className="panel-title" style={{ color: '#f59e0b' }}>◆ CRISIS EVENTS</div>
          {events.map((ev) => (
            <div key={ev.event_id} style={{ fontSize: 10, marginBottom: 6, padding: '4px 0', borderBottom: '1px solid #f59e0b11' }}>
              <div style={{ color: '#f59e0b', fontFamily: 'Courier New', marginBottom: 2 }}>
                {'█'.repeat(Math.round(ev.severity * 5))}{'░'.repeat(5 - Math.round(ev.severity * 5))} {ev.event_type.toUpperCase()}
              </div>
              <div style={{ color: '#64748b' }}>{ev.description}</div>
            </div>
          ))}
        </div>
      )}

      {turn_log.length > 0 && (
        <div>
          <div className="panel-title">◆ OPS LOG</div>
          {turn_log.slice(-8).map((entry, i) => {
            const color = entry.includes('[KINETIC]') || entry.includes('[RETALIATION') ? '#ff4499'
              : entry.includes('disrupted') || entry.includes('gray-zone') ? '#f59e0b'
              : '#475569'
            return (
              <div key={i} style={{ fontSize: 10, color, marginBottom: 2, fontFamily: 'Courier New' }}>
                {entry}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
cd /Users/tbarnes/projects/agents
git add web/src/components/FactionSidebar.tsx web/src/components/DominanceRail.tsx
git commit -m "feat: add FactionSidebar and DominanceRail components"
```

---

## Task 7: Phase panels

**Files:**
- Create: `web/src/components/phase/InvestPanel.tsx`
- Create: `web/src/components/phase/OpsPanel.tsx`
- Create: `web/src/components/phase/ResponsePanel.tsx`

- [ ] **Step 1: Create `web/src/components/phase/InvestPanel.tsx`**

```typescript
// web/src/components/phase/InvestPanel.tsx
import { useState } from 'react'

interface Props {
  budget: number
  onSubmit: (decision: Record<string, unknown>) => void
  disabled: boolean
}

const CATEGORIES = [
  { key: 'constellation', label: 'LEO Constellation (5 pts/node)' },
  { key: 'meo_deployment', label: 'MEO Deployment (12 pts/node, 2×)' },
  { key: 'geo_deployment', label: 'GEO Deployment (25 pts/node, 3×)' },
  { key: 'cislunar_deployment', label: 'Cislunar (40 pts/node, 4×)' },
  { key: 'r_and_d', label: 'R&D (payoff in 3 turns)' },
  { key: 'commercial', label: 'Commercial (market share)' },
  { key: 'influence_ops', label: 'Influence Ops' },
  { key: 'covert', label: 'Covert' },
  { key: 'diplomacy', label: 'Diplomacy' },
  { key: 'education', label: 'Education (payoff in 6 turns)' },
  { key: 'launch_capacity', label: 'Launch Capacity' },
] as const

type CategoryKey = typeof CATEGORIES[number]['key']

export default function InvestPanel({ budget, onSubmit, disabled }: Props) {
  const [allocs, setAllocs] = useState<Record<CategoryKey, number>>(
    Object.fromEntries(CATEGORIES.map((c) => [c.key, 0])) as Record<CategoryKey, number>
  )
  const [rationale, setRationale] = useState('')

  const total = Object.values(allocs).reduce((a, b) => a + b, 0)
  const remaining = 1.0 - total
  const isValid = total <= 1.001 && rationale.trim().length > 0

  function setAlloc(key: CategoryKey, pct: number) {
    setAllocs((prev) => ({ ...prev, [key]: Math.max(0, Math.min(1, pct)) }))
  }

  function handleSubmit() {
    onSubmit({
      investment: { ...allocs, rationale },
    })
  }

  return (
    <div>
      <div className="panel-title">◆ INVEST PHASE — BUDGET: {budget} PTS</div>
      <div className="mono" style={{ fontSize: 10, color: remaining < 0 ? '#ff4499' : '#64748b', marginBottom: 12 }}>
        ALLOCATED: {(total * 100).toFixed(0)}% · REMAINING: {(remaining * 100).toFixed(0)}%
      </div>

      {CATEGORIES.map(({ key, label }) => (
        <div key={key} style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
            <span style={{ color: '#94a3b8' }}>{label}</span>
            <span className="mono" style={{ color: '#00d4ff' }}>{(allocs[key] * 100).toFixed(0)}%</span>
          </div>
          <input
            type="range" min={0} max={100} step={5}
            value={allocs[key] * 100}
            onChange={(e) => setAlloc(key, parseInt(e.target.value) / 100)}
            style={{ width: '100%', accentColor: '#00d4ff' }}
            disabled={disabled}
          />
          <div style={{ fontSize: 10, color: '#334155' }}>
            ≈ {Math.floor(budget * allocs[key])} pts →{' '}
            {key === 'constellation' && `${Math.floor(budget * allocs[key] / 5)} LEO nodes`}
            {key === 'meo_deployment' && `${Math.floor(budget * allocs[key] / 12)} MEO nodes`}
            {key === 'geo_deployment' && `${Math.floor(budget * allocs[key] / 25)} GEO nodes`}
            {key === 'cislunar_deployment' && `${Math.floor(budget * allocs[key] / 40)} cislunar nodes`}
          </div>
        </div>
      ))}

      <div style={{ marginTop: 12 }}>
        <div className="panel-title" style={{ fontSize: 9 }}>RATIONALE</div>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Strategic rationale for this investment..."
          disabled={disabled}
          style={{
            width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
            color: '#94a3b8', padding: '6px 8px', fontFamily: 'system-ui',
            fontSize: 12, resize: 'vertical', minHeight: 60, borderRadius: 2,
            boxSizing: 'border-box',
          }}
        />
      </div>

      <button
        className="btn-primary"
        onClick={handleSubmit}
        disabled={disabled || !isValid || remaining < -0.001}
        style={{ marginTop: 12, width: '100%' }}
      >
        [ SUBMIT INVESTMENT ]
      </button>
    </div>
  )
}
```

- [ ] **Step 2: Create `web/src/components/phase/OpsPanel.tsx`**

```typescript
// web/src/components/phase/OpsPanel.tsx
import { useState } from 'react'

interface Props {
  factionNames: Record<string, string>
  humanFactionId: string
  onSubmit: (decision: Record<string, unknown>) => void
  disabled: boolean
}

const ACTION_TYPES = [
  { key: 'task_assets', label: 'Task Assets', desc: 'Surveillance, patrol, or kinetic intercept' },
  { key: 'coordinate', label: 'Coordinate', desc: 'Synchronize with coalition ally (+SDA bonus)' },
  { key: 'gray_zone', label: 'Gray Zone', desc: 'Deniable activity — ASAT-deniable or EW jamming' },
  { key: 'alliance_move', label: 'Alliance Move', desc: 'Reinforce partner or shift alignment' },
  { key: 'signal', label: 'Signal', desc: 'Deliberate public or back-channel communication' },
] as const

const MISSIONS = [
  { key: 'sda_sweep', label: 'SDA Sweep — intelligence only' },
  { key: 'patrol', label: 'Patrol — shows resolve' },
  { key: 'intercept', label: 'Intercept — kinetic, arrives next turn' },
] as const

type ActionKey = typeof ACTION_TYPES[number]['key']

export default function OpsPanel({ factionNames, humanFactionId, onSubmit, disabled }: Props) {
  const [actionType, setActionType] = useState<ActionKey>('task_assets')
  const [target, setTarget] = useState('')
  const [mission, setMission] = useState('sda_sweep')
  const [rationale, setRationale] = useState('')

  const otherFactions = Object.entries(factionNames).filter(([fid]) => fid !== humanFactionId)

  function handleSubmit() {
    const params: Record<string, string> = {}
    if (actionType === 'task_assets') params.mission = mission
    onSubmit({
      operations: [{
        action_type: actionType,
        target_faction: target || undefined,
        parameters: params,
        rationale,
      }],
    })
  }

  return (
    <div>
      <div className="panel-title">◆ OPERATIONS PHASE</div>

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 9 }}>ACTION TYPE</div>
        {ACTION_TYPES.map(({ key, label, desc }) => (
          <label key={key} style={{
            display: 'flex', alignItems: 'flex-start', gap: 8,
            padding: '6px 0', borderBottom: '1px solid #00d4ff08', cursor: 'pointer',
          }}>
            <input
              type="radio" name="action" value={key}
              checked={actionType === key}
              onChange={() => setActionType(key)}
              disabled={disabled}
              style={{ marginTop: 2, accentColor: '#00d4ff' }}
            />
            <div>
              <div style={{ fontSize: 12, color: '#e2e8f0' }}>{label}</div>
              <div style={{ fontSize: 10, color: '#475569' }}>{desc}</div>
            </div>
          </label>
        ))}
      </div>

      {actionType === 'task_assets' && (
        <div style={{ marginBottom: 12 }}>
          <div className="panel-title" style={{ fontSize: 9 }}>MISSION</div>
          {MISSIONS.map(({ key, label }) => (
            <label key={key} style={{ display: 'flex', gap: 8, padding: '4px 0', cursor: 'pointer' }}>
              <input
                type="radio" name="mission" value={key}
                checked={mission === key}
                onChange={() => setMission(key)}
                disabled={disabled}
                style={{ accentColor: '#00d4ff' }}
              />
              <span style={{ fontSize: 11, color: '#94a3b8' }}>{label}</span>
            </label>
          ))}
        </div>
      )}

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 9 }}>TARGET FACTION (optional)</div>
        <select
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          disabled={disabled}
          style={{
            width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
            color: '#94a3b8', padding: '6px 8px', fontFamily: 'Courier New',
            fontSize: 11, borderRadius: 2,
          }}
        >
          <option value="">— none —</option>
          {otherFactions.map(([fid, name]) => (
            <option key={fid} value={fid}>{name}</option>
          ))}
        </select>
      </div>

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 9 }}>RATIONALE</div>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Operational rationale..."
          disabled={disabled}
          style={{
            width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
            color: '#94a3b8', padding: '6px 8px', fontFamily: 'system-ui',
            fontSize: 12, resize: 'vertical', minHeight: 60, borderRadius: 2,
            boxSizing: 'border-box',
          }}
        />
      </div>

      <button
        className="btn-primary"
        onClick={handleSubmit}
        disabled={disabled || !rationale.trim()}
        style={{ width: '100%' }}
      >
        [ EXECUTE OPERATION ]
      </button>
    </div>
  )
}
```

- [ ] **Step 3: Create `web/src/components/phase/ResponsePanel.tsx`**

```typescript
// web/src/components/phase/ResponsePanel.tsx
import { useState } from 'react'

interface Props {
  factionNames: Record<string, string>
  humanFactionId: string
  turnLogSummary: string
  onSubmit: (decision: Record<string, unknown>) => void
  disabled: boolean
}

export default function ResponsePanel({ factionNames, humanFactionId, turnLogSummary, onSubmit, disabled }: Props) {
  const [escalate, setEscalate] = useState(false)
  const [retaliate, setRetaliate] = useState(false)
  const [targetFaction, setTargetFaction] = useState('')
  const [statement, setStatement] = useState('')
  const [rationale, setRationale] = useState('')

  const otherFactions = Object.entries(factionNames).filter(([fid]) => fid !== humanFactionId)

  function handleSubmit() {
    onSubmit({
      response: {
        escalate,
        retaliate: escalate && retaliate,
        target_faction: (escalate && retaliate && targetFaction) ? targetFaction : undefined,
        public_statement: statement,
        rationale,
      },
    })
  }

  return (
    <div>
      <div className="panel-title">◆ RESPONSE PHASE</div>

      {turnLogSummary && (
        <div style={{
          background: '#0a0a14', border: '1px solid #00d4ff11',
          padding: '8px 10px', fontSize: 10, color: '#475569',
          fontFamily: 'Courier New', marginBottom: 12, borderRadius: 2,
          whiteSpace: 'pre-line',
        }}>
          {turnLogSummary}
        </div>
      )}

      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'flex', gap: 10, cursor: 'pointer', alignItems: 'center' }}>
          <input
            type="checkbox" checked={escalate}
            onChange={(e) => { setEscalate(e.target.checked); if (!e.target.checked) setRetaliate(false) }}
            disabled={disabled}
            style={{ accentColor: '#ff4499', width: 16, height: 16 }}
          />
          <div>
            <div style={{ fontSize: 12, color: escalate ? '#ff4499' : '#94a3b8' }}>ESCALATE</div>
            <div style={{ fontSize: 10, color: '#475569' }}>Raises tension +15% · unlocks harder actions next turn</div>
          </div>
        </label>

        {escalate && (
          <div style={{ marginTop: 10, paddingLeft: 26 }}>
            <label style={{ display: 'flex', gap: 10, cursor: 'pointer', alignItems: 'center', marginBottom: 8 }}>
              <input
                type="checkbox" checked={retaliate}
                onChange={(e) => setRetaliate(e.target.checked)}
                disabled={disabled}
                style={{ accentColor: '#ff4499', width: 14, height: 14 }}
              />
              <span style={{ fontSize: 11, color: retaliate ? '#ff4499' : '#64748b' }}>Retaliate against faction</span>
            </label>
            {retaliate && (
              <select
                value={targetFaction}
                onChange={(e) => setTargetFaction(e.target.value)}
                disabled={disabled}
                style={{
                  width: '100%', background: '#020b18', border: '1px solid #ff449933',
                  color: '#94a3b8', padding: '6px 8px', fontFamily: 'Courier New',
                  fontSize: 11, borderRadius: 2,
                }}
              >
                <option value="">— select target —</option>
                {otherFactions.map(([fid, name]) => (
                  <option key={fid} value={fid}>{name}</option>
                ))}
              </select>
            )}
          </div>
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 9 }}>PUBLIC STATEMENT (optional)</div>
        <input
          type="text"
          value={statement}
          onChange={(e) => setStatement(e.target.value)}
          placeholder="Official statement to release..."
          disabled={disabled}
          style={{
            width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
            color: '#94a3b8', padding: '6px 8px', fontFamily: 'system-ui',
            fontSize: 12, borderRadius: 2, boxSizing: 'border-box',
          }}
        />
      </div>

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 9 }}>RATIONALE</div>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Strategic rationale for your response..."
          disabled={disabled}
          style={{
            width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
            color: '#94a3b8', padding: '6px 8px', fontFamily: 'system-ui',
            fontSize: 12, resize: 'vertical', minHeight: 60, borderRadius: 2,
            boxSizing: 'border-box',
          }}
        />
      </div>

      <button
        className="btn-primary"
        onClick={handleSubmit}
        disabled={disabled || !rationale.trim()}
        style={{ width: '100%' }}
      >
        [ SUBMIT RESPONSE ]
      </button>
    </div>
  )
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
cd /Users/tbarnes/projects/agents
git add web/src/components/phase/
git commit -m "feat: add InvestPanel, OpsPanel, ResponsePanel phase components"
```

---

## Task 8: LoadingOverlay, AdvisorPanel, TurnSummary

**Files:**
- Create: `web/src/components/LoadingOverlay.tsx`
- Create: `web/src/components/AdvisorPanel.tsx`
- Create: `web/src/components/TurnSummary.tsx`

- [ ] **Step 1: Create `web/src/components/LoadingOverlay.tsx`**

```typescript
// web/src/components/LoadingOverlay.tsx
export default function LoadingOverlay() {
  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: 'rgba(2, 11, 24, 0.85)',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      zIndex: 100,
    }}>
      <div className="mono" style={{ color: '#00d4ff', fontSize: 13, letterSpacing: 4, marginBottom: 20 }}>
        AI COMMANDERS DELIBERATING
      </div>
      <div style={{
        width: 200, height: 2,
        background: 'rgba(0,212,255,0.1)',
        overflow: 'hidden', borderRadius: 1,
      }}>
        <div style={{
          height: '100%', width: '40%',
          background: '#00d4ff',
          boxShadow: '0 0 8px #00d4ff',
          animation: 'scan 1.5s linear infinite',
        }} />
      </div>
      <style>{`
        @keyframes scan {
          0%   { transform: translateX(-100%); }
          100% { transform: translateX(600%); }
        }
      `}</style>
    </div>
  )
}
```

- [ ] **Step 2: Create `web/src/components/AdvisorPanel.tsx`**

```typescript
// web/src/components/AdvisorPanel.tsx
import type { Recommendation, Phase } from '../types'

interface Props {
  recommendation: Recommendation | null
  phase: Phase
  onAccept: () => void
  onDismiss: () => void
}

export default function AdvisorPanel({ recommendation: rec, phase, onAccept, onDismiss }: Props) {
  if (!rec) return null

  let summary = ''
  if (phase === 'invest' && rec.top_recommendation.investment) {
    const inv = rec.top_recommendation.investment
    const top = Object.entries(inv)
      .filter(([k, v]) => k !== 'rationale' && typeof v === 'number' && v > 0)
      .sort(([, a], [, b]) => (b as number) - (a as number))
      .slice(0, 3)
      .map(([k, v]) => `${k}: ${((v as number) * 100).toFixed(0)}%`)
    summary = top.join(' · ')
  } else if (phase === 'operations' && rec.top_recommendation.operations?.[0]) {
    const op = rec.top_recommendation.operations[0]
    summary = `${op.action_type}${op.target_faction ? ` → ${op.target_faction}` : ''}`
  } else if (phase === 'response' && rec.top_recommendation.response) {
    summary = rec.top_recommendation.response.escalate ? 'ESCALATE' : 'Stand down'
  }

  return (
    <div className="panel" style={{ borderColor: 'rgba(245,158,11,0.4)', marginBottom: 12 }}>
      <div className="panel-title" style={{ color: '#f59e0b' }}>◆ AI ADVISOR RECOMMENDATION</div>
      {summary && (
        <div className="mono" style={{ fontSize: 11, color: '#e2e8f0', marginBottom: 6 }}>{summary}</div>
      )}
      <div style={{ fontSize: 10, color: '#64748b', marginBottom: 10 }}>{rec.strategic_rationale}</div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn-primary" onClick={onAccept} style={{ flex: 1, fontSize: 10 }}>
          [ ACCEPT ]
        </button>
        <button className="btn-primary" onClick={onDismiss}
          style={{ flex: 1, fontSize: 10, borderColor: '#334155', color: '#64748b' }}>
          [ DISMISS ]
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create `web/src/components/TurnSummary.tsx`**

```typescript
// web/src/components/TurnSummary.tsx
import type { GameState } from '../types'

interface Props {
  gameState: GameState
  coalitionDominance: Record<string, number>
  onContinue: () => void
}

export default function TurnSummary({ gameState, coalitionDominance, onContinue }: Props) {
  const { turn, total_turns, events, turn_log, coalition_states, coalition_colors, victory_threshold } = gameState

  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: 'rgba(2, 11, 24, 0.95)',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', padding: '40px 20px',
      overflowY: 'auto', zIndex: 50,
    }}>
      <div className="mono" style={{ color: '#00d4ff', fontSize: 16, letterSpacing: 6, marginBottom: 8 }}>
        ══ END OF TURN {turn} ══
      </div>
      <div className="mono" style={{ color: '#334155', fontSize: 10, marginBottom: 32 }}>
        {total_turns - turn} turn{total_turns - turn !== 1 ? 's' : ''} remaining
      </div>

      <div style={{ width: '100%', maxWidth: 640, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {events.length > 0 && (
          <div className="panel" style={{ borderColor: 'rgba(245,158,11,0.3)' }}>
            <div className="panel-title" style={{ color: '#f59e0b' }}>◆ CRISIS EVENTS</div>
            {events.map((ev) => (
              <div key={ev.event_id} style={{ marginBottom: 8 }}>
                <div className="mono" style={{ fontSize: 11, color: '#f59e0b' }}>
                  {'█'.repeat(Math.round(ev.severity * 5))}{'░'.repeat(5 - Math.round(ev.severity * 5))} {ev.event_type.toUpperCase()}
                </div>
                <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{ev.description}</div>
              </div>
            ))}
          </div>
        )}

        {turn_log.length > 0 && (
          <div className="panel">
            <div className="panel-title">◆ OPERATIONAL LOG</div>
            {turn_log.map((entry, i) => {
              const color = entry.includes('[KINETIC]') || entry.includes('[RETALIATION') ? '#ff4499'
                : entry.includes('disrupted') || entry.includes('gray-zone') ? '#f59e0b'
                : '#475569'
              return (
                <div key={i} className="mono" style={{ fontSize: 10, color, marginBottom: 3 }}>
                  {entry}
                </div>
              )
            })}
          </div>
        )}

        <div className="panel" style={{ borderColor: 'rgba(0,212,255,0.3)' }}>
          <div className="panel-title">◆ ORBITAL DOMINANCE</div>
          {Object.entries(coalition_states).map(([cid, cs]) => {
            const dom = coalitionDominance[cid] ?? 0
            const color = coalition_colors[cid] === 'green' ? '#00ff88' : '#ff4499'
            const gap = dom - victory_threshold
            return (
              <div key={cid} style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
                  <span className="mono" style={{ color }}>{cid} ({cs.member_ids.join(', ')})</span>
                  <span className="mono" style={{ color }}>{(dom * 100).toFixed(1)}%</span>
                  <span className="mono" style={{ color: gap >= 0 ? '#00ff88' : '#ff4499' }}>
                    {gap >= 0 ? '+' : ''}{(gap * 100).toFixed(1)}% vs threshold
                  </span>
                </div>
                <div style={{ height: 3, background: 'rgba(255,255,255,0.05)' }}>
                  <div style={{ height: '100%', width: `${Math.min(100, dom * 100)}%`, background: color }} />
                </div>
              </div>
            )
          })}
        </div>

        <button className="btn-primary" onClick={onContinue} style={{ width: '100%', fontSize: 13, padding: '12px' }}>
          [ CONTINUE TO TURN {turn + 1} ]
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
cd /Users/tbarnes/projects/agents
git add web/src/components/LoadingOverlay.tsx web/src/components/AdvisorPanel.tsx web/src/components/TurnSummary.tsx
git commit -m "feat: add LoadingOverlay, AdvisorPanel, TurnSummary components"
```

---

## Task 9: GamePage — wire everything together

**Files:**
- Create: `web/src/pages/GamePage.tsx`

- [ ] **Step 1: Create `web/src/pages/GamePage.tsx`**

```typescript
// web/src/pages/GamePage.tsx
import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { advance, decide, getRecommendation } from '../api/client'
import { useGameStore } from '../store/gameStore'
import OrbitalMap from '../components/OrbitalMap'
import FactionSidebar from '../components/FactionSidebar'
import DominanceRail from '../components/DominanceRail'
import LoadingOverlay from '../components/LoadingOverlay'
import AdvisorPanel from '../components/AdvisorPanel'
import TurnSummary from '../components/TurnSummary'
import InvestPanel from '../components/phase/InvestPanel'
import OpsPanel from '../components/phase/OpsPanel'
import ResponsePanel from '../components/phase/ResponsePanel'

export default function GamePage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const {
    gameState, coalitionDominance, recommendation,
    isLoading, error, showSummary,
    setGameState, setRecommendation, setLoading, setError, setShowSummary,
  } = useGameStore()

  useEffect(() => {
    if (!sessionId || !gameState) return
    if (gameState.game_over) {
      navigate(`/result/${sessionId}`)
    }
  }, [gameState?.game_over])

  async function fetchRecommendation(phase: 'invest' | 'operations' | 'response') {
    if (!sessionId || !gameState?.use_advisor) return
    try {
      const rec = await getRecommendation(sessionId, phase)
      setRecommendation(rec)
    } catch {
      setRecommendation(null)
    }
  }

  async function handleDecision(decision: Record<string, unknown>) {
    if (!sessionId || !gameState) return
    setLoading(true)
    setError(null)
    setRecommendation(null)
    try {
      const res = await decide(sessionId, gameState.current_phase as string, decision)
      setGameState(res.state, res.coalition_dominance)
      // After RESPONSE phase resolves, show turn summary before advancing
      if (res.state.current_phase === 'invest' && !res.state.game_over && res.state.turn > 0) {
        setShowSummary(true)
      } else if (res.state.human_snapshot && gameState.use_advisor) {
        await fetchRecommendation(res.state.current_phase as 'invest' | 'operations' | 'response')
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleNextTurn() {
    if (!sessionId) return
    setShowSummary(false)
    setLoading(true)
    setError(null)
    try {
      const res = await advance(sessionId)
      setGameState(res.state, res.coalition_dominance)
      if (res.state.human_snapshot && gameState?.use_advisor) {
        await fetchRecommendation(res.state.current_phase as 'invest' | 'operations' | 'response')
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  function handleAcceptAdvisor() {
    if (!recommendation || !gameState) return
    const phase = gameState.current_phase as string
    const rec = recommendation.top_recommendation
    let decision: Record<string, unknown> = {}
    if (phase === 'invest' && rec.investment) decision = { investment: rec.investment }
    else if (phase === 'operations' && rec.operations) decision = { operations: rec.operations }
    else if (phase === 'response' && rec.response) decision = { response: rec.response }
    setRecommendation(null)
    handleDecision(decision)
  }

  if (!gameState) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <div className="mono" style={{ color: '#00d4ff' }}>NO ACTIVE SESSION — <a href="/" style={{ color: '#00ff88' }}>RETURN TO SETUP</a></div>
      </div>
    )
  }

  const fs = gameState.human_snapshot?.faction_state ?? gameState.faction_states[gameState.human_faction_id]
  const snap = gameState.human_snapshot
  const phase = gameState.current_phase as string
  const factionNames = snap?.faction_names ?? Object.fromEntries(
    Object.entries(gameState.faction_states).map(([fid, s]) => [fid, s.name])
  )

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{
        padding: '8px 16px', borderBottom: '1px solid #00d4ff22',
        display: 'flex', alignItems: 'center', gap: 16, background: '#020b18',
      }}>
        <span className="mono" style={{ color: '#00d4ff', fontSize: 13, letterSpacing: 4 }}>◆ ASTRAKON</span>
        <span className="mono" style={{ color: '#334155', fontSize: 10 }}>·</span>
        <span className="mono" style={{ color: '#64748b', fontSize: 10 }}>
          TURN {gameState.turn}/{gameState.total_turns}
        </span>
        <span className="mono" style={{ color: '#334155', fontSize: 10 }}>·</span>
        <span className="mono" style={{ color: '#00d4ff88', fontSize: 10, letterSpacing: 2 }}>
          {phase.toUpperCase()} PHASE
        </span>
        <span style={{ flex: 1 }} />
        <span className="mono" style={{ color: '#64748b', fontSize: 10 }}>{gameState.scenario_name}</span>
      </div>

      {/* 3-column layout */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '200px 1fr 200px', gap: 8, padding: 8, overflow: 'hidden' }}>
        {/* Left: Faction Sidebar */}
        <FactionSidebar
          factionState={fs}
          turn={gameState.turn}
          totalTurns={gameState.total_turns}
          tensionLevel={gameState.tension_level}
        />

        {/* Center: Orbital Map + Phase Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, overflow: 'hidden' }}>
          <div style={{ flex: '0 0 45%' }}>
            <OrbitalMap gameState={gameState} coalitionDominance={coalitionDominance} />
          </div>
          <div className="panel" style={{ flex: 1, overflowY: 'auto' }}>
            {error && (
              <div style={{ color: '#ff4499', fontSize: 11, marginBottom: 10, fontFamily: 'Courier New' }}>
                ERROR: {error}
                <button className="btn-primary" onClick={() => { setError(null); handleNextTurn() }}
                  style={{ marginLeft: 10, fontSize: 10, padding: '2px 8px' }}>
                  RETRY
                </button>
              </div>
            )}

            {recommendation && (
              <AdvisorPanel
                recommendation={recommendation}
                phase={phase as 'invest' | 'operations' | 'response'}
                onAccept={handleAcceptAdvisor}
                onDismiss={() => setRecommendation(null)}
              />
            )}

            {phase === 'invest' && (
              <InvestPanel
                budget={fs.current_budget}
                onSubmit={handleDecision}
                disabled={isLoading}
              />
            )}
            {phase === 'operations' && (
              <OpsPanel
                factionNames={factionNames}
                humanFactionId={gameState.human_faction_id}
                onSubmit={handleDecision}
                disabled={isLoading}
              />
            )}
            {phase === 'response' && (
              <ResponsePanel
                factionNames={factionNames}
                humanFactionId={gameState.human_faction_id}
                turnLogSummary={snap?.turn_log_summary ?? ''}
                onSubmit={handleDecision}
                disabled={isLoading}
              />
            )}
          </div>
        </div>

        {/* Right: Dominance Rail */}
        <DominanceRail gameState={gameState} coalitionDominance={coalitionDominance} />
      </div>

      {isLoading && <LoadingOverlay />}

      {showSummary && (
        <TurnSummary
          gameState={gameState}
          coalitionDominance={coalitionDominance}
          onContinue={handleNextTurn}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd /Users/tbarnes/projects/agents
git add web/src/pages/GamePage.tsx
git commit -m "feat: add GamePage command center layout wiring all components"
```

---

## Task 10: ResultPage and end-to-end test

**Files:**
- Create: `web/src/pages/ResultPage.tsx`

- [ ] **Step 1: Create `web/src/pages/ResultPage.tsx`**

```typescript
// web/src/pages/ResultPage.tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { generateAar } from '../api/client'
import { useGameStore } from '../store/gameStore'

export default function ResultPage() {
  const navigate = useNavigate()
  const { sessionId, gameState, coalitionDominance, reset } = useGameStore()
  const [aar, setAar] = useState<string | null>(null)
  const [loadingAar, setLoadingAar] = useState(false)

  if (!gameState?.result) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <div className="mono" style={{ color: '#00d4ff' }}>
          NO RESULT — <a href="/" style={{ color: '#00ff88' }}>RETURN TO SETUP</a>
        </div>
      </div>
    )
  }

  const { winner_coalition, turns_completed, final_dominance } = gameState.result

  async function handleGenerateAar() {
    if (!sessionId) return
    setLoadingAar(true)
    try {
      const text = await generateAar(sessionId)
      setAar(text)
    } catch (e) {
      setAar(`Error generating AAR: ${String(e)}`)
    } finally {
      setLoadingAar(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 40 }}>
      <div className="mono" style={{ fontSize: 20, color: '#00d4ff', letterSpacing: 6, marginBottom: 8 }}>
        ══ SIMULATION COMPLETE ══
      </div>
      <div className="mono" style={{ color: '#334155', fontSize: 10, marginBottom: 32 }}>
        {turns_completed} turns · {gameState.scenario_name}
      </div>

      <div className="panel" style={{ width: '100%', maxWidth: 600, marginBottom: 16 }}>
        {winner_coalition ? (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div className="mono" style={{ fontSize: 14, color: '#00ff88', marginBottom: 8 }}>
              ◆ WINNER
            </div>
            <div className="mono" style={{ fontSize: 22, color: '#00ff88', letterSpacing: 4 }}>
              {winner_coalition.toUpperCase()}
            </div>
            <div className="mono" style={{ color: '#334155', fontSize: 10, marginTop: 8 }}>COALITION ACHIEVES ORBITAL DOMINANCE</div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div className="mono" style={{ fontSize: 18, color: '#f59e0b', letterSpacing: 4 }}>DRAW</div>
            <div className="mono" style={{ color: '#334155', fontSize: 10, marginTop: 8 }}>NO FACTION ACHIEVED HEGEMONY</div>
          </div>
        )}
      </div>

      <div className="panel" style={{ width: '100%', maxWidth: 600, marginBottom: 16 }}>
        <div className="panel-title">◆ FINAL DOMINANCE</div>
        {Object.entries(final_dominance ?? coalitionDominance).map(([cid, dom]) => {
          const color = gameState.coalition_colors[cid] === 'green' ? '#00ff88' : '#ff4499'
          return (
            <div key={cid} style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
                <span className="mono" style={{ color }}>{cid}</span>
                <span className="mono" style={{ color }}>{(dom * 100).toFixed(1)}%</span>
              </div>
              <div style={{ height: 3, background: 'rgba(255,255,255,0.05)' }}>
                <div style={{ height: '100%', width: `${Math.min(100, dom * 100)}%`, background: color }} />
              </div>
            </div>
          )
        })}
      </div>

      <div style={{ display: 'flex', gap: 12, width: '100%', maxWidth: 600, marginBottom: 24 }}>
        <button className="btn-primary" onClick={handleGenerateAar} disabled={loadingAar} style={{ flex: 1 }}>
          {loadingAar ? '[ GENERATING AAR... ]' : '[ GENERATE AFTER-ACTION REPORT ]'}
        </button>
        <button className="btn-primary" onClick={() => { reset(); navigate('/') }}
          style={{ flex: 1, borderColor: '#334155', color: '#64748b' }}>
          [ NEW GAME ]
        </button>
      </div>

      {aar && (
        <div className="panel" style={{ width: '100%', maxWidth: 600, whiteSpace: 'pre-wrap', fontSize: 12, color: '#94a3b8', lineHeight: 1.6 }}>
          <div className="panel-title">◆ AFTER-ACTION REPORT</div>
          {aar}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify full TypeScript compile**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: End-to-end manual test**

Start the API:
```bash
cd /Users/tbarnes/projects/agents && python run_api.py
```

Start the dev server:
```bash
cd /Users/tbarnes/projects/agents/web && npm run dev
```

Navigate to http://localhost:5173 and verify:
1. Setup page loads with scenario list
2. Select a scenario, configure one faction as Human, click Launch
3. GamePage shows with orbital map, faction sidebar, invest panel
4. Submit an investment allocation — OpsPanel appears
5. Submit an operation — ResponsePanel appears
6. Submit a response — TurnSummary overlay appears
7. Click Continue — next turn begins

- [ ] **Step 4: Build the frontend for production**

```bash
cd /Users/tbarnes/projects/agents/web && npm run build
```

Expected: `web/dist/` created with `index.html` and assets.

- [ ] **Step 5: Verify FastAPI serves the built frontend**

```bash
cd /Users/tbarnes/projects/agents && python run_api.py
```

Navigate to http://localhost:8000 — should show the Astrakon app (served by FastAPI's StaticFiles mount).

- [ ] **Step 6: Add web/dist to .gitignore**

```bash
grep "web/dist" /Users/tbarnes/projects/agents/.gitignore || echo "web/dist" >> /Users/tbarnes/projects/agents/.gitignore
grep "web/node_modules" /Users/tbarnes/projects/agents/.gitignore || echo "web/node_modules" >> /Users/tbarnes/projects/agents/.gitignore
```

- [ ] **Step 7: Commit**

```bash
cd /Users/tbarnes/projects/agents
git add web/src/pages/ResultPage.tsx .gitignore
git commit -m "feat: add ResultPage and complete frontend implementation"
```
