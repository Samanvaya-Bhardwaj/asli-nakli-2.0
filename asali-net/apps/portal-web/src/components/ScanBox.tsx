import { Camera, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { layoutLooksWrong, useScannerBursts } from '../hooks/useScannerBursts'
import { Button, Notice } from './ui'

export type ScanSource = 'wedge' | 'camera' | 'typed'

// The input keeps focus; bursts from a keyboard-wedge scanner land here wherever focus was (PLAN.md 10.3).
export function ScanBox({ onRead, disabled = false }: { onRead: (raw: string, source: ScanSource) => void; disabled?: boolean }) {
  const ref = useRef<HTMLInputElement>(null)
  const [value, setValue] = useState('')
  const [camera, setCamera] = useState(false)
  const [layout, setLayout] = useState(false)

  const send = (raw: string, source: ScanSource) => {
    const clean = raw.trim()
    if (!clean) return
    setLayout(layoutLooksWrong(clean))
    onRead(clean, source)
    setValue('')
    ref.current?.focus()
  }
  useScannerBursts((raw) => send(raw, 'wedge'), !disabled)
  useEffect(() => {
    if (!disabled) ref.current?.focus()
  }, [disabled])

  return (
    <div className="grid gap-2">
      <label htmlFor="scan-input" className="text-[15px] font-semibold">
        Scan or type a code
      </label>
      <div className="flex gap-2.5">
        <input
          id="scan-input"
          ref={ref}
          data-scan-input
          value={value}
          disabled={disabled}
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              send(value, 'typed')
            }
          }}
          className="min-h-14 w-full min-w-0 rounded-control border-0 bg-inset px-4 font-mono text-lg tracking-[0.02em] shadow-[inset_0_0_0_1px_var(--border)] outline-none transition-shadow duration-150 hover:shadow-[inset_0_0_0_1px_var(--border-strong)] focus:shadow-[inset_0_0_0_1px_var(--accent-ink)]"
        />
        <Button onClick={() => send(value, 'typed')} disabled={disabled || !value.trim()} kind="secondary" className="min-h-14">
          Add code
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-[13px] text-meta">
        <span aria-live="polite" className="inline-flex items-center gap-2">
          <span aria-hidden className={`size-2 rounded-full ${disabled ? 'bg-unk' : 'bg-ok shadow-[0_0_0_3px_var(--ok-wash)]'}`} />
          {disabled ? 'Scanner paused' : 'Scanner ready'}
        </span>
        <span aria-hidden>·</span>
        {window.isSecureContext ? (
          <button type="button" className="inline-flex min-h-11 items-center gap-1.5 rounded-full bg-surface-2 px-4 font-medium text-ink shadow-[inset_0_0_0_1px_var(--border)] transition-colors duration-150 hover:bg-sunken" onClick={() => setCamera(true)}>
            <Camera size={16} strokeWidth={1.75} /> Camera
          </button>
        ) : (
          <span>Camera needs HTTPS. Use the scanner or type the code.</span>
        )}
      </div>
      {layout && <Notice tone="warn">The scanner may be set to a different keyboard layout. Check its settings, then scan again.</Notice>}
      {camera && <CameraSheet onClose={() => setCamera(false)} onCode={(raw) => send(raw, 'camera')} />}
    </div>
  )
}

function CameraSheet({ onClose, onCode }: { onClose: () => void; onCode: (raw: string) => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const [problem, setProblem] = useState('')
  useEffect(() => {
    let stop = false
    let stream: MediaStream | undefined
    void (async () => {
      try {
        const { BarcodeDetector } = await import('barcode-detector')
        const detector = new BarcodeDetector({ formats: ['qr_code', 'code_128', 'data_matrix'] })
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
        if (!video.current) return
        video.current.srcObject = stream
        await video.current.play()
        const tick = async () => {
          if (stop || !video.current) return
          const found = await detector.detect(video.current)
          if (found[0]) onCode(found[0].rawValue)
          setTimeout(tick, 250)
        }
        void tick()
      } catch {
        setProblem('The camera could not start. Allow camera access for this page, or use the scanner or type the code.')
      }
    })()
    return () => {
      stop = true
      stream?.getTracks().forEach((t) => t.stop())
    }
  }, [onCode])
  return (
    <div role="dialog" aria-label="Camera" className="fixed inset-x-0 bottom-0 z-20 mx-auto max-h-[80vh] max-w-[640px] rounded-t-[28px] bg-surface p-5 shadow-pop">
      <div className="mb-2 flex items-center justify-between">
        <h2>Camera</h2>
        <Button kind="quiet" onClick={onClose} aria-label="Close camera">
          <X size={20} strokeWidth={1.75} />
        </Button>
      </div>
      {problem ? <Notice tone="warn">{problem}</Notice> : <video ref={video} muted playsInline className="max-h-[60vh] w-full rounded-control bg-inset" />}
    </div>
  )
}
