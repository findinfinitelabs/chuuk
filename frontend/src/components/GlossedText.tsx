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

/** A dictionary entry for one Chuukese word, keyed by its lowercase form. */
export interface DictEntry {
  english: string
  grammar: string
  grammar_modifier: string | null
  definition: string
  status: 'translated' | 'untranslated'
}

export type Dictionary = Record<string, DictEntry>

/** A dictionary word that looks related to one we don't hold. */
export interface SimilarWord {
  word: string
  english: string
}

/** Related words for each unknown word, already in alphabetical order. */
export type SimilarMap = Record<string, SimilarWord[]>

/** What the floating gloss is currently describing: either a dictionary entry
 *  or, for an unknown word, the related entries we do hold. */
export interface Gloss {
  word: string
  entry?: DictEntry
  similar?: SimilarWord[]
  x: number
  y: number
}

/** Splits on non-letters, keeping the separators so the text rebuilds exactly.
 *  Mirrors the backend's `[^\W\d_]+`, so both sides agree on what a word is. */
const TOKENS = /([^\p{L}]+)/u
const IS_WORD = /^\p{L}+$/u

/** Every word of `text` tinted by dictionary status; hovering a known or
 *  near-known word reports a Gloss through `onGloss` (null on leave). */
export function GlossedWords({
  text, dictionary, similar, onGloss, keyPrefix = '',
}: {
  text: string
  dictionary: Dictionary
  similar: SimilarMap
  onGloss: (g: Gloss | null) => void
  keyPrefix?: string
}): ReactNode {
  return text.split(TOKENS).map((tok, ti) => {
    if (!tok) return null
    const key = `${keyPrefix}${ti}`
    if (!IS_WORD.test(tok)) return <span key={key}>{tok}</span>

    const lower = tok.toLowerCase()
    const entry = dictionary[lower]
    const near = entry ? undefined : similar[lower]
    const tint = entry
      ? entry.status === 'translated'
        ? styles.translated
        : styles.untranslated
      : near
        ? styles.similar
        : undefined

    const hoverable = entry || near
    return (
      <span
        key={key}
        className={`${styles.word}${tint ? ` ${tint}` : ''}`}
        onMouseEnter={
          hoverable
            ? (e: MouseEvent<HTMLSpanElement>) =>
                onGloss({ word: tok, entry, similar: near, x: e.clientX, y: e.clientY })
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
  const top = Math.min(gloss.y + 18, window.innerHeight - 160)
  const { entry, similar } = gloss

  return (
    <div className={styles.gloss} style={{ left, top }}>
      <div className={styles.glossWord}>{gloss.word}</div>

      {entry ? (
        <>
          {entry.status === 'translated' ? (
            <div className={styles.glossEnglish}>{entry.english}</div>
          ) : (
            <div className={styles.glossMeta}>In the dictionary — no English translation yet</div>
          )}
          {(entry.grammar || entry.definition) && (
            <div className={styles.glossMeta}>
              {entry.grammar}
              {entry.grammar && entry.definition ? ' · ' : ''}
              {entry.definition}
            </div>
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
    </Group>
  )
}
