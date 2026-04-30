import { useState, useEffect } from 'react'
import { LOADING_QUOTES } from '../data/loadingQuotes'

export default function LoadingOverlay() {
  const [quoteIdx, setQuoteIdx] = useState(() => Math.floor(Math.random() * LOADING_QUOTES.length))
  const [fading, setFading] = useState(true)

  useEffect(() => {
    // Initial fade in
    const initial = setTimeout(() => setFading(false), 50)

    // Rotate every 10s: fade out → swap → fade in
    const interval = setInterval(() => {
      setFading(true)
      setTimeout(() => {
        setQuoteIdx((i) => (i + 1) % LOADING_QUOTES.length)
        setFading(false)
      }, 600)
    }, 10000)

    return () => {
      clearTimeout(initial)
      clearInterval(interval)
    }
  }, [])

  const quote = LOADING_QUOTES[quoteIdx]

  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: 'rgba(2, 11, 24, 0.92)',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      zIndex: 100, gap: 20,
    }}>
      <div className="mono" style={{ color: '#00d4ff', fontSize: 13, letterSpacing: 4 }}>
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

      <div style={{
        maxWidth: 480, textAlign: 'center',
        opacity: fading ? 0 : 1,
        transition: 'opacity 0.6s ease',
        marginTop: 12,
      }}>
        <div style={{
          fontSize: 12, color: '#64748b', fontStyle: 'italic',
          lineHeight: 1.7, marginBottom: 10,
          fontFamily: 'Georgia, serif',
        }}>
          "{quote.text}"
        </div>
        <div className="mono" style={{ fontSize: 9, color: '#334155', letterSpacing: 1 }}>
          — {quote.author}
        </div>
        <div className="mono" style={{ fontSize: 9, color: '#1e3a4a', letterSpacing: 1, marginTop: 2 }}>
          {quote.source}
        </div>
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
