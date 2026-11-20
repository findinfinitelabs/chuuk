/**
 * wordAlign.ts — pairs the words of a Chuukese sentence with the words of its
 * English rendering through the dictionary: each Chuukese word the dictionary
 * holds is looked up, the English words of its gloss are matched (by a light
 * stem) against the English text, and each match becomes a numbered pair.
 * Pages colour both sides of a pair alike. Purely lexical: no model, no
 * network, and a word is paired at most once on each side.
 */

/** Same split as GlossedWords, so word ordinals line up with its spans. */
export const WORD_TOKENS = /([^\p{L}\p{N}]+)/u
const IS_WORD = /^[\p{L}\p{N}]+$/u

const EN_STOP = new Set(
  'the a an of to in on at by for with and or but as is are was were be been am do does did has have had he she it they them his her its their we us our you your i me my this that these those there here who which what when not no so if then than too very can could will would shall should may might must also just'.split(' '),
)

/** Strip common English endings so "loved" meets "love" and "thoughts" meets "thought". */
export function stem(word: string): string {
  let w = word.toLowerCase().normalize('NFD').replace(/\p{M}/gu, '').replace(/[’']s$/u, '')
  for (const end of ['ingly', 'edly', 'ness', 'ing', 'ed', 'es', 'ly', 's']) {
    if (w.length > end.length + 3 && w.endsWith(end)) { w = w.slice(0, -end.length); break }
  }
  return w.replace(/ie$/, 'y')
}

export interface Alignment {
  /** Pair id per Chuukese word ordinal (undefined when unpaired). */
  chk: (number | undefined)[]
  /** Pair id per English word ordinal. */
  en: (number | undefined)[]
  /** How many pairs were made. */
  pairs: number
}

/** Words of `text` in order, as GlossedWords counts them. */
export function words(text: string): string[] {
  return text.split(WORD_TOKENS).filter((t) => t && IS_WORD.test(t))
}

/** The English words a dictionary gloss offers, best first: content words of
 *  each alternative ("after; afterwards; later" → after, afterwards, later). */
function glossWords(english: string): string[] {
  const out: string[] = []
  for (const alt of english.split(/[;,/]|\bor\b/)) {
    for (const w of words(alt.replace(/\(.*?\)/g, ''))) {
      const lw = w.toLowerCase()
      if (!EN_STOP.has(lw) && lw.length >= 2 && !out.includes(lw)) out.push(lw)
    }
  }
  return out
}

export function alignWords(chkText: string, enText: string, dictionary: Record<string, { english?: string }>): Alignment {
  const chk = words(chkText)
  const en = words(enText)
  const enStems = en.map(stem)
  const enUsed = new Array<boolean>(en.length).fill(false)
  const out: Alignment = { chk: new Array(chk.length).fill(undefined), en: new Array(en.length).fill(undefined), pairs: 0 }

  chk.forEach((w, ci) => {
    const entry = dictionary[w.toLowerCase()]
    if (!entry?.english) return
    const candidates = glossWords(entry.english).map(stem)
    if (!candidates.length) return
    // Prefer the unused English word nearest the same relative position.
    const target = (ci / Math.max(1, chk.length)) * en.length
    let best = -1, bestRank = Infinity
    candidates.forEach((c, rank) => {
      enStems.forEach((s, ei) => {
        if (enUsed[ei] || EN_STOP.has(en[ei].toLowerCase())) return
        // Equal stems, or one the other's start within three letters (love / loved, thought / thoughts).
        const hit = s === c || (Math.min(s.length, c.length) >= 4 && Math.abs(s.length - c.length) <= 3 && (s.startsWith(c) || c.startsWith(s)))
        if (!hit) return
        const score = rank * 100 + Math.abs(ei - target)
        if (score < bestRank) { bestRank = score; best = ei }
      })
    })
    if (best >= 0) {
      enUsed[best] = true
      out.chk[ci] = out.pairs
      out.en[best] = out.pairs
      out.pairs += 1
    }
  })
  return out
}

/** Pastel tints that read in light and dark themes (alpha keeps the text legible). */
export const PAIR_COLORS = [
  'rgba(255, 183, 77, 0.45)',   // peach
  'rgba(129, 199, 132, 0.45)',  // mint
  'rgba(100, 181, 246, 0.45)',  // sky
  'rgba(240, 98, 146, 0.40)',   // rose
  'rgba(186, 104, 200, 0.40)',  // lavender
  'rgba(255, 241, 118, 0.60)',  // lemon
  'rgba(77, 208, 225, 0.45)',   // aqua
  'rgba(161, 136, 127, 0.45)',  // sand
]
export const pairColor = (pair: number) => PAIR_COLORS[pair % PAIR_COLORS.length]
