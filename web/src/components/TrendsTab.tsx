// web/src/components/TrendsTab.tsx
import type { GameState } from '../types'
import type { TurnSnapshot } from '../store/gameStore'

interface Props {
  gameState: GameState
  turnHistory: TurnSnapshot[]
}

interface LineSeries {
  id: string
  label: string
  color: string
  dash?: string
  getValue: (s: TurnSnapshot) => number
}

const MONO = { fontFamily: 'Courier New' } as const

const SHELL_ITEMS = [
  { id: 'leo' as const, label: 'LEO', color: '#00d4ff' },
  { id: 'meo' as const, label: 'MEO', color: '#f59e0b' },
  { id: 'geo' as const, label: 'GEO', color: '#c084fc' },
  { id: 'cis' as const, label: 'CIS', color: '#4ade80' },
]

const DASH_PATTERNS = ['none', '6,3', '2,2']

function Chart({
  history, series, yMax, height,
}: {
  history: TurnSnapshot[]
  series: LineSeries[]
  yMax: number
  height: number
}) {
  const W = 400
  const H = height
  if (history.length < 2) {
    return (
      <div style={{
        height: H, background: '#020b18', border: '1px solid #00d4ff0a', borderRadius: 2,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ ...MONO, fontSize: 10, color: '#1e3a4a' }}>AWAITING DATA</span>
      </div>
    )
  }
  const n = history.length
  const minTurn = history[0].turn
  const xRange = Math.max(history[n - 1].turn - minTurn, 1)
  const xOf = (snap: TurnSnapshot) => ((snap.turn - minTurn) / xRange) * W
  const yOf = (v: number) => H - (Math.min(Math.max(v, 0), yMax) / yMax) * H

  return (
    <div style={{ background: '#020b18', border: '1px solid #00d4ff0a', borderRadius: 2, overflow: 'hidden' }}>
      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ display: 'block' }}>
        {[0.25, 0.5, 0.75].map((f) => (
          <line key={f} x1={0} y1={H * (1 - f)} x2={W} y2={H * (1 - f)} stroke="#00d4ff06" strokeWidth="0.8" />
        ))}
        {series.map((s) => {
          const pts = history.map((snap) =>
            `${xOf(snap).toFixed(1)},${yOf(s.getValue(snap)).toFixed(1)}`
          ).join(' ')
          const last = history[n - 1]
          const lx = xOf(last)
          const ly = yOf(s.getValue(last))
          return (
            <g key={s.id}>
              <polyline
                points={pts} fill="none" stroke={s.color} strokeWidth="1.5"
                strokeLinejoin="round" strokeLinecap="round"
                strokeDasharray={!s.dash || s.dash === 'none' ? undefined : s.dash}
                opacity={0.85}
              />
              <circle cx={lx.toFixed(1)} cy={ly.toFixed(1)} r="2.5" fill={s.color} />
            </g>
          )
        })}
      </svg>
    </div>
  )
}

export default function TrendsTab({ gameState, turnHistory }: Props) {
  if (turnHistory.length === 0) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ ...MONO, fontSize: 11, color: '#00d4ff', letterSpacing: 2, marginBottom: 8 }}>◆ TRENDS</div>
          <div style={{ ...MONO, fontSize: 11, color: '#64748b' }}>Complete at least one turn to see trend data.</div>
        </div>
      </div>
    )
  }

  const lastSnap = turnHistory[turnHistory.length - 1]
  const coalitions = Object.keys(gameState.coalition_states)
  const factionIds = Object.keys(gameState.faction_states)

  const coalitionColor = (cid: string) =>
    gameState.coalition_colors[cid] === 'green' ? '#00ff88' : '#ff4499'

  // ── Dominance ──────────────────────────────────────────────────────────────
  const domSeries: LineSeries[] = coalitions.map((cid) => ({
    id: cid, label: cid,
    color: coalitionColor(cid),
    getValue: (s) => s.dominance[cid] ?? 0,
  }))

  // ── Tension ────────────────────────────────────────────────────────────────
  const tenSeries: LineSeries[] = [{
    id: 'tension', label: 'TENSION', color: '#f59e0b',
    getValue: (s) => s.tension,
  }]

  // ── Shell totals ───────────────────────────────────────────────────────────
  const shellSeries: LineSeries[] = SHELL_ITEMS.map((sh) => ({
    id: sh.id, label: sh.label, color: sh.color,
    getValue: (s) => s.shellTotals[sh.id],
  }))
  const maxShell = Math.max(...turnHistory.flatMap((s) => Object.values(s.shellTotals)), 1)
  const shellYMax = Math.ceil(maxShell / 5) * 5 || 5

  // ── Faction totals ─────────────────────────────────────────────────────────
  const factionSeries: LineSeries[] = factionIds.map((fid) => {
    const coalEntry = Object.entries(gameState.coalition_states).find(([, cs]) => cs.member_ids.includes(fid))
    const cid = coalEntry?.[0]
    const color = cid ? coalitionColor(cid) : '#00d4ff'
    const members = coalEntry?.[1].member_ids ?? [fid]
    const dash = DASH_PATTERNS[members.indexOf(fid)] ?? 'none'
    return {
      id: fid,
      label: (gameState.faction_states[fid]?.name ?? fid).slice(0, 12),
      color, dash,
      getValue: (s) => s.factionTotals[fid] ?? 0,
    }
  })
  const maxFaction = Math.max(...turnHistory.flatMap((s) => Object.values(s.factionTotals)), 1)
  const factionYMax = Math.ceil(maxFaction / 5) * 5 || 5

  function Legend({ series, fmt }: { series: LineSeries[]; fmt: (v: number) => string }) {
    return (
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {series.map((s) => (
          <span key={s.id} style={{ ...MONO, fontSize: 10, color: s.color }}>
            ● {s.label} {fmt(s.getValue(lastSnap))}
          </span>
        ))}
      </div>
    )
  }

  function TurnRange() {
    return (
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3 }}>
        <span style={{ ...MONO, fontSize: 9, color: '#1e3a4a' }}>T{turnHistory[0]?.turn}</span>
        <span style={{ ...MONO, fontSize: 9, color: '#1e3a4a' }}>T{lastSnap.turn}</span>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 18 }}>

      {/* DOMINANCE */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
          <span style={{ ...MONO, fontSize: 11, color: '#00d4ff', letterSpacing: 2 }}>◆ DOMINANCE</span>
          <Legend series={domSeries} fmt={(v) => `${(v * 100).toFixed(1)}%`} />
        </div>
        <Chart history={turnHistory} series={domSeries} yMax={1} height={90} />
        <TurnRange />
      </div>

      {/* TENSION */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
          <span style={{ ...MONO, fontSize: 11, color: '#00d4ff', letterSpacing: 2 }}>◆ TENSION</span>
          <Legend series={tenSeries} fmt={(v) => `${(v * 100).toFixed(0)}%`} />
        </div>
        <Chart history={turnHistory} series={tenSeries} yMax={1} height={60} />
        <TurnRange />
      </div>

      {/* NODES BY SHELL */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
          <span style={{ ...MONO, fontSize: 11, color: '#00d4ff', letterSpacing: 2 }}>◆ NODES BY SHELL</span>
          <Legend series={shellSeries} fmt={String} />
        </div>
        <Chart history={turnHistory} series={shellSeries} yMax={shellYMax} height={90} />
        <TurnRange />
      </div>

      {/* NODES BY FACTION */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
          <span style={{ ...MONO, fontSize: 11, color: '#00d4ff', letterSpacing: 2 }}>◆ NODES BY FACTION</span>
          <Legend series={factionSeries} fmt={String} />
        </div>
        <Chart history={turnHistory} series={factionSeries} yMax={factionYMax} height={90} />
        <TurnRange />
      </div>

    </div>
  )
}
