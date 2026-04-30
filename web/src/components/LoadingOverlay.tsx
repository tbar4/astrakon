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
