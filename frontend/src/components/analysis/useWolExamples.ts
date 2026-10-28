/**
 * useWolExamples — sentences from wol.jw.org containing a word, each with its
 * English equivalent. Two requests: the search (one page, trimmed to a few
 * results), then the English for those results, which fills in after the
 * Chuukese is shown — the same shape the Watchtower Library page uses.
 */
import { useEffect, useRef, useState } from 'react'
import axios from 'axios'

interface Segment { text: string; match: boolean }

export interface WolEnglish {
  text: string
  scope: 'sentence' | 'paragraph' | 'verse'
  title: string | null
  citation: string | null
  publication: string | null
  link: string
}

export interface WolExample {
  text: string
  segments: Segment[]
  title: string | null
  link: string | null
  docId?: string | null
  verseIds?: string[]
  citation: string | null
  reference: { year: number | null; pub: string | null }
  /** undefined while loading, null when WOL has no English for it. */
  english?: WolEnglish | null
}

interface Loaded {
  word: string
  items: WolExample[]
  total: number
  error: string
}

function errorMessage(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) return e.response?.data?.error || fallback
  return fallback
}

export function useWolExamples(word: string | null, limit = 6) {
  // State is keyed by the word it was fetched for, so a change of word reads
  // as "loading" until the new results land — no reset inside the effect.
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const run = useRef(0)

  useEffect(() => {
    if (!word) return
    const mine = ++run.current
    ;(async () => {
      let results: WolExample[]
      let total: number
      try {
        const res = await axios.post('/api/wol/search', { query: word, pages: 1, limit, sort: 'newest', dictionary: false })
        if (mine !== run.current) return
        results = res.data?.results || []
        total = res.data?.totalFound || results.length
        setLoaded({ word, items: results, total, error: '' })
      } catch (e) {
        if (mine !== run.current) return
        setLoaded({ word, items: [], total: 0, error: errorMessage(e, 'Could not reach wol.jw.org') })
        return
      }
      if (!results.length) return
      let english: (WolEnglish | null)[] = results.map(() => null)
      try {
        const en = await axios.post('/api/wol/english', { items: results })
        english = en.data?.english || english
      } catch {
        // Leave the cards reading "no English" rather than failing the drawer.
      }
      if (mine !== run.current) return
      setLoaded({ word, items: results.map((r, i) => ({ ...r, english: english[i] ?? null })), total, error: '' })
    })()
  }, [word, limit])

  const current = word && loaded?.word === word ? loaded : null
  return {
    items: current?.items ?? [],
    total: current?.total ?? 0,
    error: current?.error ?? '',
    loading: !!word && !current,
  }
}
