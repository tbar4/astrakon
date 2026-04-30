// web/src/pages/ResultPage.tsx
import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { generateAar, listAars } from '../api/client'
import type { AarResult, SavedAar } from '../api/client'
import { useGameStore } from '../store/gameStore'

function downloadMarkdown(text: string, scenarioName: string, focus: string) {
  const suffix = focus ? `-${focus.slice(0, 30).toLowerCase().replace(/\s+/g, '-')}` : ''
  const blob = new Blob([text], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `aar-${scenarioName.toLowerCase().replace(/\s+/g, '-')}${suffix}.md`
  a.click()
  URL.revokeObjectURL(url)
}

function printAsPdf(text: string, scenarioName: string) {
  const win = window.open('', '_blank')
  if (!win) return
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  win.document.open()
  win.document.write(`<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>AAR — ${scenarioName}</title>
  <style>
    body{font-family:Georgia,serif;max-width:800px;margin:40px auto;padding:0 20px;color:#1a1a1a;line-height:1.7}
    h1{font-size:20px;border-bottom:2px solid #333;padding-bottom:8px;margin-top:32px}
    h2{font-size:16px;margin-top:28px}h3{font-size:14px;margin-top:20px}
    p{margin:0 0 12px}ul,ol{margin:0 0 12px 24px}hr{border:none;border-top:1px solid #ccc;margin:24px 0}
    @media print{body{margin:20px}}
  </style>
</head>
<body>
<pre style="white-space:pre-wrap;font-family:Georgia,serif;font-size:14px">${escaped}</pre>
<script>window.onload=function(){window.print()}<\/script>
</body></html>`)
  win.document.close()
}

const PROSE: React.CSSProperties = { fontSize: 13, lineHeight: 1.75, color: '#cbd5e1', fontFamily: 'Georgia, serif' }
const INPUT_S: React.CSSProperties = {
  width: '100%', background: '#020b18', border: '1px solid #00d4ff33',
  color: '#94a3b8', fontFamily: 'Courier New', fontSize: 11, borderRadius: 2,
  padding: '8px 10px', resize: 'vertical',
}

function AarMarkdown({ text }: { text: string }) {
  return (
    <div style={PROSE}>
      <ReactMarkdown
        components={{
          h1: ({ children }) => <h1 style={{ fontSize: 16, color: '#00d4ff', letterSpacing: 2, marginBottom: 12, marginTop: 24, fontFamily: 'Courier New' }}>{children}</h1>,
          h2: ({ children }) => <h2 style={{ fontSize: 13, color: '#00d4ff99', letterSpacing: 1, marginBottom: 8, marginTop: 20, fontFamily: 'Courier New' }}>{children}</h2>,
          h3: ({ children }) => <h3 style={{ fontSize: 12, color: '#64748b', marginBottom: 6, marginTop: 16, fontFamily: 'Courier New' }}>{children}</h3>,
          p: ({ children }) => <p style={{ marginBottom: 12, color: '#94a3b8' }}>{children}</p>,
          strong: ({ children }) => <strong style={{ color: '#e2e8f0', fontWeight: 600 }}>{children}</strong>,
          em: ({ children }) => <em style={{ color: '#94a3b8', fontStyle: 'italic' }}>{children}</em>,
          ul: ({ children }) => <ul style={{ marginBottom: 12, paddingLeft: 20, color: '#94a3b8' }}>{children}</ul>,
          ol: ({ children }) => <ol style={{ marginBottom: 12, paddingLeft: 20, color: '#94a3b8' }}>{children}</ol>,
          li: ({ children }) => <li style={{ marginBottom: 4 }}>{children}</li>,
          hr: () => <hr style={{ border: 'none', borderTop: '1px solid #00d4ff22', margin: '20px 0' }} />,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}

export default function ResultPage() {
  const navigate = useNavigate()
  const { sessionId, gameState, coalitionDominance, reset } = useGameStore()

  const [savedAars, setSavedAars] = useState<SavedAar[]>([])
  const [activeAar, setActiveAar] = useState<AarResult | null>(null)
  const [focus, setFocus] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [selectedSavedIdx, setSelectedSavedIdx] = useState<number | null>(null)
  const focusRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (!sessionId) return
    listAars(sessionId)
      .then((aars) => {
        setSavedAars(aars)
        if (aars.length > 0) {
          setSelectedSavedIdx(0)
        }
      })
      .catch(() => {})
      .finally(() => setLoadingHistory(false))
  }, [sessionId])

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

  async function handleGenerate(force = false) {
    if (!sessionId) return
    setLoading(true)
    setActiveAar(null)
    setSelectedSavedIdx(null)
    try {
      const result = await generateAar(sessionId, focus, force)
      setActiveAar(result)
      // Refresh saved list
      const aars = await listAars(sessionId)
      setSavedAars(aars)
    } catch (e) {
      setActiveAar({ text: `Error generating AAR: ${String(e)}`, cached: false, focus })
    } finally {
      setLoading(false)
    }
  }

  const displayedAar: { text: string; focus: string; cached?: boolean } | null =
    activeAar ?? (selectedSavedIdx !== null ? savedAars[selectedSavedIdx] : null)

  const scenarioName = gameState.scenario_name

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 40 }}>

      {/* Top nav */}
      <div style={{ width: '100%', maxWidth: 700, display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
        <button className="btn-primary" onClick={() => navigate('/')}
          style={{ fontSize: 10, padding: '4px 14px', borderColor: '#334155', color: '#64748b' }}>
          ← MAIN MENU
        </button>
        <div className="mono" style={{ fontSize: 20, color: '#00d4ff', letterSpacing: 6 }}>
          ══ SIMULATION COMPLETE ══
        </div>
        <button className="btn-primary" onClick={() => { reset(); navigate('/') }}
          style={{ fontSize: 10, padding: '4px 14px', borderColor: '#334155', color: '#64748b' }}>
          NEW GAME
        </button>
      </div>

      <div className="mono" style={{ color: '#334155', fontSize: 10, marginBottom: 32 }}>
        {turns_completed} turns · {scenarioName}
      </div>

      {/* Winner panel */}
      <div className="panel" style={{ width: '100%', maxWidth: 700, marginBottom: 16 }}>
        {winner_coalition ? (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div className="mono" style={{ fontSize: 14, color: '#00ff88', marginBottom: 8 }}>◆ WINNER</div>
            <div className="mono" style={{ fontSize: 22, color: '#00ff88', letterSpacing: 4 }}>{winner_coalition.toUpperCase()}</div>
            <div className="mono" style={{ color: '#334155', fontSize: 10, marginTop: 8 }}>COALITION ACHIEVES ORBITAL DOMINANCE</div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div className="mono" style={{ fontSize: 18, color: '#f59e0b', letterSpacing: 4 }}>DRAW</div>
            <div className="mono" style={{ color: '#334155', fontSize: 10, marginTop: 8 }}>NO FACTION ACHIEVED HEGEMONY</div>
          </div>
        )}
      </div>

      {/* Final dominance */}
      <div className="panel" style={{ width: '100%', maxWidth: 700, marginBottom: 16 }}>
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

      {/* AAR generation controls */}
      <div className="panel" style={{ width: '100%', maxWidth: 700, marginBottom: 16 }}>
        <div className="panel-title">◆ AFTER-ACTION REPORT</div>

        {/* Saved AARs selector */}
        {!loadingHistory && savedAars.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 10, color: '#475569', fontFamily: 'Courier New', marginBottom: 6, letterSpacing: 1 }}>SAVED REPORTS</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {savedAars.map((s, i) => (
                <button key={i}
                  onClick={() => { setSelectedSavedIdx(i); setActiveAar(null) }}
                  style={{
                    textAlign: 'left', background: selectedSavedIdx === i && !activeAar ? '#00d4ff0a' : 'none',
                    border: `1px solid ${selectedSavedIdx === i && !activeAar ? '#00d4ff33' : '#00d4ff11'}`,
                    borderRadius: 2, padding: '6px 10px', cursor: 'pointer',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  }}>
                  <span style={{ fontSize: 11, color: '#94a3b8', fontFamily: 'Courier New' }}>
                    {s.focus ? `"${s.focus}"` : 'Standard report'}
                  </span>
                  <span style={{ fontSize: 10, color: '#334155', fontFamily: 'Courier New' }}>
                    {new Date(s.created_at).toLocaleDateString()}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Focus field */}
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 10, color: '#475569', fontFamily: 'Courier New', marginBottom: 6, letterSpacing: 1 }}>
            FOCUS AREA <span style={{ color: '#334155' }}>(optional — e.g. "coalition defection dynamics" or "Turn 4 kinetic exchange")</span>
          </div>
          <textarea
            ref={focusRef}
            rows={2}
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            placeholder="Leave blank for a standard full-spectrum AAR..."
            style={INPUT_S}
          />
        </div>

        {/* Generate button */}
        <button className="btn-primary" onClick={() => void handleGenerate(false)} disabled={loading} style={{ width: '100%' }}>
          {loading
            ? '[ GENERATING — THIS MAY TAKE 30–60 SECONDS... ]'
            : savedAars.some(s => s.focus === focus.trim())
              ? '[ VIEW CACHED REPORT ]'
              : '[ GENERATE AFTER-ACTION REPORT ]'}
        </button>
      </div>

      {/* AAR token usage — only shown for freshly generated reports */}
      {activeAar && !activeAar.cached && activeAar.usage && (
        <div style={{ width: '100%', maxWidth: 700, marginBottom: 8, display: 'flex', gap: 16, padding: '6px 12px', border: '1px solid #00d4ff11', borderRadius: 2, background: '#020b18' }}>
          <span className="mono" style={{ fontSize: 9, color: '#334155', letterSpacing: 1 }}>AAR TOKENS</span>
          <span className="mono" style={{ fontSize: 9, color: '#475569' }}>IN {activeAar.usage.input_tokens.toLocaleString()}</span>
          <span className="mono" style={{ fontSize: 9, color: '#475569' }}>OUT {activeAar.usage.output_tokens.toLocaleString()}</span>
          {(activeAar.usage.cache_read_tokens ?? 0) > 0 && (
            <span className="mono" style={{ fontSize: 9, color: '#334155' }}>CACHE HIT {activeAar.usage.cache_read_tokens!.toLocaleString()}</span>
          )}
        </div>
      )}

      {/* Displayed AAR */}
      {displayedAar && (
        <div className="panel" style={{ width: '100%', maxWidth: 700 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <div>
              <span className="panel-title" style={{ display: 'inline' }}>◆ REPORT</span>
              {displayedAar.cached && (
                <span style={{ fontSize: 10, color: '#475569', fontFamily: 'Courier New', marginLeft: 10 }}>CACHED</span>
              )}
              {displayedAar.focus && (
                <span style={{ fontSize: 10, color: '#64748b', fontFamily: 'Courier New', marginLeft: 10 }}>
                  FOCUS: "{displayedAar.focus}"
                </span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn-primary"
                onClick={() => void handleGenerate(true)}
                disabled={loading}
                style={{ fontSize: 10, padding: '3px 10px', borderColor: '#334155', color: '#64748b' }}>
                REGENERATE
              </button>
              <button className="btn-primary"
                onClick={() => downloadMarkdown(displayedAar.text, scenarioName, displayedAar.focus ?? '')}
                style={{ fontSize: 10, padding: '3px 10px', borderColor: '#00d4ff66', color: '#00d4ff' }}>
                ↓ MD
              </button>
              <button className="btn-primary"
                onClick={() => printAsPdf(displayedAar.text, scenarioName)}
                style={{ fontSize: 10, padding: '3px 10px', borderColor: '#f59e0b66', color: '#f59e0b' }}>
                ↓ PDF
              </button>
            </div>
          </div>
          <AarMarkdown text={displayedAar.text} />
        </div>
      )}
    </div>
  )
}
