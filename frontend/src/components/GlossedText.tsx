/**
 * GlossedText — Chuukese text that reads as plain text with the dictionary
 * behind it: phrases carry a thin dotted underline, hovering a word shows a
 * soft cue and its gloss, and a click, tap or Enter selects the word (soft
 * blue) and pins its gloss. Related entries are shown for words we do not
 * hold. A reader setting adds a faint underline to every dictionary word.
 *
 * Used by the Watchtower Library search page and the Translation Game. The
 * `dictionary` and `similar` maps come from the backend's `_attach_dictionary`.
 */
import { useEffect, useState } from 'react'
import type { FocusEvent, KeyboardEvent as ReactKeyboardEvent, MouseEvent, ReactNode } from 'react'
import { Group, Switch, Text } from '@mantine/core'
import { setIndicators, useIndicators } from './glossSettings'
import styles from './GlossedText.module.css'
import { findPhraseSpans, grammarPhraseSpans, normKey, phraseGloss, spanIndex } from './glossUtils'
import type { PhraseEntry, PhraseMap } from './glossUtils'

/** An article in which a word was matched during the Translation Game. */
export interface Appearance {
  article_id: string | null
  title: string
  url: string
  /** The English sentence the word was matched in. */
  english: string
}

/** A dictionary entry for one Chuukese word, keyed by its lowercase form. */
export interface DictEntry {
  english: string
  grammar: string
  grammar_modifier: string | null
  definition: string
  status: 'translated' | 'untranslated'
  /** Confirmed by a person (translation game or review), not just imported. */
  verified?: boolean
  appearances?: Appearance[]
  /** Database id, so the analysis pages can edit the entry. */
  entry_id?: string | null
  /** Which collection holds it; only "dictionary" rows are editable in place. */
  source?: 'dictionary' | 'phrases' | 'words'
  /** Set when the text's spelling differs from the headword only in accents:
   *  the headword the entry was matched under. */
  variant_of?: string
  /** Every headword matching once accents are ignored. */
  variants?: string[]
}

export type Dictionary = Record<string, DictEntry>

/** A dictionary word that looks related to one we don't hold. */
export interface SimilarWord {
  word: string
  english: string
  grammar?: string
}

/** Related words for each unknown word, already in alphabetical order. */
export type SimilarMap = Record<string, SimilarWord[]>

/** What the floating gloss is currently describing: either a dictionary entry
 *  or, for an unknown word, the related entries we do hold. */
export interface Gloss {
  word: string
  entry?: DictEntry
  similar?: SimilarWord[]
  /** The hovered word is part of this dictionary phrase; `words` glosses each
   *  word of it in turn ("ewe: the", "Kot: God"). */
  phrase?: { entry: PhraseEntry; words: { word: string; entry?: DictEntry }[] }
  /** What the translation model proposes, shown after the dictionary's answer. */
  suggestion?: string
  x: number
  y: number
}

/** Splits on non-letters/digits, keeping the separators so the text rebuilds
 *  exactly. Mirrors the backend's `[^\W_]+`, so both sides agree on what a word is. */
const TOKENS = /([^\p{L}\p{N}]+)/u
const IS_WORD = /^[\p{L}\p{N}]+$/u
/** Separators that may sit between the words of one phrase. */
const PHRASE_GAP = /^[\s\-\u2011]+$/u

/** Articles grouped so each is listed once, with the sentence it was first seen in. */
function groupAppearances(appearances: Appearance[]): Appearance[] {
  const seen = new Map<string, Appearance>()
  appearances.forEach((a) => {
    const key = a.article_id || a.url || a.title
    if (key && !seen.has(key)) seen.set(key, a)
  })
  return Array.from(seen.values())
}

/** Every word of `text` as plain reading text with the dictionary behind it:
 *  a dotted underline marks phrases (library phrases, and runs of dictionary
 *  words whose parts of speech form one), hovering shows a soft cue, and a
 *  click, tap or Enter selects the word (soft blue) and pins its gloss until
 *  the next click or Escape. With "Show dictionary indicators" on, every word
 *  the dictionary holds also gets a faint dotted underline. */
export function GlossedWords({
  text, dictionary, similar, phrases = {}, onGloss, onWordClick, keyPrefix = '', marks,
}: {
  text: string
  /** Lowercase words to mark as key phrases (yellow), on top of the dictionary tint. */
  marks?: Set<string>
  dictionary: Dictionary
  similar: SimilarMap
  /** Multi-word headwords to underline as one unit when they occur. */
  phrases?: PhraseMap
  onGloss: (g: Gloss | null) => void
  /** Clicking any word (known or not) reports it, for pages that edit entries. */
  onWordClick?: (word: string) => void
  keyPrefix?: string
}): ReactNode {
  const indicators = useIndicators()
  const [pinned, setPinned] = useState<number | null>(null)
  useEffect(() => {
    if (pinned === null) return
    const clear = () => { setPinned(null); onGloss(null) }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') clear() }
    document.addEventListener('click', clear)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('click', clear); document.removeEventListener('keydown', onKey) }
  }, [pinned]) // eslint-disable-line react-hooks/exhaustive-deps

  const tokens = text.split(TOKENS)
  // Word tokens in order, so phrases can be found across the separators.
  const wordAt: number[] = []
  tokens.forEach((tok, ti) => { if (tok && IS_WORD.test(tok)) wordAt.push(ti) })
  const words = wordAt.map((ti) => tokens[ti])
  const keys = words.map(normKey)
  const lowers = words.map((w) => w.toLowerCase())
  const joinable = (i: number) => {
    const between = tokens.slice(wordAt[i] + 1, wordAt[i + 1]).join('')
    return PHRASE_GAP.test(between)
  }
  const library = findPhraseSpans(keys, phrases, joinable)
  const taken = new Set<number>()
  library.forEach((sp) => { for (let i = sp.start; i < sp.end; i++) taken.add(i) })
  const spans = spanIndex([...library, ...grammarPhraseSpans(words, lowers, dictionary, taken, joinable)])
  const tokenSpan = new Map<number, ReturnType<typeof spans.get>>()
  spans.forEach((span, wi) => {
    // Every token from the first word to the last word of the phrase, separators included.
    for (let ti = wordAt[span.start]; ti < wordAt[span.end - 1] + 1; ti++) tokenSpan.set(ti, span)
    tokenSpan.set(wordAt[wi], span)
  })
  const pinnedSpan = pinned !== null ? tokenSpan.get(pinned) : undefined

  return tokens.map((tok, ti) => {
    if (!tok) return null
    const key = `${keyPrefix}${ti}`
    const span = tokenSpan.get(ti)
    const inPinned = pinned !== null && (ti === pinned || (!!pinnedSpan && span === pinnedSpan))
    const phraseClass = span ? ` ${span.entry.kind === 'grammar' ? styles.grammarPhrase : styles.phrase}` : ''
    const selectedClass = inPinned ? ` ${styles.selected}` : ''
    if (!IS_WORD.test(tok)) return <span key={key} className={(phraseClass + selectedClass).trim() || undefined}>{tok}</span>

    const lower = tok.toLowerCase()
    const entry = dictionary[lower]
    const near = entry ? undefined : similar[lower]
    const hoverable = !!(entry || near || span)
    const marked = marks?.has(lower.replace(/[^\p{L}\p{N}]/gu, '')) ? ` ${styles.mark}` : ''
    const gloss = (e: { clientX: number; clientY: number }): Gloss => ({
      word: tok, entry, similar: near,
      phrase: span ? phraseGloss(span.entry, dictionary) : undefined,
      x: e.clientX, y: e.clientY,
    })
    const label = entry ? `${tok}: ${entry.english || 'in the dictionary'}` : span ? `${tok}, part of ${span.entry.text}` : near ? `${tok}: similar to ${near[0]?.word}` : tok
    const select = (e: { clientX: number; clientY: number; stopPropagation: () => void }) => {
      e.stopPropagation()
      if (onWordClick) { onWordClick(tok); return }
      if (!hoverable) return
      if (pinned === ti) { setPinned(null); onGloss(null) } else { setPinned(ti); onGloss(gloss(e)) }
    }
    return (
      <span
        key={key}
        className={`${styles.word}${hoverable ? ` ${styles.known}` : ''}${indicators && entry ? ` ${styles.indicator}` : ''}${phraseClass}${selectedClass}${marked}${onWordClick ? ` ${styles.clickable}` : ''}`}
        role={hoverable || onWordClick ? 'button' : undefined}
        tabIndex={hoverable || onWordClick ? 0 : undefined}
        aria-label={hoverable ? label : undefined}
        aria-pressed={hoverable ? inPinned : undefined}
        onClick={hoverable || onWordClick ? select : undefined}
        onKeyDown={hoverable || onWordClick ? (e: ReactKeyboardEvent<HTMLSpanElement>) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            const r = e.currentTarget.getBoundingClientRect()
            select({ clientX: r.left, clientY: r.bottom, stopPropagation: () => e.stopPropagation() })
          }
        } : undefined}
        onFocus={hoverable ? (e: FocusEvent<HTMLSpanElement>) => { if (pinned === null) { const r = e.currentTarget.getBoundingClientRect(); onGloss(gloss({ clientX: r.left, clientY: r.bottom })) } } : undefined}
        onBlur={hoverable ? () => { if (pinned === null) onGloss(null) } : undefined}
        onMouseEnter={hoverable ? (e: MouseEvent<HTMLSpanElement>) => { if (pinned === null) onGloss(gloss(e)) } : undefined}
        onMouseLeave={hoverable ? () => { if (pinned === null) onGloss(null) } : undefined}
      >
        {tok}
      </span>
    )
  })
}

export function GlossCard({ gloss }: { gloss: Gloss }) {
  // Keep the card on screen near the right and bottom edges.
  const left = Math.min(gloss.x + 14, window.innerWidth - 300)
  const top = Math.min(gloss.y + 18, window.innerHeight - 220)
  const { entry, similar, suggestion, phrase } = gloss
  const seenIn = entry?.appearances ? groupAppearances(entry.appearances) : []

  return (
    <div className={styles.gloss} style={{ left, top }}>
      {phrase && (
        <div className={styles.glossPhrase}>
          <div className={styles.glossWord}>{phrase.entry.text}</div>
          {phrase.entry.english ? (
            <div className={styles.glossEnglish}>{phrase.entry.english}</div>
          ) : (
            <div className={styles.glossMeta}>Phrase in the dictionary — no English translation yet</div>
          )}
          {(phrase.entry.grammar || phrase.entry.definition) && (
            <div className={styles.glossMeta}>
              {phrase.entry.grammar}
              {phrase.entry.grammar && phrase.entry.definition ? ' · ' : ''}
              {phrase.entry.definition}
            </div>
          )}
          <ul className={styles.glossList}>
            {phrase.words.map((w, i) => (
              <li key={`${w.word}-${i}`}>
                {w.word}: <span>{w.entry?.english || (w.entry ? 'no translation yet' : 'not in dictionary')}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className={styles.glossWord}>{gloss.word}</div>

      {entry ? (
        <>
          {entry.variant_of && (
            <div className={styles.glossVariant}>
              In the dictionary as <strong>{entry.variant_of}</strong>
              {entry.variants && entry.variants.length > 1
                ? ` (also ${entry.variants.filter((v) => v !== entry.variant_of).join(', ')})`
                : ''}
            </div>
          )}
          {entry.status === 'translated' ? (
            <div className={styles.glossEnglish}>{entry.english}</div>
          ) : (
            <div className={styles.glossMeta}>In the dictionary — no English translation yet</div>
          )}
          {(entry.grammar || entry.definition || entry.verified) && (
            <div className={styles.glossMeta}>
              {entry.grammar}
              {entry.grammar && entry.definition ? ' · ' : ''}
              {entry.definition}
              {entry.verified ? (entry.grammar || entry.definition ? ' · ' : '') + 'confirmed' : ''}
            </div>
          )}
          {seenIn.length > 0 && (
            <>
              <div className={styles.glossMeta}>Matched in:</div>
              <ul className={styles.glossList}>
                {seenIn.map((a) => (
                  <li key={a.article_id || a.url || a.title} className={styles.glossAppearance}>
                    {a.title || a.url || 'Untitled article'}
                    {a.english && <span> — “{a.english}”</span>}
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      ) : similar && similar.length > 0 ? (
        <>
          <div className={styles.glossMeta}>
            Not in the dictionary. Similar {similar.length === 1 ? 'entry' : 'entries'} we have:
          </div>
          <ul className={styles.glossList}>
            {similar.map((s) => (
              <li key={s.word}>
                {s.word}
                {s.english && <span> — {s.english}</span>}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {suggestion && suggestion.toLowerCase() !== (entry?.english || '').toLowerCase() && (
        <div className={styles.glossSuggestion}>
          Model suggests: {suggestion}
        </div>
      )}
    </div>
  )
}

/** The reader's dictionary setting and what the underlines mean. */
export function GlossLegend() {
  const indicators = useIndicators()
  return (
    <Group gap="md" mt="xs" align="center">
      <Switch size="xs" label="Show dictionary indicators" checked={indicators} onChange={(e) => setIndicators(e.currentTarget.checked)} />
      <Text size="xs" c="dimmed">
        <span className={styles.swatch} style={{ background: 'transparent', borderBottom: '2px dotted #6685A1', borderRadius: 0, height: 8 }} />
        phrase
      </Text>
      {indicators && (
        <Text size="xs" c="dimmed">
          <span className={styles.swatch} style={{ background: 'transparent', borderBottom: '2px dotted #B7C3CE', borderRadius: 0, height: 8 }} />
          in the dictionary
        </Text>
      )}
      <Text size="xs" c="dimmed">
        <span className={styles.swatch} style={{ background: '#DCEAF5' }} />
        selected · click or tap a word for its definition
      </Text>
    </Group>
  )
}
