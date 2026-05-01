import { useState, useEffect } from 'react'

const STEPS = [0.75, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.2, 1.3, 1.4, 1.5]
const STORAGE_KEY = 'ui-font-scale'

function clampToStep(val: number): number {
  return STEPS.reduce((prev, curr) => Math.abs(curr - val) < Math.abs(prev - val) ? curr : prev)
}

export default function FontScaleWidget() {
  const [scale, setScale] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? clampToStep(parseFloat(saved)) : 1.0
  })

  useEffect(() => {
    document.body.style.zoom = String(scale)
    localStorage.setItem(STORAGE_KEY, String(scale))
  }, [scale])

  function adjust(dir: 1 | -1) {
    const idx = STEPS.indexOf(scale)
    const next = STEPS[Math.max(0, Math.min(STEPS.length - 1, idx + dir))]
    if (next !== undefined) setScale(next)
  }

  return (
    <div style={{
      position: 'fixed', bottom: 12, right: 12, zIndex: 9999,
      display: 'flex', alignItems: 'center', gap: 4,
      background: 'rgba(2, 11, 24, 0.85)', border: '1px solid #1e3a4a',
      borderRadius: 3, padding: '3px 6px',
    }}>
      <button
        onClick={() => adjust(-1)}
        disabled={scale <= STEPS[0]}
        style={{
          fontFamily: 'Courier New', fontSize: 11, color: scale <= STEPS[0] ? '#1e3a4a' : '#475569',
          background: 'none', border: 'none', cursor: scale <= STEPS[0] ? 'default' : 'pointer',
          padding: '0 2px', lineHeight: 1,
        }}
      >A−</button>
      <span style={{ fontFamily: 'Courier New', fontSize: 9, color: '#475569', minWidth: 28, textAlign: 'center', letterSpacing: 1 }}>
        {Math.round(scale * 100)}%
      </span>
      <button
        onClick={() => adjust(1)}
        disabled={scale >= STEPS[STEPS.length - 1]}
        style={{
          fontFamily: 'Courier New', fontSize: 13, color: scale >= STEPS[STEPS.length - 1] ? '#1e3a4a' : '#475569',
          background: 'none', border: 'none', cursor: scale >= STEPS[STEPS.length - 1] ? 'default' : 'pointer',
          padding: '0 2px', lineHeight: 1,
        }}
      >A+</button>
    </div>
  )
}
