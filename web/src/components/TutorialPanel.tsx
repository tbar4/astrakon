// web/src/components/TutorialPanel.tsx
import { useState, useEffect } from 'react'

const STORAGE_KEY = 'astrakon_tutorial_done'

const STEPS: Record<string, { title: string; bullets: string[]; tip: string }> = {
  invest: {
    title: 'INVEST PHASE',
    bullets: [
      'Allocate your budget across categories using the sliders.',
      'LEO Constellation (5 pts/node) is cheapest — build your backbone here first.',
      'R&D and Education pay off in 3–6 turns, so invest early for long-term gain.',
      'Covert and Influence Ops deny rivals without triggering formal retaliation.',
      'To prevent kinetic escalation: avoid Kinetic Weapons entirely — you cannot launch an Intercept without them. Diplomacy investment also lowers adversary willingness to strike first.',
    ],
    tip: 'SUGGESTED TURN 1: ~40% LEO, ~20% R&D, remainder into Influence Ops or Diplomacy.',
  },
  operations: {
    title: 'OPERATIONS PHASE',
    bullets: [
      'Take direct action this turn — or pass if you have nothing to gain.',
      'Task Assets uses your orbital nodes for a mission (costs budget).',
      'Gray Zone lets you disrupt rivals covertly (deniable, lower risk).',
      'Coordinate shares intel with coalition partners for joint-force bonuses.',
      'KINETIC WARNING: Intercept (Task Assets) destroys a satellite node but creates orbital debris and raises the escalation rung — triggering harder retaliations. Use Signal or Alliance Move to de-escalate instead.',
    ],
    tip: 'TURN 1 TIP: A diplomatic Signal or Coordinate action builds early coalition strength with low risk.',
  },
  response: {
    title: 'RESPONSE PHASE',
    bullets: [
      'React to crisis events and this turn\'s ops from other factions.',
      'Escalate signals resolve but raises tension — can trigger counter-responses.',
      'De-escalate stabilizes the situation; useful when tension is already high.',
      'Retaliate only if you were attacked and need to deter future aggression.',
      'STOP KINETIC SPIRAL: Each Escalate raises tension +15% and unlocks harder actions — including kinetic strikes — for all factions next turn. Choose De-escalate or a Public Statement when tension exceeds 60% to keep the conflict sub-kinetic.',
    ],
    tip: 'TURN 1 TIP: A neutral Public Statement is usually the safest first-turn response.',
  },
}

interface Props {
  phase: string
  turn: number
}

export default function TutorialPanel({ phase, turn }: Props) {
  const [visible, setVisible] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    const done = localStorage.getItem(STORAGE_KEY)
    if (!done && turn === 1) setVisible(true)
  }, [turn, phase])

  function dismissForever() {
    localStorage.setItem(STORAGE_KEY, '1')
    setDismissed(true)
    setVisible(false)
  }

  function dismissStep() {
    setVisible(false)
  }

  if (dismissed || !visible || turn !== 1) return null

  const step = STEPS[phase]
  if (!step) return null

  return (
    <div style={{
      background: '#0a1929', border: '1px solid #00d4ff44', borderRadius: 4,
      padding: '12px 14px', marginBottom: 14,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontFamily: 'Courier New', fontSize: 10, color: '#00d4ff', letterSpacing: 2 }}>
          ◆ TUTORIAL — {step.title}
        </span>
        <button onClick={dismissStep}
          style={{ background: 'none', border: 'none', color: '#64748b', fontSize: 11, cursor: 'pointer', fontFamily: 'Courier New' }}>
          ✕
        </button>
      </div>
      <ul style={{ margin: 0, paddingLeft: 16, listStyle: 'disc' }}>
        {step.bullets.map((b, i) => (
          <li key={i} style={{ fontSize: 11, color: '#64748b', marginBottom: 4, fontFamily: 'system-ui' }}>{b}</li>
        ))}
      </ul>
      <div style={{ marginTop: 10, padding: '6px 8px', background: '#00d4ff08', borderLeft: '2px solid #00d4ff44' }}>
        <span style={{ fontSize: 10, color: '#00d4ffaa', fontFamily: 'Courier New' }}>{step.tip}</span>
      </div>
      <div style={{ marginTop: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button onClick={dismissForever}
          style={{ background: 'none', border: 'none', color: '#64748b', fontSize: 10, cursor: 'pointer', fontFamily: 'Courier New', textDecoration: 'underline' }}>
          skip tutorial
        </button>
        <button onClick={dismissStep}
          style={{ background: 'none', border: '1px solid #00d4ff44', color: '#00d4ff', fontSize: 10, cursor: 'pointer', fontFamily: 'Courier New', padding: '3px 12px', borderRadius: 2 }}>
          GOT IT
        </button>
      </div>
    </div>
  )
}
