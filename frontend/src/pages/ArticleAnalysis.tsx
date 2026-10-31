/**
 * ArticleAnalysis — fetch a Chuukese article from wol.jw.org, look every word
 * up in the dictionary, and show each sentence beside its English from the
 * parallel article.
 *
 * Reads like the Watchtower Library page: words are tinted by dictionary
 * status with a hover gloss, and clicking a word opens an action bar to edit
 * or add the entry, ask for a suggested entry, or see WOL examples. The
 * backend streams one paragraph at a time (NDJSON), each with the dictionary
 * maps covering its words; completed analyses are saved and listed in the
 * sidebar.
 */
import { Fragment, useState, useRef, useEffect, useCallback, useMemo } from 'react'
import {
  Container, Title, Text, TextInput, Button, Stack, Card, Group, Badge, Divider, Loader, Alert, Paper,
  Anchor, Progress, Box, ScrollArea, ActionIcon, NavLink as MantineNavLink, Tooltip,
} from '@mantine/core'
import {
  IconWorld, IconLanguage, IconAlertCircle, IconSearch, IconBookmark, IconExternalLink,
  IconPencil, IconPlus, IconHistory, IconTrash, IconRefresh, IconSparkles, IconQuote, IconX,
} from '@tabler/icons-react'
import axios from 'axios'
import { useUser } from '../contexts/UserContext'
import { GlossedWords, GlossCard, GlossLegend } from '../components/GlossedText'
import type { Dictionary, SimilarMap, Gloss, DictEntry } from '../components/GlossedText'
import type { PhraseMap } from '../components/glossUtils'
import { EntryEditor } from '../components/analysis/EntryEditor'
import type { EntryPrefill, EntrySaved } from '../components/analysis/EntryEditor'
import { SuggestModal } from '../components/analysis/SuggestModal'
import { WolExamplesDrawer } from '../components/analysis/WolExamples'
import styles from '../components/analysis/analysis.module.css'

// ── Types ─────────────────────────────────────────────────────────────────────

interface WordAnalysis {
  original: string
  key?: string
  english: string
  grammar: string
  grammar_modifier?: string | null
  definition?: string
  found: boolean
  entry_id?: string | null
  source?: DictEntry['source']
  variant_of?: string | null
  english_token_indices?: number[]
}

interface AnalyzedSentence {
  chuukese: string
  text_only: string
  words: WordAnalysis[]
  english_text?: string | null
  english_tokens?: string[] | null
  scriptures: string[]
}

interface StreamedParagraph {
  index: number
  is_heading: boolean
  raw_text: string
  sentences: AnalyzedSentence[]
  sentence_count: number
  /** Present on analyses made since the rebuild; older saved ones lack them. */
  dictionary?: Dictionary
  similar?: SimilarMap
  phrases?: PhraseMap
}

interface ArticleMeta {
  title: string
  url: string
  source_label: string
  paragraph_count: number
  english_url?: string
  english_title?: string
  has_english: boolean
}

interface SavedAnalysis {
  _id: string
  chuukese_title: string
  english_title?: string
  url: string
  english_url?: string
  paragraph_count: number
  sentence_count: number
  created_at?: string
  has_english: boolean
}

/** The word the user clicked, with the sentence it sits in. */
interface Selection {
  word: string
  key: string
  sentence: AnalyzedSentence
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function cleanScripture(ref: string): string {
  return ref.replace(/^\s*--\s*/, '').replace(/^\s*\(|\)\s*$/g, '').trim()
}

function errorMessage(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) return e.response?.data?.error || fallback
  return fallback
}

/** Dictionary maps for a paragraph. Analyses saved before the rebuild carry
 *  no maps, so one is rebuilt from the per-word results. */
function paragraphMaps(p: StreamedParagraph): { dictionary: Dictionary; similar: SimilarMap; phrases: PhraseMap } {
  if (p.dictionary) return { dictionary: p.dictionary, similar: p.similar || {}, phrases: p.phrases || {} }
  const dictionary: Dictionary = {}
  p.sentences.forEach((s) => s.words.forEach((w) => {
    if (!w.found) return
    const key = (w.key || w.original).toLowerCase()
    if (dictionary[key]) return
    dictionary[key] = {
      english: w.english || '',
      grammar: w.grammar || '',
      grammar_modifier: w.grammar_modifier || null,
      definition: w.definition || '',
      status: w.english ? 'translated' : 'untranslated',
      entry_id: w.entry_id || null,
      source: w.source,
      variant_of: w.variant_of || undefined,
    }
  }))
  return { dictionary, similar: {}, phrases: {} }
}

/** Paragraph number as printed in the article (leading digits of the text),
 *  or the running count of body paragraphs when the text has none. */
function paragraphNumber(para: StreamedParagraph, fallback: number): number {
  const m = /^\s*(\d{1,3})\b/.exec(para.raw_text || '')
  return m ? parseInt(m[1], 10) : fallback
}

// ── Sentence ──────────────────────────────────────────────────────────────────

function SentenceRow({
  sentence, label, maps, onGloss, onSelect, selectedKey,
}: {
  sentence: AnalyzedSentence
  /** "paragraph.sentence", e.g. "3.2" for the second sentence of paragraph 3. */
  label: string
  maps: { dictionary: Dictionary; similar: SimilarMap; phrases: PhraseMap }
  onGloss: (g: Gloss | null) => void
  onSelect: (sel: Selection) => void
  selectedKey: string | null
}) {
  const [hoverKey, setHoverKey] = useState<string | null>(null)
  const words = sentence.words.filter((w) => !/^\d+$/.test(w.original))
  const known = words.filter((w) => maps.dictionary[(w.key || w.original).toLowerCase()]).length
  const pct = words.length ? Math.round((known / words.length) * 100) : 0

  // English tokens lined up with the hovered (or selected) Chuukese word.
  const activeKey = hoverKey || selectedKey
  const highlight = new Set<number>()
  if (activeKey) {
    sentence.words
      .filter((w) => (w.key || w.original).toLowerCase() === activeKey)
      .forEach((w) => (w.english_token_indices || []).forEach((i) => highlight.add(i)))
  }

  return (
    <Card withBorder padding="md" className={styles.result}>
      <Group gap="xs" mb={6} wrap="wrap">
        <Badge size="sm" variant="outline" color="violet" fw={700}>{label}</Badge>
        <Badge size="xs" variant="light" color={pct >= 80 ? 'green' : pct >= 50 ? 'yellow' : 'red'}>
          {known}/{words.length} in dictionary
        </Badge>
        {sentence.scriptures.map((ref, ri) => (
          <Group key={ri} gap={4} wrap="nowrap">
            <IconBookmark size={12} color="#7950f2" />
            <Text size="xs" fw={600} c="violet.7">{cleanScripture(ref)}</Text>
          </Group>
        ))}
      </Group>
      <Text className={styles.sentence}>
        <GlossedWords
          text={sentence.text_only}
          dictionary={maps.dictionary}
          similar={maps.similar}
          phrases={maps.phrases}
          onGloss={(g) => { onGloss(g); setHoverKey(g ? g.word.toLowerCase() : null) }}
          onWordClick={(w) => onSelect({ word: w, key: w.toLowerCase(), sentence })}
        />
      </Text>
      <Box className={styles.english}>
        {sentence.english_tokens && sentence.english_tokens.length > 0 ? (
          <Text className={styles.englishText}>
            {sentence.english_tokens.map((tok, ti) => (
              <span key={ti}>
                <span className={highlight.has(ti) ? styles.englishHit : undefined}>{tok}</span>{' '}
              </span>
            ))}
          </Text>
        ) : sentence.english_text ? (
          <Text className={styles.englishText}>{sentence.english_text}</Text>
        ) : (
          <Text size="xs" c="dimmed" fs="italic">No matching sentence in the English article.</Text>
        )}
      </Box>
    </Card>
  )
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

function HistorySidebar({
  saved, activeId, onSelect, onDelete, isAdmin, loading, error,
}: {
  saved: SavedAnalysis[]
  activeId: string | null
  onSelect: (a: SavedAnalysis) => void
  onDelete: (id: string) => void
  isAdmin: boolean
  loading: boolean
  error: string
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
            <Text size="xs" c="dimmed" ta="center" py="md">Articles you analyze are saved here.</Text>
          )}
          {saved.map((a) => (
            <Box key={a._id} mb={4} style={{ position: 'relative' }}>
              <MantineNavLink
                label={
                  <Stack gap={2}>
                    <Text size="xs" fw={700} lineClamp={2} c={activeId === a._id ? 'violet.9' : undefined}>
                      {a.chuukese_title || 'Untitled'}
                    </Text>
                    {a.english_title && <Text size="xs" c="dimmed" lineClamp={1}>{a.english_title}</Text>}
                    <Group gap={4} mt={2}>
                      <Badge size="xs" variant="light" color="violet">{a.paragraph_count}¶</Badge>
                      <Badge size="xs" variant="light" color="teal">{a.sentence_count}s</Badge>
                      {a.has_english && <Badge size="xs" variant="dot" color="green">EN</Badge>}
                    </Group>
                  </Stack>
                }
                active={activeId === a._id}
                onClick={() => onSelect(a)}
                style={{ borderRadius: 6, paddingRight: isAdmin ? 30 : undefined }}
              />
              {isAdmin && (
                <ActionIcon
                  size="xs" color="red" variant="subtle"
                  style={{ position: 'absolute', top: 8, right: 4 }}
                  onClick={(e) => { e.stopPropagation(); onDelete(a._id) }}
                  aria-label={`Delete ${a.chuukese_title}`}
                >
                  <IconTrash size={12} />
                </ActionIcon>
              )}
            </Box>
          ))}
        </ScrollArea>
      </Paper>
    </Box>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ArticleAnalysis() {
  const { role } = useUser()
  const isAdmin = role === 'admin'

  const [url, setUrl] = useState('')
  const [englishUrl, setEnglishUrl] = useState('')

  const [meta, setMeta] = useState<ArticleMeta | null>(null)
  const [paragraphs, setParagraphs] = useState<StreamedParagraph[]>([])
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')
  const [progress, setProgress] = useState(0)
  const abortRef = useRef<AbortController | null>(null)

  const [saved, setSaved] = useState<SavedAnalysis[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [sidebarLoading, setSidebarLoading] = useState(false)
  const [sidebarError, setSidebarError] = useState('')

  const [gloss, setGloss] = useState<Gloss | null>(null)
  const [selection, setSelection] = useState<Selection | null>(null)
  const [editor, setEditor] = useState<{ word: string; entry?: DictEntry | null; prefill?: EntryPrefill | null; example: string } | null>(null)
  const [suggest, setSuggest] = useState<Selection | null>(null)
  const [examplesWord, setExamplesWord] = useState<string | null>(null)

  const maps = useMemo(() => paragraphs.map(paragraphMaps), [paragraphs])

  // Page-wide maps, for the selected word's entry.
  const pageDictionary = useMemo(() => Object.assign({}, ...maps.map((m) => m.dictionary)) as Dictionary, [maps])

  const totals = useMemo(() => {
    let words = 0
    let known = 0
    paragraphs.forEach((p, pi) => p.sentences.forEach((s) => s.words.forEach((w) => {
      if (/^\d+$/.test(w.original)) return
      words += 1
      if (maps[pi]?.dictionary[(w.key || w.original).toLowerCase()]) known += 1
    })))
    return { words, known, pct: words ? Math.round((known / words) * 100) : 0 }
  }, [paragraphs, maps])
  const progressPct = meta ? Math.round((progress / meta.paragraph_count) * 100) : 0

  // ── Saved analyses ──────────────────────────────────────────────────────
  const loadSaved = useCallback(async () => {
    setSidebarLoading(true)
    setSidebarError('')
    try {
      const res = await axios.get('/api/article-analyses')
      setSaved(Array.isArray(res.data) ? res.data : [])
    } catch (e) {
      setSidebarError(errorMessage(e, 'Could not load saved articles'))
    } finally {
      setSidebarLoading(false)
    }
  }, [])

  useEffect(() => { loadSaved() }, [loadSaved])

  const saveAnalysis = useCallback(async (metaArg: ArticleMeta, parasArg: StreamedParagraph[], sentenceCount: number) => {
    try {
      const res = await axios.post('/api/article-analyses', {
        url: metaArg.url,
        chuukese_title: metaArg.title,
        english_title: metaArg.english_title || '',
        english_url: metaArg.english_url || '',
        source_label: metaArg.source_label || '',
        has_english: metaArg.has_english,
        paragraph_count: metaArg.paragraph_count,
        sentence_count: sentenceCount,
        paragraphs: parasArg,
      })
      if (res.data?.id) setActiveId(res.data.id)
      await loadSaved()
    } catch (e) {
      setError(errorMessage(e, 'Could not save the analysis'))
    }
  }, [loadSaved])

  const loadAnalysis = async (a: SavedAnalysis) => {
    setActiveId(a._id)
    setError('')
    setLoading(true)
    setSelection(null)
    setGloss(null)
    try {
      const res = await axios.get(`/api/article-analyses/${a._id}`)
      const doc = res.data
      setMeta({
        title: doc.chuukese_title,
        url: doc.url,
        source_label: doc.source_label || '',
        paragraph_count: doc.paragraph_count,
        english_url: doc.english_url,
        english_title: doc.english_title,
        has_english: doc.has_english,
      })
      setParagraphs(doc.paragraphs || [])
      setUrl(doc.url)
      setEnglishUrl(doc.english_url || '')
      setDone(true)
    } catch (e) {
      setError(errorMessage(e, 'Could not open that saved analysis'))
    } finally {
      setLoading(false)
    }
  }

  const deleteAnalysis = async (id: string) => {
    try {
      await axios.delete(`/api/article-analyses/${id}`)
      if (activeId === id) { setMeta(null); setParagraphs([]); setDone(false); setActiveId(null) }
      await loadSaved()
    } catch (e) {
      setSidebarError(errorMessage(e, 'Could not delete that analysis'))
    }
  }

  // ── Dictionary changes ──────────────────────────────────────────────────
  /** After an add or edit, update every paragraph that holds the word so the
   *  tints change at once, then re-save so the change survives a reopen. */
  const applySaved = (saved: EntrySaved) => {
    const key = saved.word.toLowerCase()
    const update = (entry: DictEntry | undefined, textKey: string): DictEntry => ({
      ...(entry || { grammar_modifier: null, status: 'translated' as const }),
      english: saved.english,
      grammar: saved.grammar,
      definition: saved.definition,
      status: saved.english ? 'translated' : 'untranslated',
      entry_id: saved.entry_id ?? entry?.entry_id ?? null,
      source: 'dictionary',
      // Adding the text's own spelling makes it a headword in its own right.
      ...(saved.mode === 'add' && textKey === key ? { variant_of: undefined, variants: undefined } : {}),
    })
    const next = paragraphs.map((p, pi) => {
      const m = maps[pi]
      const dictionary = { ...m.dictionary }
      let touched = false
      // The spelling in the text, and any text spelling matched to this headword.
      Object.keys(dictionary).forEach((k) => {
        if (k === key || dictionary[k].variant_of?.toLowerCase() === key) {
          dictionary[k] = update(dictionary[k], k)
          touched = true
        }
      })
      p.sentences.forEach((s) => s.words.forEach((w) => {
        const k = (w.key || w.original).toLowerCase()
        if (k === key && !dictionary[k]) { dictionary[k] = update(undefined, k); touched = true }
      }))
      if (!touched) return p
      const similar = { ...m.similar }
      delete similar[key]
      const sentences = p.sentences.map((s) => ({
        ...s,
        words: s.words.map((w) => {
          const k = (w.key || w.original).toLowerCase()
          const e = dictionary[k]
          if (!e || !(k === key || e.variant_of?.toLowerCase() === key)) return w
          return { ...w, found: true, english: e.english, grammar: e.grammar, definition: e.definition, entry_id: e.entry_id, source: e.source, variant_of: e.variant_of || null }
        }),
      }))
      return { ...p, dictionary, similar, phrases: m.phrases, sentences }
    })
    setParagraphs(next)
    if (meta) {
      const count = next.reduce((n, p) => n + (p.sentence_count ?? p.sentences.length), 0)
      saveAnalysis(meta, next, count)
    }
  }

  const openEditor = (sel: Selection, prefill?: EntryPrefill | null) => {
    setEditor({ word: sel.word, entry: pageDictionary[sel.key], prefill: prefill ?? null, example: sel.sentence.text_only })
  }

  // ── Fetch & analyze ─────────────────────────────────────────────────────
  const handleStop = () => {
    abortRef.current?.abort()
    setLoading(false)
    setDone(true)
  }

  const handleAnalyze = async () => {
    if (!url.trim()) { setError('Enter the article URL first'); return }
    setLoading(true); setDone(false); setError('')
    setMeta(null); setParagraphs([]); setProgress(0); setActiveId(null); setSelection(null); setGloss(null)
    abortRef.current = new AbortController()

    let finalMeta: ArticleMeta | null = null
    let finalParas: StreamedParagraph[] = []
    let finalSentenceCount = 0

    try {
      const response = await fetch('/api/sentences/analyze-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ url: url.trim(), english_url: englishUrl.trim() || undefined }),
        signal: abortRef.current.signal,
      })

      if (!response.ok) {
        const text = await response.text()
        try { setError(JSON.parse(text).error || 'Request failed') } catch { setError(`HTTP ${response.status}`) }
        setLoading(false)
        return
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      const processLine = async (trimmed: string) => {
        if (!trimmed) return
        let event: Record<string, unknown>
        try { event = JSON.parse(trimmed) } catch { return }

        if (event.type === 'meta') {
          finalMeta = event as unknown as ArticleMeta
          setMeta(finalMeta)
          if (event.english_url && !englishUrl) setEnglishUrl(String(event.english_url))
        } else if (event.type === 'paragraph') {
          const para = event as unknown as StreamedParagraph
          finalParas = [...finalParas, para]
          finalSentenceCount += para.sentence_count
          setParagraphs((prev) => [...prev, para])
          setProgress((prev) => prev + 1)
        } else if (event.type === 'done') {
          finalSentenceCount = Number(event.total_sentences) || finalSentenceCount
          setDone(true)
          setLoading(false)
          if (finalMeta) await saveAnalysis(finalMeta, finalParas, finalSentenceCount)
        } else if (event.type === 'error') {
          setError(String(event.message))
          setLoading(false)
        }
      }

      while (true) {
        const { value, done: streamDone } = await reader.read()
        if (value) buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = streamDone ? '' : (lines.pop() ?? '')
        for (const line of lines) await processLine(line.trim())
        if (streamDone) {
          if (buffer.trim()) await processLine(buffer.trim())
          break
        }
      }
    } catch (err) {
      if (!(err instanceof DOMException && err.name === 'AbortError')) {
        setError(err instanceof Error ? err.message : 'Could not fetch the article')
      }
      setLoading(false)
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────
  const selectedEntry = selection ? pageDictionary[selection.key] : undefined
  const selectedNear = selection ? maps.find((m) => m.similar[selection.key])?.similar[selection.key] : undefined

  return (
    <Container size="xl" py="md">
      <Title order={2} mb={4}>Article Analysis</Title>
      <Text c="dimmed" size="sm" mb="lg">
        Fetch a Chuukese article from wol.jw.org: every word is checked against the dictionary and each
        sentence is shown with its English from the parallel article.
      </Text>

      <Group align="flex-start" gap="lg" wrap="nowrap" className={styles.layout}>
        <HistorySidebar
          saved={saved}
          activeId={activeId}
          onSelect={loadAnalysis}
          onDelete={deleteAnalysis}
          isAdmin={isAdmin}
          loading={sidebarLoading}
          error={sidebarError}
        />

        <Box style={{ flex: 1, minWidth: 0 }}>
          <Paper p="md" withBorder mb="md">
            <Stack gap="sm">
              <TextInput
                label="Chuukese article"
                placeholder="https://wol.jw.org/chk/wol/d/r303/lp-te/2026281"
                value={url}
                onChange={(e) => setUrl(e.currentTarget.value)}
                leftSection={<IconWorld size={16} />}
                onKeyDown={(e) => e.key === 'Enter' && !loading && handleAnalyze()}
                disabled={loading}
              />
              <TextInput
                label="English article"
                description="Optional — worked out from the Chuukese URL for wol.jw.org"
                placeholder="https://wol.jw.org/en/wol/d/r1/lp-e/2026281"
                value={englishUrl}
                onChange={(e) => setEnglishUrl(e.currentTarget.value)}
                leftSection={<IconLanguage size={14} />}
                disabled={loading}
              />
              <Group justify="space-between" wrap="wrap">
                <GlossLegend />
                <Group gap="xs">
                  {loading && <Button color="red" variant="light" onClick={handleStop}>Stop</Button>}
                  {done && activeId && (
                    <Button variant="light" leftSection={<IconRefresh size={16} />} onClick={handleAnalyze}>Re-analyze</Button>
                  )}
                  <Button onClick={handleAnalyze} loading={loading} leftSection={<IconSearch size={16} />} disabled={!url.trim()}>
                    Fetch & analyze
                  </Button>
                </Group>
              </Group>
            </Stack>
          </Paper>

          {error && <Alert icon={<IconAlertCircle size={16} />} color="red" mb="md">{error}</Alert>}

          {meta && (
            <Paper withBorder radius="md" p="md" mb="md">
              <Group justify="space-between" align="flex-start" wrap="wrap">
                <Stack gap={4} style={{ flex: 1, minWidth: 240 }}>
                  <Text fw={700} size="lg" className={styles.title}>{meta.title}</Text>
                  {meta.source_label && <Text size="xs" c="dimmed">{meta.source_label}</Text>}
                  <Group gap="md" wrap="wrap">
                    <Anchor href={meta.url} target="_blank" rel="noopener noreferrer" size="xs">
                      <Group gap={4} wrap="nowrap"><IconExternalLink size={13} />Chuukese article</Group>
                    </Anchor>
                    {meta.english_url && (
                      <Anchor href={meta.english_url} target="_blank" rel="noopener noreferrer" size="xs">
                        <Group gap={4} wrap="nowrap"><IconExternalLink size={13} />{meta.english_title ? `English: ${meta.english_title}` : 'English article'}</Group>
                      </Anchor>
                    )}
                    {!meta.has_english && <Badge color="orange" variant="light" size="sm">No English article found</Badge>}
                  </Group>
                </Stack>
                {(done || paragraphs.length > 0) && (
                  <Group gap="xs">
                    <Badge variant="light" color={totals.pct >= 80 ? 'green' : totals.pct >= 50 ? 'yellow' : 'red'} size="lg">
                      {totals.known} / {totals.words} words in dictionary
                    </Badge>
                  </Group>
                )}
              </Group>
              {loading && (
                <Stack gap={4} mt="sm">
                  <Text size="xs" c="dimmed">Analyzing paragraph {Math.min(progress + 1, meta.paragraph_count)} of {meta.paragraph_count}…</Text>
                  <Progress value={progressPct} animated size="sm" radius="xl" />
                </Stack>
              )}
            </Paper>
          )}

          {selection && (
            <Paper withBorder radius="md" p="sm" mb="md" className={styles.actionBar}>
              <Group gap="sm" wrap="wrap">
                <Text fw={700} className={styles.headword} c="blue.8">{selection.word}</Text>
                {selectedEntry ? (
                  <>
                    {selectedEntry.variant_of && <Badge size="sm" variant="light" color="blue">in dictionary as “{selectedEntry.variant_of}”</Badge>}
                    <Text size="sm">{selectedEntry.english || <Text component="span" c="dimmed" fs="italic">no translation yet</Text>}</Text>
                    {selectedEntry.grammar && <Badge size="xs" variant="outline">{selectedEntry.grammar}</Badge>}
                  </>
                ) : selectedNear && selectedNear.length > 0 ? (
                  <Text size="xs" c="dimmed">not in dictionary · similar: {selectedNear.slice(0, 4).map((s) => s.word).join(', ')}</Text>
                ) : (
                  <Text size="xs" c="dimmed">not in dictionary</Text>
                )}
                <Group gap={4} ml="auto" wrap="nowrap">
                  {isAdmin && (
                    <Button size="xs" variant="light" leftSection={selectedEntry ? <IconPencil size={14} /> : <IconPlus size={14} />} onClick={() => openEditor(selection)}>
                      {selectedEntry ? 'Edit' : 'Add'}
                    </Button>
                  )}
                  {(!selectedEntry || selectedEntry.status === 'untranslated') && (
                    <Button size="xs" variant="light" color="violet" leftSection={<IconSparkles size={14} />} onClick={() => setSuggest(selection)}>
                      Suggest
                    </Button>
                  )}
                  <Button size="xs" variant="light" color="teal" leftSection={<IconQuote size={14} />} onClick={() => setExamplesWord(selection.word)}>
                    Examples
                  </Button>
                  <Tooltip label="Clear selection">
                    <ActionIcon variant="subtle" color="gray" onClick={() => setSelection(null)} aria-label="Clear selection"><IconX size={14} /></ActionIcon>
                  </Tooltip>
                </Group>
              </Group>
            </Paper>
          )}

          {paragraphs.length > 0 && (
            <Stack gap="sm">
              {(() => {
                let bodyCount = 0
                return paragraphs.map((para, pi) => {
                  if (para.is_heading) {
                    return (
                      <Paper key={para.index} withBorder radius="md" p="sm" className={styles.heading}>
                        <Group gap="xs">
                          <Text fw={700} c="violet.9">{para.raw_text}</Text>
                          <Badge size="xs" variant="outline" color="violet" ml="auto">§{pi + 1}</Badge>
                        </Group>
                      </Paper>
                    )
                  }
                  bodyCount += 1
                  const pn = paragraphNumber(para, bodyCount)
                  return (
                    <Fragment key={para.index}>
                      <Group gap="sm" align="center" wrap="nowrap" className={styles.paraMarker} mt={pi === 0 ? 0 : 'sm'}>
                        <Text className={styles.paraNumber}>{pn}</Text>
                        <Text size="sm" fw={600} c="violet.9" style={{ whiteSpace: 'nowrap' }}>
                          Paragraph {pn}
                        </Text>
                        <Divider style={{ flex: 1 }} color="violet.2" />
                        <Text size="xs" c="dimmed">{para.sentences.length} sentence{para.sentences.length === 1 ? '' : 's'}</Text>
                      </Group>
                      {para.sentences.map((s, si) => (
                        <SentenceRow
                          key={`${para.index}-${si}`}
                          sentence={s}
                          label={`${pn}.${si + 1}`}
                          maps={maps[pi]}
                          onGloss={setGloss}
                          onSelect={setSelection}
                          selectedKey={selection?.sentence === s ? selection.key : null}
                        />
                      ))}
                    </Fragment>
                  )
                })
              })()}
            </Stack>
          )}

          {loading && meta && (
            <Group gap="sm" mt="sm">
              <Loader size="sm" />
              <Text size="sm" c="dimmed">Analyzing paragraph {Math.min(progress + 1, meta.paragraph_count)} of {meta.paragraph_count}…</Text>
            </Group>
          )}
          {!isAdmin && paragraphs.length > 0 && (
            <Text size="xs" c="dimmed" mt="md">
              Click a word to see examples or send a suggested entry to the review queue. Editing entries here is for admins.
            </Text>
          )}
        </Box>
      </Group>

      <Divider my="xl" />
      <Text size="xs" c="dimmed" ta="center">
        Articles are fetched live from wol.jw.org and saved so you can reopen them here. Word tints come from our Chuukese dictionary.
      </Text>

      {gloss && <GlossCard gloss={gloss} />}

      <EntryEditor
        opened={!!editor}
        onClose={() => setEditor(null)}
        word={editor?.word || ''}
        entry={editor?.entry}
        prefill={editor?.prefill}
        example={editor?.example}
        onSaved={applySaved}
      />
      <SuggestModal
        word={suggest?.word ?? null}
        sentence={suggest?.sentence.text_only || ''}
        english={suggest?.sentence.english_text || null}
        englishSource="article"
        canAdd={isAdmin}
        onClose={() => setSuggest(null)}
        onUse={(prefill) => { const sel = suggest!; setSuggest(null); openEditor(sel, prefill) }}
      />
      <WolExamplesDrawer word={examplesWord} onClose={() => setExamplesWord(null)} />
    </Container>
  )
}
