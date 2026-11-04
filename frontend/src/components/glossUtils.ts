/**
 * Helpers shared by the gloss rendering and the Translation Game modal: how a
 * word is tinted, and where multi-word dictionary phrases occur in a run of
 * words. Kept apart from GlossedText.tsx so that file exports only components.
 */
import type { DictEntry, Dictionary, Gloss, SimilarWord } from './GlossedText'

export type GlossStatus = 'translated' | 'untranslated' | 'accent' | 'similar' | null

export function glossStatus(entry: DictEntry | undefined, near: SimilarWord[] | undefined): GlossStatus {
  // Held under a different accent spelling: known, but worth flagging.
  if (entry?.variant_of) return 'accent'
  if (entry) return entry.status
  if (near && near.length > 0) return 'similar'
  return null
}

/** Mantine colour matching each tint, for places that render chips not text. */
export const GLOSS_COLOR: Record<Exclude<GlossStatus, null>, string> = {
  translated: 'green',
  untranslated: 'pink',
  accent: 'blue',
  similar: 'yellow',
}

/** A multi-word dictionary headword ("ewe Kot"), keyed by its lowercase words. */
export interface PhraseEntry {
  text: string
  words: string[]
  english: string
  grammar: string
  definition: string
  /** "library": a phrase recorded in the phrase library; "grammar": consecutive
   *  dictionary words whose parts of speech form a phrase (pronoun + noun…). */
  kind?: 'library' | 'grammar'
}

export type PhraseMap = Record<string, PhraseEntry>

/** Lowercase with accents and hyphens stripped: the key phrase words are
 *  indexed under on the server, so "múrinné" and "murinne" match. */
export function normKey(word: string): string {
  return word.toLowerCase().replace(/-/g, '').normalize('NFD').replace(/\p{M}/gu, '')
}

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

// ── Grammatical phrases ───────────────────────────────────────────────────────

/** Part-of-speech sequences that read as one phrase in Chuukese, longest first.
 *  Labels are the first word of the dictionary's `grammar` field. */
export const GRAMMAR_PATTERNS: string[][] = [
  ['preposition', 'article', 'noun'], ['article', 'noun', 'adjective'], ['pronoun', 'verb', 'noun'], ['noun', 'verb', 'noun'],
  ['possessive', 'noun', 'adjective'], ['demonstrative', 'noun', 'adjective'],
  ['pronoun', 'noun'], ['possessive', 'noun'], ['classifier', 'noun'], ['article', 'noun'], ['demonstrative', 'noun'], ['noun', 'demonstrative'],
  ['adjective', 'noun'], ['noun', 'adjective'], ['number', 'noun'], ['numeral', 'noun'], ['quantifier', 'noun'],
  ['preposition', 'noun'], ['preposition', 'pronoun'], ['pronoun', 'verb'], ['noun', 'verb'], ['verb', 'noun'], ['verb', 'adverb'], ['adverb', 'verb'], ['auxiliary', 'verb'],
]

export function posOf(entry: DictEntry | undefined): string {
  return (entry?.grammar || '').trim().toLowerCase().split(/[\s(/,]+/)[0] || ''
}

/** Phrases formed by the parts of speech of consecutive dictionary words, in
 *  the gaps left by the library phrases (`taken`: word indexes already in a
 *  span). `words` are the words as written, `keys` their lowercase forms. */
export function grammarPhraseSpans(
  words: string[], keys: string[], dictionary: Dictionary, taken: Set<number>, joinable: (i: number) => boolean = () => true,
): PhraseSpan[] {
  const pos = keys.map((k) => posOf(dictionary[k]))
  const spans: PhraseSpan[] = []
  let i = 0
  while (i < keys.length) {
    if (taken.has(i) || !pos[i]) { i += 1; continue }
    const hit = GRAMMAR_PATTERNS.find((pat) => pat.every((label, k) => pos[i + k] === label && !taken.has(i + k) && (k === 0 || joinable(i + k - 1))))
    if (!hit) { i += 1; continue }
    const n = hit.length
    const text = words.slice(i, i + n).join(' ')
    const entry: PhraseEntry = {
      text, words: keys.slice(i, i + n), kind: 'grammar',
      english: keys.slice(i, i + n).map((k) => dictionary[k]?.english || '…').join(' '),
      grammar: hit.join(' + '), definition: '',
    }
    spans.push({ start: i, end: i + n, key: `${text.toLowerCase()}#grammar`, entry })
    i += n
  }
  return spans
}
