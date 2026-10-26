import { useState, useEffect, useRef, useCallback } from 'react'
import { Card, Title, Text, Button, Group, Stack, Badge, Alert, ScrollArea, Paper, Textarea, Modal, TextInput, ActionIcon, CopyButton, Tooltip, Divider, Loader, Tabs, Switch, Box, NavLink as MantineNavLink } from '@mantine/core'
import { IconTrophy, IconTarget, IconRefresh, IconCheck, IconX, IconWorld, IconCopy, IconLink, IconUnlink, IconPencil, IconEye, IconEdit, IconHistory, IconTrash } from '@tabler/icons-react'
import MarkdownIt from 'markdown-it'
import { notifications } from '@mantine/notifications'
import axios from 'axios'
import './TranslationGame.css'
import { GlossedWords, GlossCard, GlossLegend } from '../components/GlossedText'
import { findPhraseSpans, glossStatus, GLOSS_COLOR, phraseGloss, spanIndex } from '../components/glossUtils'
import type { PhraseMap } from '../components/glossUtils'
import type { Dictionary, SimilarMap, Gloss } from '../components/GlossedText'

interface Sentence {
  id: number
  text: string
  editedText?: string
  paragraph_index?: number
  /** wol.jw.org paragraph id — shared by the English and Chuukese editions. */
  pid?: string | null
  sentence_index?: number
  sentence_count?: number
  is_scripture_ref?: boolean
}

/** Clue for one English sentence: the Chuukese sentences in the same paragraph,
 *  and which of those the server thinks are its translation. */
interface Hint {
  paragraph: number[]
  likely: number[]
}

interface Match {
  englishId: number
  chuukeseIds: number[]  // Changed to array to support multiple Chuukese sentences
  editedEnglishText?: string
  savedWordPairs?: WordPair[]
}

interface WordSuggestion {
  chuukese: string
  helsinki_translation: string
  matched_english_words: string[]
  grammar_suggestion: string
  in_dictionary: boolean
  confidence: 'high' | 'low'
}

interface WordPair {
  id: string
  englishIndices: number[]
  chuukeseIndices: number[]
  englishWords: string[]
  chuukeseWords: string[]
  grammar: string
  color: string
  description: string
  inDatabase: boolean
  /** Proposed from a related entry, an identical token or a number rather than
   *  an exact dictionary hit; the user decides whether it stands. */
  fuzzy?: boolean
  /** The dictionary word a fuzzy proposal was based on. */
  baseWord?: string
  source?: 'dictionary' | 'similar' | 'number' | 'identical' | 'manual'
}

/** One row in the saved-article sidebar. */
interface SavedArticle {
  id: string
  english_title: string | null
  chuukese_title: string | null
  english_url: string
  chuukese_url: string
  english_count: number
  chuukese_count: number
  match_count: number
  updated_at?: string
  created_by?: string
}

/** A match as stored by the server, returned when a saved article is reopened. */
interface SavedMatch {
  english_id: number
  chuukese_ids: number[]
  english_text: string | null
  was_edited: boolean
  word_pairs: WordPair[]
}

const _md = new MarkdownIt()

/** Articles already fetched for the game. Reopening one costs a single
 *  database read instead of two round trips to wol.jw.org, and restores the
 *  matches made on it. */
function ArticleSidebar({
  saved, activeId, loading, error, onSelect, onDelete,
}: {
  saved: SavedArticle[]
  activeId: string | null
  loading: boolean
  error: string
  onSelect: (a: SavedArticle) => void
  onDelete: (id: string) => void
}) {
  return (
    <Box style={{ width: 250, flexShrink: 0 }}>
      <Paper withBorder radius="md" p="sm" style={{ position: 'sticky', top: 16 }}>
        <Group gap={6} mb="sm">
          <IconHistory size={16} color="#7c55de" />
          <Text size="sm" fw={700} c="violet.8">Saved Articles</Text>
          {loading && <Loader size="xs" style={{ marginLeft: 'auto' }} />}
        </Group>
        <Divider mb="sm" />
        {error && <Text size="xs" c="red" mb="xs">{error}</Text>}
        <ScrollArea h={520} type="auto">
          {saved.length === 0 && !loading && (
            <Text size="xs" c="dimmed" ta="center" py="md">
              Articles you load are saved here automatically, with your matches.
            </Text>
          )}
          {saved.map((item) => {
            const done = item.english_count > 0 && item.match_count >= item.english_count
            return (
              <Box key={item.id} mb={4} style={{ position: 'relative' }}>
                <MantineNavLink
                  label={
                    <Stack gap={2}>
                      <Text size="xs" fw={700} lineClamp={2} c={activeId === item.id ? 'violet.9' : undefined}>
                        {item.english_title || item.english_url}
                      </Text>
                      {item.chuukese_title && (
                        <Text size="xs" c="dimmed" lineClamp={1}>{item.chuukese_title}</Text>
                      )}
                      <Group gap={4} mt={2}>
                        <Badge size="xs" variant="light" color="blue">{item.english_count} EN</Badge>
                        <Badge size="xs" variant="light" color="green">{item.chuukese_count} CHK</Badge>
                        <Badge size="xs" variant={done ? 'filled' : 'light'} color={done ? 'teal' : 'orange'}>
                          {item.match_count} matched
                        </Badge>
                      </Group>
                      {item.updated_at && (
                        <Text size="xs" c="dimmed">{new Date(item.updated_at).toLocaleDateString()}</Text>
                      )}
                    </Stack>
                  }
                  active={activeId === item.id}
                  onClick={() => onSelect(item)}
                  style={{ borderRadius: 6, paddingRight: 30 }}
                />
                <ActionIcon
                  size="xs"
                  color="red"
                  variant="subtle"
                  style={{ position: 'absolute', top: 8, right: 4 }}
                  onClick={(e) => { e.stopPropagation(); onDelete(item.id) }}
                  aria-label={`Remove saved article ${item.english_title || item.english_url}`}
                >
                  <IconTrash size={12} />
                </ActionIcon>
              </Box>
            )
          })}
        </ScrollArea>
      </Paper>
    </Box>
  )
}

const PAIR_COLORS = ['green', 'blue', 'orange', 'violet', 'teal', 'red', 'cyan', 'pink', 'grape', 'yellow']

/** A reference tail: an em/en dash after the sentence's closing punctuation,
 *  then a publication or scripture citation ("now?—w24.05 17 ¶10.",
 *  "manaw.—Jer 48:27, 29."). Inside a sentence a dash sits between words,
 *  so this never cuts a parenthetical aside. */
const REF_TAIL = /(?<=[.?!”’'")\]])\s*[—–]\s*(?=[\p{L}\p{N}¶(]).*$/u
/** A parenthesised citation: verses ("(Jon 3:16)") or a publication ("(w24.05 17)"). */
const PAREN_REF = /\((?:[^()]*\d+:\d+[^()]*|\s*(?:w|g|mwb|wp|km|bt|lff|lfb|ijwbq|od|jy|rr|lvs|cl|kr|ws)\d{2}(?:\.\d{2})?[^()]*)\)/giu

/** The sentence body and the references it carried, kept apart so a citation
 *  never blends into a word chip ("IEI?—w24.05"). */
function splitReferences(text: string): { body: string; refs: string[] } {
  const refs: string[] = []
  let body = text.replace(REF_TAIL, (m) => { refs.push(m.trim()); return '' })
  body = body.replace(PAREN_REF, (m) => { refs.push(m.trim()); return ' ' })
  return { body: body.replace(/\s+/g, ' ').trim(), refs }
}

/** The word chips of a sentence: references removed, dashes split off, and
 *  chips with no letter or digit dropped. */
function tokenize(text: string): string[] {
  return splitReferences(text).body
    .replace(/[—–]/g, ' — ')
    .split(/\s+/)
    .filter((t) => /[\p{L}\p{N}]/u.test(t))
}

/** Saved pairs point at chip positions; after the chips of a sentence change
 *  (a reference split off, text edited) find each pair's words again. A pair
 *  whose words are gone keeps its old positions. */
function realignPairs(pairs: WordPair[], enTokens: string[], chkTokens: string[]): WordPair[] {
  const enKeys = enTokens.map(tokenKey)
  const chkKeys = chkTokens.map(tokenKey)
  const usedEn = new Set<number>()
  const usedChk = new Set<number>()
  const locate = (words: string[], keys: string[], used: Set<number>): number[] | null => {
    const wanted = words.map((w) => w.toLowerCase())
    for (let i = 0; i + wanted.length <= keys.length; i++) {
      const run = Array.from({ length: wanted.length }, (_, k) => i + k)
      if (run.every((idx) => !used.has(idx) && keys[idx] === wanted[idx - i])) {
        run.forEach((idx) => used.add(idx))
        return run
      }
    }
    return null
  }
  return pairs.map((p) => {
    const en = locate(p.englishWords, enKeys, usedEn)
    const chk = locate(p.chuukeseWords, chkKeys, usedChk)
    return { ...p, englishIndices: en ?? p.englishIndices, chuukeseIndices: chk ?? p.chuukeseIndices }
  })
}

/** A token without its surrounding punctuation: 'Jeremaia,' → 'Jeremaia'. */
const stripToken = (t: string) => t.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '')
/** The key a token is looked up by in the dictionary maps. */
const tokenKey = (t: string) => stripToken(t).toLowerCase()
const isNumber = (t: string) => /^\p{N}+$/u.test(t)

/** English function words that never identify a translation on their own. */
const EN_STOPWORDS = new Set([
  'the', 'a', 'an', 'to', 'of', 'in', 'on', 'at', 'and', 'or', 'is', 'are', 'be', 'was', 'were',
  'it', 'its', 'for', 'with', 'by', 'as', 'that', 'this', 'his', 'her', 'their', 'our', 'your',
  'my', 'he', 'she', 'they', 'we', 'you', 'i', 'not', 'do', 'does', 'did', 'have', 'has', 'had',
  'will', 'would', 'can', 'could', 'from', 'but', 'so', 'if', 'one', 'someone', 'something',
])

/** Crude stem so 'loves' meets 'love' and 'walking' meets 'walk'. */
function stem(word: string): string {
  const w = word.toLowerCase()
  if (w.length > 5 && w.endsWith('ing')) return w.slice(0, -3)
  if (w.length > 4 && w.endsWith('ed')) return w.slice(0, -2)
  if (w.length > 3 && w.endsWith('es')) return w.slice(0, -2)
  if (w.length > 3 && w.endsWith('s')) return w.slice(0, -1)
  return w
}

/** 'loved' and 'love' are the same word for pairing purposes: equal stems, or
 *  one is a prefix of the other once both are at least four letters. */
function sameWord(a: string, b: string): boolean {
  if (a === b) return true
  const sa = stem(a), sb = stem(b)
  if (sa === sb) return true
  if (a.length >= 4 && b.length >= 4) return sa.startsWith(sb) || sb.startsWith(sa)
  return false
}

/** The senses of a dictionary wording, each as its words: 'to love; love of'
 *  → [['love'], ['love', 'of']] with stopwords kept, [['love'], ['love']] without. */
function senseWords(english: string, keepStopwords = false): string[][] {
  return english
    .split(/[;/]/)
    .map((sense) =>
      sense
        .replace(/\(.*?\)/g, ' ')
        .replace(/^\s*to\s+/i, '')
        .split(/[\s,]+/)
        .map((w) => stripToken(w).toLowerCase())
        .filter((w) => w && (keepStopwords || !EN_STOPWORDS.has(w))),
    )
    .filter((words) => words.length > 0)
}

/** Unused indices where `words` occur in order as a run, or []. */
function findRun(words: string[], enKeys: string[], used: Set<number>): number[] {
  for (let i = 0; i + words.length <= enKeys.length; i++) {
    const run = Array.from({ length: words.length }, (_, k) => i + k)
    if (run.every((idx) => !used.has(idx) && sameWord(enKeys[idx], words[idx - i]))) return run
  }
  return []
}

/** English token indices that express `english`: the whole sense as written
 *  ("the God"), then its content words as a run, then any single content
 *  word. Only unused indices are considered. */
function findEnglish(english: string, enKeys: string[], used: Set<number>): number[] {
  for (const words of senseWords(english, true)) {
    if (words.length > 1) {
      const run = findRun(words, enKeys, used)
      if (run.length > 0) return run
    }
  }
  for (const words of senseWords(english)) {
    if (words.length > 1) {
      const run = findRun(words, enKeys, used)
      if (run.length > 0) return run
    }
    for (const w of words) {
      if (w.length < 3) continue
      const idx = enKeys.findIndex((k, i) => !used.has(i) && sameWord(k, w))
      if (idx >= 0) return [idx]
    }
  }
  return []
}

/** Dictionary phrases among whitespace-split Chuukese tokens. A token ending
 *  in sentence punctuation ("ewe.") cannot run on into the next. */
function chkPhraseSpans(chkTokens: string[], phrases: PhraseMap) {
  const keys = chkTokens.map(tokenKey)
  const joinable = (i: number) => !/[.;:!?]["'”’)]*$/.test(chkTokens[i])
  return findPhraseSpans(keys, phrases, joinable)
}

/** The colour and number a confirmed sentence match is shown with, on both
 *  the English card and its Chuukese card(s). */
function matchBadge(matches: Match[], predicate: (m: Match) => boolean): { color: string; n: number } | null {
  const i = matches.findIndex(predicate)
  return i < 0 ? null : { color: PAIR_COLORS[i % PAIR_COLORS.length], n: i + 1 }
}

/** Word pairs the game can propose before the user links anything: exact
 *  dictionary entries, fuzzy hits through a related entry (same base word),
 *  identical tokens such as names, and numbers. */
function proposePairs(
  enTokens: string[], chkTokens: string[], dictionary: Dictionary, similar: SimilarMap, phrases: PhraseMap = {},
): WordPair[] {
  const enKeys = enTokens.map(tokenKey)
  const usedEn = new Set<number>()
  const usedChk = new Set<number>()
  const pairs: WordPair[] = []

  const add = (chkIdx: number[], enIdx: number[], extra: Partial<WordPair>) => {
    enIdx.forEach((i) => usedEn.add(i))
    chkIdx.forEach((i) => usedChk.add(i))
    pairs.push({
      id: `auto_${chkIdx.join('-')}_${enIdx.join('-')}`,
      englishIndices: enIdx,
      chuukeseIndices: chkIdx,
      englishWords: enIdx.map((i) => stripToken(enTokens[i])),
      chuukeseWords: chkIdx.map((i) => stripToken(chkTokens[i])),
      grammar: 'noun',
      color: PAIR_COLORS[pairs.length % PAIR_COLORS.length],
      description: '',
      inDatabase: false,
      ...extra,
    })
  }

  // Dictionary phrases first ("ewe Kot" ↔ "the God"): both words make one pair.
  chkPhraseSpans(chkTokens, phrases).forEach((span) => {
    if (!span.entry.english) return
    const idx = findEnglish(span.entry.english, enKeys, usedEn)
    if (idx.length > 0) {
      const chkIdx = Array.from({ length: span.end - span.start }, (_, k) => span.start + k)
      add(chkIdx, idx, {
        grammar: span.entry.grammar || 'phrase', description: span.entry.definition,
        inDatabase: true, source: 'dictionary',
      })
    }
  })

  chkTokens.forEach((raw, chkIdx) => {
    const key = tokenKey(raw)
    if (!key || usedChk.has(chkIdx)) return

    if (isNumber(key)) {
      const idx = enKeys.findIndex((k, i) => !usedEn.has(i) && k === key)
      if (idx >= 0) add([chkIdx], [idx], { grammar: 'number', source: 'number' })
      return
    }

    const entry = dictionary[key]
    if (entry?.english) {
      const idx = findEnglish(entry.english, enKeys, usedEn)
      if (idx.length > 0) {
        add([chkIdx], idx, {
          grammar: entry.grammar || 'noun', description: entry.definition,
          inDatabase: true, source: 'dictionary',
        })
      }
      return
    }

    for (const near of similar[key] || []) {
      if (!near.english) continue
      const idx = findEnglish(near.english, enKeys, usedEn)
      if (idx.length > 0) {
        add([chkIdx], idx, { grammar: near.grammar || 'noun', fuzzy: true, baseWord: near.word, source: 'similar' })
        return
      }
    }

    // A name spelled the same in both languages.
    if (key.length >= 3) {
      const idx = enKeys.findIndex((k, i) => !usedEn.has(i) && k === key)
      if (idx >= 0) add([chkIdx], [idx], { fuzzy: true, source: 'identical' })
    }
  })

  return pairs
}

function TranslationGame() {
  const [englishSentences, setEnglishSentences] = useState<Sentence[]>([])
  const [chuukeseSentences, setChuukeseSentences] = useState<Sentence[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedEnglish, setSelectedEnglish] = useState<number | null>(null)
  const [selectedChuukese, setSelectedChuukese] = useState<number[]>([])  // Changed to array
  const [matches, setMatches] = useState<Match[]>([])
  const [hints, setHints] = useState<Record<string, Hint>>({})
  const [showClues, setShowClues] = useState(true)
  // Word glosses for the Chuukese column (same hover as the Watchtower Library page)
  const [dictionary, setDictionary] = useState<Dictionary>({})
  const [similar, setSimilar] = useState<SimilarMap>({})
  const [phrases, setPhrases] = useState<PhraseMap>({})
  const [gloss, setGloss] = useState<Gloss | null>(null)
  const chuukeseCardRefs = useRef<Record<number, HTMLDivElement | null>>({})

  // Saved-article sidebar
  const [articleId, setArticleId] = useState<string | null>(null)
  const [saved, setSaved] = useState<SavedArticle[]>([])
  const [savedLoading, setSavedLoading] = useState(false)
  const [savedError, setSavedError] = useState('')

  const refreshSaved = useCallback(async () => {
    setSavedLoading(true)
    try {
      const res = await axios.get('/api/game/articles')
      setSaved(Array.isArray(res.data) ? res.data : [])
      setSavedError('')
    } catch {
      setSavedError('Could not load saved articles')
    } finally {
      setSavedLoading(false)
    }
  }, [])

  useEffect(() => { refreshSaved() }, [refreshSaved])
  const [score, setScore] = useState(0)
  const [totalAttempts, setTotalAttempts] = useState(0)
  const [correctMatches, setCorrectMatches] = useState(0)
  
  // URL input
  const [englishUrl, setEnglishUrl] = useState('')
  const [chuukeseUrl, setChuukeseUrl] = useState('')
  const [articleTitle, setArticleTitle] = useState('')
  
  // Edit modal state
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editingEnglishId, setEditingEnglishId] = useState<number | null>(null)
  const [editedText, setEditedText] = useState('')
  const [pendingChuukeseIds, setPendingChuukeseIds] = useState<number[]>([])  // Changed to array
  const [editedChuukeseTexts, setEditedChuukeseTexts] = useState<Record<number, string>>({})

  // Word-level matching state
  const [englishTokens, setEnglishTokens] = useState<string[]>([])
  const [chuukeseTokens, setChuukeseTokens] = useState<string[]>([])
  /** Citations split off the sentences, shown under the chips but never matched. */
  const [englishRefs, setEnglishRefs] = useState<string[]>([])
  const [chuukeseRefs, setChuukeseRefs] = useState<string[]>([])
  const [selEnTokens, setSelEnTokens] = useState<number[]>([])
  const [selChkTokens, setSelChkTokens] = useState<number[]>([])
  const [wordPairs, setWordPairs] = useState<WordPair[]>([])
  const [wordSuggestions, setWordSuggestions] = useState<Record<string, WordSuggestion>>({})
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [showEditTexts, setShowEditTexts] = useState(false)
  /** Set once the user links or unlinks a pair, so a late lookup result does
   *  not overwrite their work with fresh proposals. */
  const pairsTouched = useRef(false)

  /** Fold entries saved or looked up on the server into the board's gloss maps,
   *  so the next sentence with the same word shows it as known. */
  const mergeGloss = useCallback((dict: Dictionary | undefined, near: SimilarMap | undefined, found?: PhraseMap) => {
    if (found && Object.keys(found).length > 0) {
      setPhrases(prev => ({ ...prev, ...found }))
    }
    if (dict && Object.keys(dict).length > 0) {
      setDictionary(prev => ({ ...prev, ...dict }))
      setSimilar(prev => {
        const next = { ...prev }
        Object.keys(dict).forEach(k => { delete next[k] })
        return next
      })
    }
    if (near && Object.keys(near).length > 0) {
      setSimilar(prev => ({ ...near, ...prev }))
    }
  }, [])

  // Description editor modal state
  const [descModalOpen, setDescModalOpen] = useState(false)
  const [descEditingPairId, setDescEditingPairId] = useState<string | null>(null)
  const [descContent, setDescContent] = useState('')
  const [descTab, setDescTab] = useState<string | null>('write')
  const descTextareaRef = useRef<HTMLTextAreaElement>(null)
  useEffect(() => {
    loadStats()
    loadGameStateFromCache()
  }, [])

  useEffect(() => {
    // Save game state to localStorage whenever it changes
    if (englishSentences.length > 0 || chuukeseSentences.length > 0) {
      saveGameStateToCache()
    }
  }, [englishSentences, chuukeseSentences, matches, selectedEnglish, selectedChuukese, englishUrl, chuukeseUrl, articleTitle, hints, dictionary, similar, phrases, articleId])

  // Bring the first clue into view when an English sentence is picked.
  useEffect(() => {
    if (selectedEnglish === null || !showClues) return
    const hint = hints[String(selectedEnglish)]
    const target = hint?.likely[0] ?? hint?.paragraph[0]
    if (target !== undefined) {
      chuukeseCardRefs.current[target]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [selectedEnglish, hints, showClues])

  const saveGameStateToCache = () => {
    const gameState = {
      englishSentences,
      chuukeseSentences,
      matches,
      hints,
      dictionary,
      similar,
      phrases,
      articleId,
      englishUrl,
      chuukeseUrl,
      articleTitle,
      timestamp: Date.now()
    }
    localStorage.setItem('translationGameState', JSON.stringify(gameState))
  }

  const loadGameStateFromCache = () => {
    try {
      const cached = localStorage.getItem('translationGameState')
      if (cached) {
        const gameState = JSON.parse(cached)
        // Check if cache is less than 24 hours old
        const age = Date.now() - gameState.timestamp
        if (age < 24 * 60 * 60 * 1000) {
          setEnglishSentences(gameState.englishSentences || [])
          setChuukeseSentences(gameState.chuukeseSentences || [])
          setMatches(gameState.matches || [])
          setHints(gameState.hints || {})
          setDictionary(gameState.dictionary || {})
          setSimilar(gameState.similar || {})
          setPhrases(gameState.phrases || {})
          setArticleId(gameState.articleId || null)
          setEnglishUrl(gameState.englishUrl || '')
          setChuukeseUrl(gameState.chuukeseUrl || '')
          setArticleTitle(gameState.articleTitle || '')
          
          if (gameState.englishSentences?.length > 0) {
            notifications.show({
              title: 'Game State Restored',
              message: 'Your previous session has been restored',
              color: 'blue'
            })
          }
        } else {
          // Clear old cache
          localStorage.removeItem('translationGameState')
        }
      }
    } catch (error) {
      console.error('Failed to load game state from cache:', error)
    }
  }

  const clearGameState = () => {
    localStorage.removeItem('translationGameState')
    setEnglishSentences([])
    setChuukeseSentences([])
    setMatches([])
    setHints({})
    setDictionary({})
    setSimilar({})
    setPhrases({})
    setGloss(null)
    setArticleId(null)
    setSelectedEnglish(null)
    setSelectedChuukese([])
    setEnglishUrl('')
    setChuukeseUrl('')
    setArticleTitle('')
    notifications.show({
      title: 'Game Reset',
      message: 'All progress has been cleared',
      color: 'orange'
    })
  }

  const fetchFromUrl = async () => {
    if (!englishUrl.trim()) {
      notifications.show({
        title: 'Error',
        message: 'Please enter an English URL',
        color: 'red'
      })
      return
    }

    if (!chuukeseUrl.trim()) {
      notifications.show({
        title: 'Error',
        message: 'Please enter a Chuukese URL',
        color: 'red'
      })
      return
    }

    try {
      setLoading(true)
      const response = await axios.post('/api/articles/fetch', { 
        englishUrl: englishUrl,
        chuukeseUrl: chuukeseUrl 
      })
      
      setEnglishSentences(response.data.english.sentences)
      setChuukeseSentences(response.data.chuukese.sentences)
      setHints(response.data.hints || {})
      setDictionary(response.data.dictionary || {})
      setSimilar(response.data.similar || {})
      setPhrases(response.data.phrases || {})
      setArticleId(response.data.article_id || null)
      setArticleTitle(response.data.english.title)
      // An article played before comes back with the matches already made on it.
      const restored = restoreMatches(response.data.matches)
      refreshSaved()
      setSelectedEnglish(null)
      setSelectedChuukese([])
      
      notifications.show({
        title: 'Success',
        message: `Loaded: ${response.data.english.title}${restored ? ` · ${restored} saved match${restored === 1 ? '' : 'es'} restored` : ''}`,
        color: 'green'
      })
    } catch {
      notifications.show({
        title: 'Error',
        message: 'Failed to fetch article. Make sure it\'s a valid wol.jw.org URL.',
        color: 'red'
      })
    } finally {
      setLoading(false)
    }
  }

  /** Put the matches saved on the server onto the board (one per English
   *  sentence, latest wins) and return how many there are. */
  const restoreMatches = (saved: SavedMatch[] | undefined): number => {
    const restored: Match[] = (saved || [])
      .filter((m) => typeof m.english_id === 'number')
      .map((m) => ({
        englishId: m.english_id,
        chuukeseIds: m.chuukese_ids || [],
        editedEnglishText: m.was_edited && m.english_text ? m.english_text : undefined,
        savedWordPairs: m.word_pairs && m.word_pairs.length > 0 ? m.word_pairs : undefined,
      }))
    const byEnglish = new Map<number, Match>()
    restored.forEach((m) => byEnglish.set(m.englishId, m))
    const list = Array.from(byEnglish.values())
    setMatches(list)
    return list.length
  }

  /** Reopen a saved article pair, with the matches already made on it. */
  const openSaved = async (item: SavedArticle) => {
    try {
      setLoading(true)
      setGloss(null)
      const res = await axios.get(`/api/game/articles/${item.id}`)
      const data = res.data
      setEnglishSentences(data.english.sentences || [])
      setChuukeseSentences(data.chuukese.sentences || [])
      setHints(data.hints || {})
      setDictionary(data.dictionary || {})
      setSimilar(data.similar || {})
      setPhrases(data.phrases || {})
      setArticleId(data.article_id || item.id)
      setEnglishUrl(data.english.url || '')
      setChuukeseUrl(data.chuukese.url || '')
      setArticleTitle(data.english.title || '')
      const count = restoreMatches(data.matches)
      setSelectedEnglish(null)
      setSelectedChuukese([])
      notifications.show({
        title: 'Article Restored',
        message: `${data.english.title || 'Article'} · ${count} match${count === 1 ? '' : 'es'}`,
        color: 'violet'
      })
    } catch {
      notifications.show({ title: 'Error', message: 'Could not open that saved article', color: 'red' })
    } finally {
      setLoading(false)
    }
  }

  const removeSaved = async (id: string) => {
    try {
      await axios.delete(`/api/game/articles/${id}`)
      if (articleId === id) setArticleId(null)
      refreshSaved()
    } catch {
      setSavedError('Could not remove that saved article')
    }
  }

  const loadStats = async () => {
    try {
      const response = await axios.get('/api/brochures/stats')
      setScore(response.data.score)
      setCorrectMatches(response.data.correct_matches)
      setTotalAttempts(response.data.total_matches)
    } catch (error) {
      console.error('Failed to load stats:', error)
    }
  }

  const handleEnglishClick = (id: number) => {
    // If already matched, allow re-editing by removing and reopening modal
    const existingMatch = matches.find(m => m.englishId === id)
    if (existingMatch) {
      // Remove from matches so sentence is editable again
      setMatches(prev => prev.filter(m => m.englishId !== id))
      setScore(prev => Math.max(0, prev - 10))
      setCorrectMatches(prev => Math.max(0, prev - 1))
      // Reopen modal with previously saved word pairs
      openEditModal(id, existingMatch.chuukeseIds, existingMatch.savedWordPairs)
      return
    }
    
    // If this English is already selected, deselect it
    if (selectedEnglish === id) {
      setSelectedEnglish(null)
      setSelectedChuukese([])
      return
    }
    
    setSelectedEnglish(id)
    setSelectedChuukese([])  // Reset Chuukese selection when selecting new English
  }

  const handleChuukeseClick = (id: number) => {
    // If already matched, allow clicking to re-pair via the English sentence
    if (matches.some(m => m.chuukeseIds.includes(id))) return
    
    if (!selectedEnglish) {
      notifications.show({
        title: 'Select English First',
        message: 'Please select an English sentence before selecting Chuukese sentences',
        color: 'blue'
      })
      return
    }
    
    // Toggle selection
    setSelectedChuukese(prev => 
      prev.includes(id) 
        ? prev.filter(cid => cid !== id)
        : [...prev, id]
    )
  }

  const handleConfirmMatch = () => {
    if (selectedEnglish === null || selectedChuukese.length === 0) {
      notifications.show({
        title: 'Incomplete Selection',
        message: 'Please select both English and at least one Chuukese sentence',
        color: 'orange'
      })
      return
    }
    
    openEditModal(selectedEnglish, selectedChuukese)
  }

  const openEditModal = (englishId: number, chuukeseIds: number[], existingPairs?: WordPair[]) => {
    const englishSentence = englishSentences.find(s => s.id === englishId)
    if (englishSentence) {
      setEditingEnglishId(englishId)
      setPendingChuukeseIds(chuukeseIds)
      const engText = englishSentence.editedText || englishSentence.text
      setEditedText(engText)

      // Initialize edited Chuukese texts with current values
      const initialChuukeseTexts: Record<number, string> = {}
      chuukeseIds.forEach(id => {
        const sentence = chuukeseSentences.find(s => s.id === id)
        if (sentence) {
          initialChuukeseTexts[id] = sentence.editedText || sentence.text
        }
      })
      setEditedChuukeseTexts(initialChuukeseTexts)

      // Tokenize both sides: citations set aside, chips keep their punctuation
      // for display, lookups go through tokenKey.
      const enTokens = tokenize(engText)
      const chkText = Object.values(initialChuukeseTexts).join(' ')
      const chkTokens = tokenize(chkText)
      setEnglishTokens(enTokens)
      setChuukeseTokens(chkTokens)
      setEnglishRefs(splitReferences(engText).refs)
      setChuukeseRefs(splitReferences(chkText).refs)
      setSelEnTokens([])
      setSelChkTokens([])
      setWordSuggestions({})
      setShowEditTexts(false)
      setEditModalOpen(true)

      // Restore previously saved word pairs (re-edit flow), or propose pairs
      // from what the board already knows about these words.
      const restoring = !!existingPairs && existingPairs.length > 0
      pairsTouched.current = restoring
      setWordPairs(restoring ? realignPairs(existingPairs!, enTokens, chkTokens) : proposePairs(enTokens, chkTokens, dictionary, similar, phrases))

      // Fresh dictionary glosses (a word saved a moment ago must show as known)
      // and model suggestions, in parallel.
      const lookupKeys = Array.from(new Set(chkTokens.map(stripToken).filter(t => t && !isNumber(t))))
      setLoadingSuggestions(true)
      const suggestionsReq = axios.post('/api/translate/word-suggestions', {
        chuukese_tokens: lookupKeys,
        english_sentence: engText
      })
      const dbLookupReq = axios.get('/api/brochures/match/words', {
        params: { chuukese_tokens: lookupKeys.join(',') }
      })

      Promise.allSettled([suggestionsReq, dbLookupReq]).then(([suggResult, dbResult]) => {
        const map: Record<string, WordSuggestion> = {}
        if (suggResult.status === 'fulfilled') {
          suggResult.value.data.suggestions?.forEach((sg: WordSuggestion) => {
            map[tokenKey(sg.chuukese)] = sg
          })
        }

        if (dbResult.status === 'fulfilled') {
          const freshDict: Dictionary = dbResult.value.data.dictionary || {}
          const freshSimilar: SimilarMap = dbResult.value.data.similar || {}
          const freshPhrases: PhraseMap = dbResult.value.data.phrases || {}
          mergeGloss(freshDict, freshSimilar, freshPhrases)
          Object.keys(freshDict).forEach(k => {
            if (map[k]) map[k] = { ...map[k], in_dictionary: true }
          })
          if (!pairsTouched.current) {
            setWordPairs(proposePairs(
              enTokens, chkTokens, { ...dictionary, ...freshDict }, { ...freshSimilar, ...similar }, { ...phrases, ...freshPhrases },
            ))
          }
        }

        setWordSuggestions(map)
      }).finally(() => setLoadingSuggestions(false))
    }
  }

  const handleSaveEdit = async () => {
    if (editingEnglishId !== null && pendingChuukeseIds.length > 0) {
      // Update the English sentence with edited text
      setEnglishSentences(prev => 
        prev.map(s => s.id === editingEnglishId 
          ? { ...s, editedText: editedText } 
          : s
        )
      )
      
      // Update Chuukese sentences with edited texts
      setChuukeseSentences(prev =>
        prev.map(s => {
          if (editedChuukeseTexts[s.id] !== undefined) {
            return { ...s, editedText: editedChuukeseTexts[s.id] }
          }
          return s
        })
      )
      
      // Proceed with sentence match
      attemptMatch(editingEnglishId, pendingChuukeseIds, wordPairs, editedText, editedChuukeseTexts)

      // Save word pairs if any were linked (awaited so DB is updated before modal closes).
      // The server returns the refreshed entries, which go straight into the
      // board's gloss maps so the next sentence shows these words as known.
      if (wordPairs.length > 0) {
        try {
          const res = await axios.post('/api/brochures/match/words', {
            word_pairs: wordPairs.map(p => ({
              chuukese: p.chuukeseWords.map(stripToken).join(' '),
              english: p.englishWords.map(stripToken).join(' '),
              grammar: p.grammar,
              description: p.description,
            })),
            source_sentence_id: `${editingEnglishId}_${pendingChuukeseIds.join('_')}`,
            article_id: articleId,
            article_title: articleTitle,
            article_url: chuukeseUrl,
            english_text: editedText,
            chuukese_text: Object.values(editedChuukeseTexts).join(' '),
          })
          mergeGloss(res.data?.dictionary, undefined, res.data?.phrases)
        } catch {
          notifications.show({ title: 'Word pairs not saved', message: 'The sentence match was saved, but the dictionary update failed', color: 'orange' })
        }
      }
      
      setEditModalOpen(false)
      setEditingEnglishId(null)
      setPendingChuukeseIds([])
      setEditedText('')
      setEditedChuukeseTexts({})
      setWordPairs([])
      setSelEnTokens([])
      setSelChkTokens([])
    }
  }

  const toggleEnToken = (idx: number) => {
    setSelEnTokens(prev =>
      prev.includes(idx) ? prev.filter(i => i !== idx) : [...prev, idx]
    )
  }

  const toggleChkToken = (idx: number) => {
    setSelChkTokens(prev =>
      prev.includes(idx) ? prev.filter(i => i !== idx) : [...prev, idx]
    )
  }

  const linkSelectedTokens = () => {
    if (selEnTokens.length === 0 || selChkTokens.length === 0) return
    const enWords = selEnTokens.sort((a,b)=>a-b).map(i => stripToken(englishTokens[i]))
    const chkWords = selChkTokens.sort((a,b)=>a-b).map(i => stripToken(chuukeseTokens[i]))
    // Grammar: the dictionary's tag when we hold the word, else the model's guess
    const primaryKey = tokenKey(chkWords[0] || '')
    const entry = dictionary[primaryKey]
    const sugg = wordSuggestions[primaryKey]
    const grammar = entry?.grammar || sugg?.grammar_suggestion || 'noun'
    const inDatabase = !!entry
    const color = PAIR_COLORS[wordPairs.length % PAIR_COLORS.length]
    pairsTouched.current = true
    setWordPairs(prev => [...prev, {
      id: `${selEnTokens.join('-')}_${selChkTokens.join('-')}`,
      englishIndices: [...selEnTokens],
      chuukeseIndices: [...selChkTokens],
      englishWords: enWords,
      chuukeseWords: chkWords,
      grammar,
      color,
      description: entry?.definition || '',
      inDatabase,
      source: 'manual',
    }])
    setSelEnTokens([])
    setSelChkTokens([])
  }

  const openDescEditor = (pairId: string) => {
    const pair = wordPairs.find(p => p.id === pairId)
    if (!pair) return
    setDescEditingPairId(pairId)
    setDescContent(pair.description)
    setDescTab('write')
    setDescModalOpen(true)
  }

  const saveDescription = () => {
    if (!descEditingPairId) return
    setWordPairs(prev => prev.map(p =>
      p.id === descEditingPairId ? { ...p, description: descContent } : p
    ))
    setDescModalOpen(false)
    setDescEditingPairId(null)
  }

  const insertFormatting = (before: string, after = '') => {
    const ta = descTextareaRef.current
    if (!ta) return
    const start = ta.selectionStart
    const end = ta.selectionEnd
    const selected = descContent.slice(start, end)
    const newText = descContent.slice(0, start) + before + selected + after + descContent.slice(end)
    setDescContent(newText)
    // Restore cursor after state update
    setTimeout(() => {
      ta.focus()
      ta.setSelectionRange(start + before.length, start + before.length + selected.length)
    }, 0)
  }

  const unlinkPair = (pairId: string) => {
    pairsTouched.current = true
    setWordPairs(prev => prev.filter(p => p.id !== pairId))
  }

  const handleCancelEdit = () => {
    setEditModalOpen(false)
    setEditingEnglishId(null)
    setPendingChuukeseIds([])
    setEditedText('')
    setEditedChuukeseTexts({})
    setWordPairs([])
    setSelEnTokens([])
    setSelChkTokens([])
    setSelectedEnglish(null)
    setSelectedChuukese([])
  }

  const attemptMatch = async (englishId: number, chuukeseIds: number[], currentWordPairs: WordPair[], customEnglishText?: string, customChuukeseTexts?: Record<number, string>) => {
    // For now, assume matches are correct
    const isCorrect = true
    
    const englishSentence = englishSentences.find(s => s.id === englishId)
    const englishText = customEnglishText || englishSentence?.editedText || englishSentence?.text || ''
    const chuukeseTexts = chuukeseIds.map(id => {
      // Use custom edited text if provided, otherwise fall back to sentence text
      if (customChuukeseTexts && customChuukeseTexts[id]) {
        return customChuukeseTexts[id]
      }
      const sentence = chuukeseSentences.find(s => s.id === id)
      return sentence?.editedText || sentence?.text || ''
    }).join(' ')
    
    try {
      // Save match to backend
      await axios.post('/api/brochures/match', {
        english_id: englishId,
        chuukese_ids: chuukeseIds,
        english_text: englishText,
        original_english_text: englishSentence?.text,
        chuukese_text: chuukeseTexts,
        is_correct: isCorrect,
        user_id: 'anonymous',
        article_id: articleId,
        word_pairs: currentWordPairs,
      })
      if (articleId) refreshSaved()
      
      // Add to matches with edited text and saved word pairs
      setMatches(prev => [...prev, { 
        englishId, 
        chuukeseIds,
        editedEnglishText: customEnglishText || englishSentence?.editedText,
        savedWordPairs: currentWordPairs,
      }])
      setScore(score + 10)
      setCorrectMatches(correctMatches + 1)
      
      notifications.show({
        title: '✅ Match Saved!',
        message: `+10 points (${chuukeseIds.length} Chuukese sentence${chuukeseIds.length > 1 ? 's' : ''})`,
        color: 'green'
      })
      
      setTotalAttempts(totalAttempts + 1)
      
      // Reset selections
      setSelectedEnglish(null)
      setSelectedChuukese([])
      
    } catch {
      notifications.show({
        title: 'Error',
        message: 'Failed to save match',
        color: 'red'
      })
    }
  }

  const resetGame = () => {
    setMatches([])
    setHints({})
    setDictionary({})
    setSimilar({})
    setPhrases({})
    setGloss(null)
    setArticleId(null)
    setSelectedEnglish(null)
    setSelectedChuukese([])
    setEnglishUrl('')
    setChuukeseUrl('')
    setArticleTitle('')
    setEnglishSentences([])
    setChuukeseSentences([])
    clearGameState()
  }

  const accuracy = totalAttempts > 0 ? Math.round((correctMatches / totalAttempts) * 100) : 0

  // Dictionary phrases among the modal's Chuukese chips, so hovering one word
  // of "ewe Kot" shows the phrase and both words.
  const modalPhraseSpans = spanIndex(chkPhraseSpans(chuukeseTokens, phrases))

  // The clue for the selected English sentence, if the server could pair its paragraph.
  const activeHint: Hint | undefined =
    showClues && selectedEnglish !== null ? hints[String(selectedEnglish)] : undefined
  const clueFor = (chuukeseId: number): 'likely' | 'paragraph' | null => {
    if (!activeHint) return null
    if (activeHint.likely.includes(chuukeseId)) return 'likely'
    if (activeHint.paragraph.includes(chuukeseId)) return 'paragraph'
    return null
  }

  return (
    <Group align="flex-start" gap="lg" wrap="nowrap" className="game-layout">
      <ArticleSidebar
        saved={saved}
        activeId={articleId}
        loading={savedLoading}
        error={savedError}
        onSelect={openSaved}
        onDelete={removeSaved}
      />
      <Stack gap="lg" style={{ flex: 1, minWidth: 0 }}>
      {/* Header Card */}
      <Card withBorder>
        <Group justify="space-between">
          <div>
            <Title order={2} mb="xs">
              <IconTarget size={28} style={{ marginRight: '8px', verticalAlign: 'middle' }} />
              Translation Matching Game
            </Title>
            <Text c="dimmed">
              {articleTitle || 'Fetch an article from wol.jw.org to start matching'}
            </Text>
          </div>
          {englishSentences.length > 0 && (
            <Button 
              leftSection={<IconRefresh size={16} />}
              onClick={resetGame}
              variant="outline"
            >
              New Article
            </Button>
          )}
        </Group>
      </Card>

      {/* URL Display Card - shown when article is loaded */}
      {englishSentences.length > 0 && (
        <Card withBorder>
          <Stack gap="sm">
            <Group justify="space-between" align="flex-start">
              <Title order={4}>
                <IconWorld size={20} style={{ marginRight: '8px', verticalAlign: 'middle' }} />
                Article URLs
              </Title>
              <Button 
                onClick={fetchFromUrl}
                loading={loading}
                leftSection={<IconRefresh size={16} />}
                variant="light"
                size="sm"
              >
                Rescan Document
              </Button>
            </Group>
            <Group gap="xs" wrap="nowrap">
              <Text size="sm" fw={500} style={{ minWidth: '60px' }}>English:</Text>
              <Text 
                size="sm" 
                c="blue" 
                style={{ 
                  wordBreak: 'break-all', 
                  cursor: 'pointer',
                  textDecoration: 'underline',
                  flex: 1
                }}
                onClick={() => window.open(englishUrl, '_blank')}
                title="Click to open in new tab"
              >
                {englishUrl}
              </Text>
              <CopyButton value={englishUrl}>
                {({ copied, copy }) => (
                  <Tooltip label={copied ? 'Copied!' : 'Copy URL'}>
                    <ActionIcon color={copied ? 'teal' : 'gray'} variant="subtle" onClick={copy} size="sm">
                      {copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
                    </ActionIcon>
                  </Tooltip>
                )}
              </CopyButton>
            </Group>
            <Group gap="xs" wrap="nowrap">
              <Text size="sm" fw={500} style={{ minWidth: '60px' }}>Chuukese:</Text>
              <Text 
                size="sm" 
                c="blue" 
                style={{ 
                  wordBreak: 'break-all', 
                  cursor: 'pointer',
                  textDecoration: 'underline',
                  flex: 1
                }}
                onClick={() => window.open(chuukeseUrl, '_blank')}
                title="Click to open in new tab"
              >
                {chuukeseUrl}
              </Text>
              <CopyButton value={chuukeseUrl}>
                {({ copied, copy }) => (
                  <Tooltip label={copied ? 'Copied!' : 'Copy URL'}>
                    <ActionIcon color={copied ? 'teal' : 'gray'} variant="subtle" onClick={copy} size="sm">
                      {copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
                    </ActionIcon>
                  </Tooltip>
                )}
              </CopyButton>
            </Group>
          </Stack>
        </Card>
      )}

      {/* URL Input Card */}
      {englishSentences.length === 0 && (
        <Card withBorder>
          <Stack gap="md">
            <Title order={4}>
              <IconWorld size={20} style={{ marginRight: '8px', verticalAlign: 'middle' }} />
              Load Article from JW.org
            </Title>
            <TextInput
              placeholder="https://wol.jw.org/en/wol/d/r1/lp-e/..."
              label="English Article URL"
              description="Enter the English article URL"
              value={englishUrl}
              onChange={(e) => setEnglishUrl(e.target.value)}
            />
            <TextInput
              placeholder="https://wol.jw.org/chk/wol/d/r303/lp-te/..."
              label="Chuukese Article URL"
              description="Enter the Chuukese article URL (note: /chk/ and /lp-te/)"
              value={chuukeseUrl}
              onChange={(e) => setChuukeseUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && fetchFromUrl()}
            />
            <Group>
              <Button 
                onClick={fetchFromUrl}
                loading={loading}
                leftSection={<IconWorld size={16} />}
              >
                Fetch Article
              </Button>
              {(englishSentences.length > 0 || chuukeseSentences.length > 0) && (
                <Button 
                  onClick={clearGameState}
                  variant="outline"
                  color="red"
                  leftSection={<IconRefresh size={16} />}
                >
                  Reset Game
                </Button>
              )}
            </Group>
          </Stack>
        </Card>
      )}

      {/* Stats Card */}
      <Card withBorder>
        <Group justify="space-around">
          <Stack gap="xs" align="center">
            <IconTrophy size={32} color="#FFD700" />
            <Text size="xl" fw={700}>{score}</Text>
            <Text size="sm" c="dimmed">Score</Text>
          </Stack>
          <Stack gap="xs" align="center">
            <IconCheck size={32} color="green" />
            <Text size="xl" fw={700}>{correctMatches}</Text>
            <Text size="sm" c="dimmed">Correct</Text>
          </Stack>
          <Stack gap="xs" align="center">
            <IconX size={32} color="red" />
            <Text size="xl" fw={700}>{totalAttempts - correctMatches}</Text>
            <Text size="sm" c="dimmed">Incorrect</Text>
          </Stack>
          <Stack gap="xs" align="center">
            <IconTarget size={32} color="blue" />
            <Text size="xl" fw={700}>{accuracy}%</Text>
            <Text size="sm" c="dimmed">Accuracy</Text>
          </Stack>
        </Group>
      </Card>

      {/* Game Instructions */}
      {englishSentences.length > 0 && (
        <>
          <Alert title="How to Play" color="blue">
            <Text size="sm">
              1. Click an English sentence — the Chuukese sentences from the same paragraph light up, and the likely match is marked <Badge size="xs" color="yellow" variant="filled">Clue</Badge><br />
              2. Click one or more Chuukese sentences that match it (hover a word for its dictionary entry)<br />
              &nbsp;&nbsp;&nbsp;Matched pairs share a colour and number across both columns; click a matched English sentence to redo it<br />
              3. Click "Confirm Match" button<br />
              4. Edit the English text if needed before saving
            </Text>
          </Alert>
          
          {/* Confirm Match Button */}
          {selectedEnglish !== null && selectedChuukese.length > 0 && (
            <Button 
              size="md" 
              onClick={handleConfirmMatch}
              color="green"
            >
              Confirm Match ({selectedChuukese.length} Chuukese sentence{selectedChuukese.length > 1 ? 's' : ''})
            </Button>
          )}
        </>
      )}

      {/* Game Board */}
      {englishSentences.length > 0 && (
        <Group align="flex-start" grow style={{ minHeight: '500px' }}>
          {/* English Column */}
          <Card withBorder>
            <Title order={4} mb="md">
              <Badge color="blue" size="lg" mb="xs">English ({englishSentences.length})</Badge>
            </Title>
            <ScrollArea h={600}>
              <Stack gap="xs">
                {englishSentences.map((sentence) => {
                  const badge = matchBadge(matches, m => m.englishId === sentence.id)
                  const matched = !!badge
                  const selected = selectedEnglish === sentence.id
                  
                  return (
                    <Paper
                      key={sentence.id}
                      p="md"
                      withBorder
                      className={`sentence-card ${matched ? 'matched' : ''} ${selected ? 'selected' : ''}`}
                      onClick={() => handleEnglishClick(sentence.id)}
                      style={{
                        cursor: 'pointer',
                        backgroundColor: badge ? `var(--mantine-color-${badge.color}-0)` : selected ? '#e3f2fd' : 'white',
                        border: selected ? '2px solid #2196F3' : badge ? `2px solid var(--mantine-color-${badge.color}-6)` : '1px solid #dee2e6',
                        borderLeftWidth: badge ? 6 : undefined,
                      }}
                    >
                      <Group justify="space-between" align="flex-start">
                        <Text size="sm" style={{ flex: 1 }}>
                          {sentence.editedText || sentence.text}
                        </Text>
                        <Group gap="xs">
                          {badge && (
                            <Badge size="sm" color={badge.color} variant="filled" circle>{badge.n}</Badge>
                          )}
                          {sentence.editedText && (
                            <Badge size="xs" color="orange" variant="dot">Edited</Badge>
                          )}
                          {selected && activeHint && (
                            <Badge size="xs" color="yellow" variant="light">
                              {activeHint.likely.length} clue{activeHint.likely.length === 1 ? '' : 's'}
                            </Badge>
                          )}
                          {selected && showClues && !activeHint && (
                            <Badge size="xs" color="gray" variant="light">no clue</Badge>
                          )}
                          {matched ? (
                            <Tooltip label="Click to re-edit this match" withArrow>
                              <Group gap={4}>
                                <IconCheck size={16} color="green" />
                                <IconEdit size={14} color="gray" />
                              </Group>
                            </Tooltip>
                          ) : null}
                        </Group>
                      </Group>
                    </Paper>
                  )
                })}
              </Stack>
            </ScrollArea>
          </Card>

          {/* Chuukese Column */}
          <Card withBorder>
            <Title order={4} mb="md">
              <Group justify="space-between" align="center">
                <Badge color="green" size="lg" mb="xs">Chuukese ({chuukeseSentences.length})</Badge>
                <Switch
                  size="sm"
                  label="Show clues"
                  checked={showClues}
                  onChange={(e) => setShowClues(e.currentTarget.checked)}
                />
              </Group>
              <GlossLegend />
            </Title>
            <ScrollArea h={600}>
              <Stack gap="xs">
                {chuukeseSentences.map((sentence) => {
                  const badge = matchBadge(matches, m => m.chuukeseIds.includes(sentence.id))
                  const matched = !!badge
                  const selected = selectedChuukese.includes(sentence.id)
                  const clue = matched ? null : clueFor(sentence.id)
                  const background = badge ? `var(--mantine-color-${badge.color}-0)`
                    : selected ? '#e3f2fd'
                    : clue === 'likely' ? '#fff3bf'
                    : clue === 'paragraph' ? '#fff9db'
                    : 'white'
                  const border = selected ? '2px solid #2196F3'
                    : badge ? `2px solid var(--mantine-color-${badge.color}-6)`
                    : clue === 'likely' ? '2px dashed #f59f00'
                    : clue === 'paragraph' ? '1px dashed #fab005'
                    : '1px solid #dee2e6'
                  
                  return (
                    <Paper
                      key={sentence.id}
                      ref={(el: HTMLDivElement | null) => { chuukeseCardRefs.current[sentence.id] = el }}
                      p="md"
                      withBorder
                      className={`sentence-card ${matched ? 'matched' : ''} ${selected ? 'selected' : ''} ${clue ? `clue-${clue}` : ''}`}
                      onClick={() => !matched && handleChuukeseClick(sentence.id)}
                      style={{
                        cursor: matched ? 'not-allowed' : 'pointer',
                        opacity: !matched && activeHint && !clue && !selected ? 0.55 : 1,
                        backgroundColor: background,
                        border,
                        borderLeftWidth: badge ? 6 : undefined,
                      }}
                    >
                      <Group justify="space-between" align="flex-start">
                        <Text size="sm" className="chuukese-text-style" style={{ flex: 1 }}>
                          <GlossedWords
                            text={sentence.editedText || sentence.text}
                            dictionary={dictionary}
                            similar={similar}
                            phrases={phrases}
                            onGloss={setGloss}
                            keyPrefix={`${sentence.id}-`}
                          />
                        </Text>
                        <Group gap="xs">
                          {badge && (
                            <Badge size="sm" color={badge.color} variant="filled" circle>{badge.n}</Badge>
                          )}
                          {clue === 'likely' && (
                            <Badge size="xs" color="yellow" variant="filled">Clue</Badge>
                          )}
                          {clue === 'paragraph' && (
                            <Badge size="xs" color="yellow" variant="outline">Same ¶</Badge>
                          )}
                          {sentence.editedText && (
                            <Badge size="xs" color="orange" variant="dot">Edited</Badge>
                          )}
                          {badge && <IconCheck size={16} color={`var(--mantine-color-${badge.color}-7)`} />}
                        </Group>
                      </Group>
                    </Paper>
                  )
                })}
              </Stack>
            </ScrollArea>
          </Card>
        </Group>
      )}

      {gloss && <GlossCard gloss={gloss} />}

      {/* Completion Message */}
      {matches.length === englishSentences.length && englishSentences.length > 0 && (
        <Alert title="🎉 Round Complete!" color="green">
          <Text>
            Congratulations! You matched all {matches.length} sentences.
          </Text>
          <Button 
            mt="md" 
            leftSection={<IconRefresh size={16} />}
            onClick={resetGame}
          >
            Start New Round
          </Button>
        </Alert>
      )}

      {/* Edit Translation Modal */}
      <Modal
        opened={editModalOpen}
        onClose={handleCancelEdit}
        title="Match Words"
        size="xl"
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Pairs the dictionary already knows are linked for you; <Badge size="xs" variant="outline" color="orange">fuzzy</Badge> pairs
            come from a related entry, an identical name or a number — unlink any that are wrong.
            Select English and Chuukese words, then click <strong>Link</strong> to pair the rest. Hover a Chuukese word for its gloss.
            {loadingSuggestions && <Loader size="xs" ml="xs" />}
          </Text>
          <GlossLegend />

          {/* English word chips */}
          <Stack gap={4}>
            <Text size="xs" fw={600} tt="uppercase" c="blue">English</Text>
            <Group gap={6} wrap="wrap">
              {englishTokens.map((token, idx) => {
                const pair = wordPairs.find(p => p.englishIndices.includes(idx))
                const isSelected = selEnTokens.includes(idx)
                const isPaired = !!pair
                const pendingColor = PAIR_COLORS[wordPairs.length % PAIR_COLORS.length]
                return (
                  <Badge
                    key={idx}
                    size="lg"
                    variant={isPaired || isSelected ? 'filled' : 'outline'}
                    color={isSelected ? pendingColor : isPaired ? pair!.color : 'gray'}
                    style={{ cursor: 'pointer', userSelect: 'none' }}
                    onClick={() => toggleEnToken(idx)}
                  >
                    {token}
                  </Badge>
                )
              })}
            </Group>
            {englishRefs.length > 0 && (
              <Text size="xs" c="dimmed" fs="italic">References (not matched): {englishRefs.join(' ')}</Text>
            )}
          </Stack>

          {/* Chuukese word chips */}
          <Stack gap={4}>
            <Text size="xs" fw={600} tt="uppercase" c="orange">Chuukese</Text>
            <Group gap={6} wrap="wrap">
              {chuukeseTokens.map((token, idx) => {
                const pair = wordPairs.find(p => p.chuukeseIndices.includes(idx))
                const isSelected = selChkTokens.includes(idx)
                const isPaired = !!pair
                const key = tokenKey(token)
                const entry = dictionary[key]
                const near = entry ? undefined : similar[key]
                const status = glossStatus(entry, near)
                const sugg = wordSuggestions[key]
                const span = modalPhraseSpans.get(idx)
                const pendingColor = PAIR_COLORS[wordPairs.length % PAIR_COLORS.length]
                const hoverable = !!(entry || near || sugg || span)
                return (
                  <Badge
                    key={idx}
                    size="lg"
                    variant={isPaired || isSelected ? 'filled' : status ? 'light' : 'outline'}
                    color={isSelected ? pendingColor : isPaired ? pair!.color : status ? GLOSS_COLOR[status] : 'gray'}
                    style={{
                      cursor: 'pointer', userSelect: 'none',
                      outline: isPaired && pair!.fuzzy ? '2px dashed var(--mantine-color-orange-5)' : undefined,
                      outlineOffset: 1,
                    }}
                    onClick={() => toggleChkToken(idx)}
                    onMouseEnter={hoverable ? (e) => setGloss({
                      word: stripToken(token), entry, similar: near,
                      phrase: span ? phraseGloss(span.entry, dictionary) : undefined,
                      suggestion: sugg?.helsinki_translation, x: e.clientX, y: e.clientY,
                    }) : undefined}
                    onMouseLeave={hoverable ? () => setGloss(null) : undefined}
                  >
                    {token}
                  </Badge>
                )
              })}
            </Group>
            {chuukeseRefs.length > 0 && (
              <Text size="xs" c="dimmed" fs="italic" className="chuukese-text-style">References (not matched): {chuukeseRefs.join(' ')}</Text>
            )}
          </Stack>

          {/* Link button */}
          <Group>
            <Button
              leftSection={<IconLink size={16} />}
              disabled={selEnTokens.length === 0 || selChkTokens.length === 0}
              onClick={linkSelectedTokens}
              variant="light"
              color="teal"
              size="sm"
            >
              Link Selected Words ({selEnTokens.length} EN + {selChkTokens.length} CHK)
            </Button>
            {(selEnTokens.length > 0 || selChkTokens.length > 0) && (
              <Button size="sm" variant="subtle" color="gray"
                onClick={() => { setSelEnTokens([]); setSelChkTokens([]) }}>
                Clear selection
              </Button>
            )}
          </Group>

          {/* Linked pairs */}
          {wordPairs.length > 0 && (
            <>
              <Divider label="Linked word pairs" labelPosition="left" />
              <Stack gap="xs">
                {wordPairs.map(pair => (
                  <Paper key={pair.id} withBorder p="xs" style={{ borderLeft: `4px solid var(--mantine-color-${pair.color}-5)` }}>
                    <Group justify="space-between" wrap="nowrap" mb={4}>
                      <Group gap="xs" wrap="wrap">
                        <Badge color={pair.color} variant="filled">{pair.englishWords.join(' ')}</Badge>
                        <Text size="sm" c="dimmed">↔</Text>
                        <Badge color={pair.color} variant="light">{pair.chuukeseWords.join(' ')}</Badge>
                        <Badge size="xs" variant="outline" color="gray">{pair.grammar}</Badge>
                        {pair.fuzzy && (
                          <Tooltip
                            label={pair.baseWord ? `Proposed from the entry "${pair.baseWord}"` : pair.source === 'number' ? 'Same number on both sides' : 'Same word on both sides'}
                            withArrow
                          >
                            <Badge size="xs" variant="outline" color="orange">fuzzy{pair.baseWord ? ` · ${pair.baseWord}` : ''}</Badge>
                          </Tooltip>
                        )}
                        {pair.inDatabase && (
                          <Tooltip label="Already in database" withArrow>
                            <span style={{
                              display: 'inline-block',
                              width: 8, height: 8,
                              borderRadius: '50%',
                              background: 'var(--mantine-color-teal-5)',
                              flexShrink: 0,
                            }} />
                          </Tooltip>
                        )}
                      </Group>
                      <ActionIcon size="sm" color="red" variant="subtle" onClick={() => unlinkPair(pair.id)}>
                        <IconUnlink size={14} />
                      </ActionIcon>
                    </Group>
                    {/* Clickable description */}
                    <Text
                      size="xs"
                      c={pair.description ? 'dark' : 'dimmed'}
                      style={{ cursor: 'pointer', fontStyle: pair.description ? 'normal' : 'italic',
                               padding: '4px 6px', borderRadius: 4,
                               background: 'var(--mantine-color-gray-0)',
                               border: '1px dashed var(--mantine-color-gray-3)' }}
                      onClick={() => openDescEditor(pair.id)}
                    >
                      {pair.description
                        ? pair.description.length > 80 ? pair.description.slice(0, 80) + '…' : pair.description
                        : '+ Add description…'}
                    </Text>
                  </Paper>
                ))}
              </Stack>
            </>
          )}

          {/* Toggle sentence edit */}
          <Divider
            label={
              <Text size="xs" style={{ cursor: 'pointer' }} c="dimmed"
                onClick={() => setShowEditTexts(v => !v)}>
                {showEditTexts ? '▲ Hide sentence edit' : '▼ Edit sentences'}
              </Text>
            }
            labelPosition="left"
          />
          {showEditTexts && (
            <Stack gap="sm">
              <Textarea
                label="English Translation"
                value={editedText}
                onChange={(e) => setEditedText(e.target.value)}
                minRows={2}
                maxRows={5}
                autosize
              />
              {pendingChuukeseIds.map(id => {
                const sentence = chuukeseSentences.find(s => s.id === id)
                return sentence ? (
                  <Textarea
                    key={id}
                    label="Chuukese"
                    value={editedChuukeseTexts[id] || sentence.text}
                    onChange={(e) => setEditedChuukeseTexts(prev => ({ ...prev, [id]: e.target.value }))}
                    minRows={2}
                    maxRows={4}
                    autosize
                    className="chuukese-text-style"
                  />
                ) : null
              })}
            </Stack>
          )}

          <Group justify="flex-end" mt="md">
            <Button variant="subtle" onClick={handleCancelEdit}>Cancel</Button>
            <Button leftSection={<IconCheck size={16} />} onClick={handleSaveEdit}>
              Confirm Match{wordPairs.length > 0 ? ` & Save ${wordPairs.length} Word Pair${wordPairs.length > 1 ? 's' : ''}` : ''}
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* Description Editor Modal */}
      <Modal
        opened={descModalOpen}
        onClose={() => setDescModalOpen(false)}
        title={(() => {
          const pair = wordPairs.find(p => p.id === descEditingPairId)
          return pair ? `Description — ${pair.chuukeseWords.join(' ')} ↔ ${pair.englishWords.join(' ')}` : 'Description'
        })()}
        size="lg"
        zIndex={300}
      >
        <Stack gap="sm">
          <Tabs value={descTab} onChange={setDescTab}>
            <Tabs.List>
              <Tabs.Tab value="write" leftSection={<IconPencil size={14} />}>Write</Tabs.Tab>
              <Tabs.Tab value="preview" leftSection={<IconEye size={14} />}>Preview</Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="write" pt="sm">
              {/* Formatting toolbar */}
              <Group gap={4} mb={6}>
                {([
                  { label: 'B', title: 'Bold', before: '**', after: '**' },
                  { label: 'I', title: 'Italic', before: '_', after: '_' },
                  { label: 'H', title: 'Heading', before: '## ', after: '' },
                ] as { label: string; title: string; before: string; after: string }[]).map(btn => (
                  <Button
                    key={btn.label}
                    size="xs"
                    variant="default"
                    title={btn.title}
                    onClick={() => insertFormatting(btn.before, btn.after)}
                    style={{ fontWeight: btn.label === 'B' ? 700 : btn.label === 'I' ? 400 : undefined,
                             fontStyle: btn.label === 'I' ? 'italic' : undefined, minWidth: 32 }}
                  >
                    {btn.label}
                  </Button>
                ))}
                <Button size="xs" variant="default" title="Bullet list"
                  onClick={() => insertFormatting('\n- ', '')}>• List</Button>
                <Button size="xs" variant="default" title="Numbered list"
                  onClick={() => insertFormatting('\n1. ', '')}>1. List</Button>
              </Group>
              <Textarea
                ref={descTextareaRef}
                value={descContent}
                onChange={e => setDescContent(e.currentTarget.value)}
                minRows={8}
                autosize
                placeholder="Write a description using Markdown…"
                styles={{ input: { fontFamily: 'monospace', fontSize: 13 } }}
              />
            </Tabs.Panel>

            <Tabs.Panel value="preview" pt="sm">
              {descContent.trim() ? (
                <Paper withBorder p="md" style={{ minHeight: 160 }}>
                  <div
                    style={{ lineHeight: 1.6 }}
                    dangerouslySetInnerHTML={{ __html: _md.render(descContent) }}
                  />
                </Paper>
              ) : (
                <Text c="dimmed" size="sm" p="md">Nothing to preview yet.</Text>
              )}
            </Tabs.Panel>
          </Tabs>

          <Group justify="flex-end" mt="sm">
            <Button variant="subtle" onClick={() => setDescModalOpen(false)}>Cancel</Button>
            <Button leftSection={<IconCheck size={16} />} onClick={saveDescription}>
              Save Description
            </Button>
          </Group>
        </Stack>
      </Modal>
      </Stack>
    </Group>
  )
}

export default TranslationGame
