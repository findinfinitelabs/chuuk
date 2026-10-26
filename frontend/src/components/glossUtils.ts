/**
 * Helpers shared by the gloss rendering and the Translation Game modal: how a
 * word is tinted, and where multi-word dictionary phrases occur in a run of
 * words. Kept apart from GlossedText.tsx so that file exports only components.
 */
import type { DictEntry, Dictionary, Gloss, SimilarWord } from './GlossedText'

export type GlossStatus = 'translated' | 'untranslated' | 'similar' | null

export function glossStatus(entry: DictEntry | undefined, near: SimilarWord[] | undefined): GlossStatus {
  if (entry) return entry.status
  if (near && near.length > 0) return 'similar'
  return null
}

/** Mantine colour matching each tint, for places that render chips not text. */
export const GLOSS_COLOR: Record<Exclude<GlossStatus, null>, string> = {
  translated: 'green',
  untranslated: 'pink',
  similar: 'yellow',
}

/** A multi-word dictionary headword ("ewe Kot"), keyed by its lowercase words. */
export interface PhraseEntry {
  text: string
  words: string[]
  english: string
  grammar: string
  definition: string
}

export type PhraseMap = Record<string, PhraseEntry>

/** A phrase found in a sequence of word keys: words [start, end). */
export interface PhraseSpan {
  start: number
  end: number
  key: string
  entry: PhraseEntry
}

/** Where the phrases of `phrases` occur in `keys` (lowercase word keys, in
 *  order). `joinable(i)` says whether word i may run on into word i+1; a
 *  sentence boundary between them breaks a phrase. Longest match wins and
 *  spans never overlap. */
export function findPhraseSpans(
  keys: string[], phrases: PhraseMap, joinable: (i: number) => boolean = () => true,
): PhraseSpan[] {
  const byFirst = new Map<string, PhraseEntry[]>()
  Object.values(phrases).forEach((entry) => {
    const list = byFirst.get(entry.words[0]) || []
    list.push(entry)
    byFirst.set(entry.words[0], list)
  })
  byFirst.forEach((list) => list.sort((a, b) => b.words.length - a.words.length))

  const spans: PhraseSpan[] = []
  let i = 0
  while (i < keys.length) {
    const candidates = byFirst.get(keys[i]) || []
    const hit = candidates.find((entry) =>
      entry.words.every((w, k) => keys[i + k] === w && (k === 0 || joinable(i + k - 1))),
    )
    if (hit) {
      spans.push({ start: i, end: i + hit.words.length, key: hit.words.join(' '), entry: hit })
      i += hit.words.length
    } else {
      i += 1
    }
  }
  return spans
}

/** Word index → the span covering it, for quick lookup while rendering. */
export function spanIndex(spans: PhraseSpan[]): Map<number, PhraseSpan> {
  const map = new Map<number, PhraseSpan>()
  spans.forEach((s) => { for (let i = s.start; i < s.end; i++) map.set(i, s) })
  return map
}

/** The per-word glosses of a phrase, from the dictionary map. */
export function phraseGloss(entry: PhraseEntry, dictionary: Dictionary): Gloss['phrase'] {
  const words = entry.text.split(/[\s\-\u2011]+/).filter(Boolean)
  return {
    entry,
    words: words.map((word) => ({ word, entry: dictionary[word.toLowerCase()] })),
  }
}
