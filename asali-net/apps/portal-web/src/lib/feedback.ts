// Sound and vibration for scans (DESIGN.md 8). Sounds are generated, not files. Staff default on, consumers off.

type Tone = 'ok' | 'corrected' | 'rejected'
const KEY = 'asali.sound'
let ctx: AudioContext | null = null

export function soundEnabled(defaultOn: boolean): boolean {
  try {
    const stored = localStorage.getItem(KEY)
    return stored === null ? defaultOn : stored === 'on'
  } catch {
    return defaultOn
  }
}

export function setSound(on: boolean): void {
  try {
    localStorage.setItem(KEY, on ? 'on' : 'off')
  } catch {
    /* private window: the choice lasts until the page closes */
  }
}

function beep(freq: number, ms: number, at = 0): void {
  ctx ??= new AudioContext()
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.frequency.value = freq
  gain.gain.value = 0.08
  osc.connect(gain).connect(ctx.destination)
  osc.start(ctx.currentTime + at)
  osc.stop(ctx.currentTime + at + ms / 1000)
}

export function feedback(tone: Tone, sound: boolean): void {
  if (sound) {
    try {
      if (tone === 'ok') beep(880, 70)
      else if (tone === 'corrected') {
        beep(660, 70)
        beep(660, 70, 0.12)
      } else beep(220, 180)
    } catch {
      /* no audio device */
    }
  }
  if ('vibrate' in navigator) navigator.vibrate(tone === 'rejected' ? [40, 60, 40] : 30)
}
