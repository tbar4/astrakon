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
