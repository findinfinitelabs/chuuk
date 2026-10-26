/**
 * GlossedText — Chuukese text with every word tinted by its dictionary status
 * and a floating gloss on hover showing the base word's translation, grammar
 * and definition, or (for words we do not hold) related entries we do.
 *
 * Used by the Watchtower Library search page and the Translation Game. The
 * `dictionary` and `similar` maps come from the backend's `_attach_dictionary`.
 */
import type { MouseEvent, ReactNode } from 'react'
import { Group, Text } from '@mantine/core'
import styles from './GlossedText.module.css'
import { findPhraseSpans, glossStatus, phraseGloss, spanIndex } from './glossUtils'
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

/** Every word of `text` tinted by dictionary status; hovering a known or
 *  near-known word reports a Gloss through `onGloss` (null on leave). */
export function GlossedWords({
  text, dictionary, similar, phrases = {}, onGloss, keyPrefix = '',
}: {
  text: string
  dictionary: Dictionary
  similar: SimilarMap
  /** Multi-word headwords to underline as one unit when they occur. */
  phrases?: PhraseMap
  onGloss: (g: Gloss | null) => void
  keyPrefix?: string
}): ReactNode {
  const tokens = text.split(TOKENS)
  // Word tokens in order, so phrases can be found across the separators.
  const wordAt: number[] = []
  tokens.forEach((tok, ti) => { if (tok && IS_WORD.test(tok)) wordAt.push(ti) })
  const keys = wordAt.map((ti) => tokens[ti].toLowerCase())
  const joinable = (i: number) => {
    const between = tokens.slice(wordAt[i] + 1, wordAt[i + 1]).join('')
    return PHRASE_GAP.test(between)
  }
  const spans = spanIndex(findPhraseSpans(keys, phrases, joinable))
  const tokenSpan = new Map<number, ReturnType<typeof spans.get>>()
  spans.forEach((span, wi) => {
    // Every token from the first word to the last word of the phrase, separators included.
    for (let ti = wordAt[span.start]; ti < wordAt[span.end - 1] + 1; ti++) tokenSpan.set(ti, span)
    tokenSpan.set(wordAt[wi], span)
  })

  return tokens.map((tok, ti) => {
    if (!tok) return null
    const key = `${keyPrefix}${ti}`
    const span = tokenSpan.get(ti)
    const phraseClass = span ? ` ${styles.phrase}` : ''
    if (!IS_WORD.test(tok)) return <span key={key} className={phraseClass || undefined}>{tok}</span>

    const lower = tok.toLowerCase()
    const entry = dictionary[lower]
    const near = entry ? undefined : similar[lower]
    const status = glossStatus(entry, near)
    const tint = status ? styles[status] : undefined

    const hoverable = entry || near || span
    return (
      <span
        key={key}
        className={`${styles.word}${tint ? ` ${tint}` : ''}${phraseClass}`}
        onMouseEnter={
          hoverable
            ? (e: MouseEvent<HTMLSpanElement>) =>
                onGloss({
                  word: tok, entry, similar: near,
                  phrase: span ? phraseGloss(span.entry, dictionary) : undefined,
                  x: e.clientX, y: e.clientY,
                })
            : undefined
        }
        onMouseLeave={hoverable ? () => onGloss(null) : undefined}
      >
        {tok}
      </span>
    )
  })
}

/** The floating gloss. One instance for the page, following the cursor. */
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

/** Explains the word tints. */
export function GlossLegend() {
  return (
    <Group gap="md" mt="xs">
      <Text size="xs" c="dimmed">
        <span className={styles.swatch} style={{ background: '#d3f9d8' }} />
        in dictionary, translated
      </Text>
      <Text size="xs" c="dimmed">
        <span className={styles.swatch} style={{ background: '#ffdeeb' }} />
        in dictionary, no translation
      </Text>
      <Text size="xs" c="dimmed">
        <span className={styles.swatch} style={{ background: '#fff3bf' }} />
        similar entries exist
      </Text>
      <Text size="xs" c="dimmed">
        <span className={styles.swatch} style={{ background: 'transparent', border: '1px solid #ced4da' }} />
        not in dictionary
      </Text>
      <Text size="xs" c="dimmed">
        <span className={styles.swatch} style={{ background: 'transparent', borderBottom: '2px solid #7950f2', borderRadius: 0, height: 8 }} />
        dictionary phrase
      </Text>
    </Group>
  )
}
