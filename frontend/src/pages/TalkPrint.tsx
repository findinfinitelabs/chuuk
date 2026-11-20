/**
 * TalkPrint.tsx — the printed talk.
 * Purpose: lay the talk out on full Letter pages with a simple page number at
 * the foot of each. Browsers cannot number pages from CSS reliably, so the
 * talk is broken into blocks (title, section and point headings, scripture
 * verses, lines, images), each block is measured offscreen at page width, and
 * the blocks are packed onto pages of fixed height; a heading never ends a
 * page on its own. In print, everything but these pages is hidden.
 */
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import styles from './TalkPrint.module.css'
import { paginate } from './talkPaginate'

interface PrintLine { id: string; chk: string; en: string; scripture?: boolean; hidden?: boolean; kind?: 'text' | 'image'; image_id?: string; caption?: string }
interface PrintPoint { id: string; label: string; text: string; scriptures: string[]; minutes: number | null; children?: PrintPoint[]; hidden?: boolean; skipped?: boolean; hidden_scriptures?: string[] }
const hidden = (p: PrintPoint) => !!(p.hidden ?? p.skipped)
interface PrintVerse { chuukese: string; english: string }
export interface PrintTalk {
  title: string
  outline: { title: string; number?: string; note?: string; theme_scripture: string; points: PrintPoint[] }
  lines: Record<string, PrintLine[]>
}

type Block =
  | { kind: 'title'; number?: string; title: string; note?: string; theme?: string; verse?: PrintVerse }
  | { kind: 'section'; text: string; minutes: number | null }
  | { kind: 'point'; label: string; text: string }
  | { kind: 'verse'; cite: string; chk: string; en: string }
  | { kind: 'line'; chk: string; en: string; scripture: boolean }
  | { kind: 'image'; src: string; caption: string }

function buildBlocks(talk: PrintTalk, verses: Record<string, PrintVerse | undefined>, isScripture: (l: PrintLine) => boolean): Block[] {
  const out: Block[] = []
  const theme = talk.outline.theme_scripture
  out.push({ kind: 'title', number: talk.outline.number, title: talk.title, note: talk.outline.note, theme: theme || undefined, verse: theme ? verses[theme] : undefined })
  const pushPoint = (p: PrintPoint) => {
    for (const c of p.scriptures) {
      if ((p.hidden_scriptures || []).includes(c)) continue
      const v = verses[c]
      if (v && (v.chuukese || v.english)) out.push({ kind: 'verse', cite: c, chk: v.chuukese, en: v.english })
    }
    for (const l of talk.lines[p.id] || []) {
      if (l.hidden) continue
      if (l.kind === 'image' && l.image_id) out.push({ kind: 'image', src: `/api/talks/images/${l.image_id}`, caption: l.caption || '' })
      else if (l.chk || l.en) out.push({ kind: 'line', chk: l.chk, en: l.en, scripture: isScripture(l) })
    }
  }
  for (const s of talk.outline.points) {
    if (hidden(s)) continue
    out.push({ kind: 'section', text: s.text, minutes: s.minutes })
    pushPoint(s)
    for (const c of s.children || []) {
      if (hidden(c)) continue
      out.push({ kind: 'point', label: c.label, text: c.text })
      pushPoint(c)
    }
  }
  return out
}

function BlockView({ b, showEnglish, onImage }: { b: Block; showEnglish: boolean; onImage?: () => void }) {
  switch (b.kind) {
    case 'title':
      return (
        <div className={styles.block}>
          <div className={styles.title}>{b.number && <span className={styles.number}>{b.number}</span>}{b.title}</div>
          {b.note && <div className={styles.note}>{b.note}</div>}
          {b.theme && <div className={styles.theme}>Theme: {b.theme}</div>}
          {b.verse && (b.verse.chuukese || b.verse.english) && (
            <div className={styles.scripture}>
              {b.verse.chuukese && <div className={styles.chk}>{b.verse.chuukese}</div>}
              {showEnglish && b.verse.english && <div className={styles.en}>{b.verse.english}</div>}
            </div>
          )}
        </div>
      )
    case 'section':
      return <div className={`${styles.block} ${styles.section}`}>{b.text}{b.minutes ? <span className={styles.minutes}>({b.minutes} min)</span> : null}</div>
    case 'point':
      return <div className={`${styles.block} ${styles.point}`}>{b.label && <span className={styles.label}>{b.label}.</span>}{b.text}</div>
    case 'verse':
      return (
        <div className={`${styles.block} ${styles.scripture}`}>
          <div className={styles.cite}>{b.cite}</div>
          {b.chk && <div className={styles.chk}>{b.chk}</div>}
          {showEnglish && b.en && <div className={styles.en}>{b.en}</div>}
        </div>
      )
    case 'line':
      return (
        <div className={`${styles.block} ${b.scripture ? styles.scripture : ''}`}>
          {b.chk && <div className={styles.chk}>{b.chk}</div>}
          {showEnglish && b.en && <div className={styles.en}>{b.en}</div>}
        </div>
      )
    case 'image':
      return (
        <div className={`${styles.block} ${styles.image}`}>
          <img src={b.src} alt={b.caption || 'Talk image'} onLoad={onImage} />
          {b.caption && <div className={styles.caption}>{b.caption}</div>}
        </div>
      )
  }
}

export default function TalkPrint({ talk, verses, showEnglish, isScripture }: {
  talk: PrintTalk; verses: Record<string, PrintVerse | undefined>; showEnglish: boolean; isScripture: (l: PrintLine) => boolean
}) {
  const blocks = useMemo(() => buildBlocks(talk, verses, isScripture), [talk, verses, isScripture])
  const measureRef = useRef<HTMLDivElement>(null)
  const bodyRef = useRef<HTMLDivElement>(null)
  const [pages, setPages] = useState<number[][]>([])
  const [tick, setTick] = useState(0)

  useLayoutEffect(() => {
    const m = measureRef.current, body = bodyRef.current
    if (!m || !body) return
    const limit = body.getBoundingClientRect().height
    const heights = Array.from(m.children).map((c) => {
      const r = (c as HTMLElement).getBoundingClientRect()
      const mb = parseFloat(getComputedStyle(c as HTMLElement).marginBottom) || 0
      const mt = parseFloat(getComputedStyle(c as HTMLElement).marginTop) || 0
      return r.height + mb + mt
    })
    setPages(paginate(heights, blocks.map((b) => b.kind), limit))
  }, [blocks, showEnglish, tick])

  const node = (
    <div className={styles.root} aria-hidden="true">
      {/* Measuring copy: every block at page width, never printed. */}
      <div className={`${styles.page} ${styles.measureWrap}`}>
        <div className={styles.body} ref={bodyRef} />
        <div className={styles.measure} ref={measureRef}>
          {blocks.map((b, i) => <BlockView key={i} b={b} showEnglish={showEnglish} onImage={() => setTick((t) => t + 1)} />)}
        </div>
      </div>
      {pages.map((idx, pi) => (
        <div className={styles.page} key={pi}>
          <div className={styles.body}>{idx.map((i) => <BlockView key={i} b={blocks[i]} showEnglish={showEnglish} />)}</div>
          <div className={styles.foot}>{pi + 1} / {pages.length}</div>
        </div>
      ))}
    </div>
  )
  return createPortal(node, document.body)
}
