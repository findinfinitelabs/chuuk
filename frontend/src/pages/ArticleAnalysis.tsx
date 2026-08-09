import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Container, Title, Text, TextInput, Textarea, Select, Button,
  Stack, Card, Group, Badge, Divider, Loader, Alert, Paper,
  Tooltip, Anchor, ThemeIcon, Progress, RingProgress,
  Center, Modal, Box, ScrollArea, ActionIcon, NavLink as MantineNavLink,
} from '@mantine/core'
import {
  IconWorld, IconLanguage, IconAlertCircle, IconSearch, IconBookmark,
  IconCheck, IconX, IconExternalLink, IconChevronRight, IconPencil,
  IconPlus, IconHistory, IconTrash, IconRefresh,
} from '@tabler/icons-react'
import { useUser } from '../contexts/UserContext'

// ── Types ─────────────────────────────────────────────────────────────────────

interface WordAnalysis {
  original: string
  english: string
  grammar: string
  grammar_modifier?: string
  definition?: string
  found: boolean
  entry_id?: string
  english_token_indices?: number[]
}

interface AnalyzedSentence {
  chuukese: string
  text_only: string
  words: WordAnalysis[]
  english_assembled: string
  english_text?: string
  english_tokens?: string[]
  scriptures: string[]
}

interface StreamedParagraph {
  index: number
  is_heading: boolean
  raw_text: string
  sentences: AnalyzedSentence[]
  sentence_count: number
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

// ── Helpers ───────────────────────────────────────────────────────────────────
function cleanScripture(ref: string): string {
  return ref
    .replace(/^\s*--\s*/, '')   // strip leading " -- "
    .replace(/^\s*\(|\)\s*$/g, '') // strip surrounding ( )
    .trim()
}
function getGrammarColor(grammar: string): string {
  const colors: Record<string, string> = {
    verb: 'blue', noun: 'green', adjective: 'orange', adverb: 'cyan',
    pronoun: 'grape', preposition: 'pink', conjunction: 'indigo',
    particle: 'teal', auxiliary: 'violet', classifier: 'lime',
    demonstrative: 'yellow', interrogative: 'red',
  }
  return grammar ? colors[grammar.toLowerCase()] || 'gray' : 'gray'
}

const GRAMMAR_OPTIONS = [
  'verb', 'noun', 'adjective', 'adverb', 'pronoun', 'preposition',
  'conjunction', 'particle', 'auxiliary', 'classifier', 'demonstrative',
  'interrogative', 'phrase', 'unknown',
].map(v => ({ value: v, label: v.charAt(0).toUpperCase() + v.slice(1) }))

// ── WordChip ──────────────────────────────────────────────────────────────────

interface WordChipProps {
  word: WordAnalysis
  isHighlighted: boolean
  isAdmin: boolean
  onHoverEnter: () => void
  onHoverLeave: () => void
  onEdit: (word: WordAnalysis) => void
}

function WordChip({ word, isHighlighted, isAdmin, onHoverEnter, onHoverLeave, onEdit }: WordChipProps) {
  const chip = (
    <span
      onMouseEnter={onHoverEnter}
      onMouseLeave={onHoverLeave}
      onClick={isAdmin ? () => onEdit(word) : undefined}
      style={{
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'center',
        margin: '2px 4px',
        padding: '3px 8px 2px',
        borderRadius: 4,
        cursor: isAdmin ? 'pointer' : word.found ? 'help' : 'default',
        background: isHighlighted
          ? 'rgba(91,33,182,0.18)'
          : word.found
            ? 'rgba(91,33,182,0.08)'
            : 'rgba(250,82,82,0.10)',
        border: `1px solid ${
          isHighlighted
            ? 'rgba(91,33,182,0.5)'
            : word.found
              ? 'rgba(91,33,182,0.25)'
              : 'rgba(250,82,82,0.35)'
        }`,
        transition: 'all 0.15s',
        verticalAlign: 'top',
      }}
    >
      {/* Chuukese word */}
      <span style={{
        fontSize: 15,
        fontWeight: 700,
        color: isHighlighted ? '#3b1898' : word.found ? '#5f30d8' : '#c0392b',
        lineHeight: 1.4,
        display: 'flex',
        alignItems: 'center',
        gap: 3,
      }}>
        {word.original}
        {isAdmin && <IconPencil size={9} style={{ opacity: 0.4, flexShrink: 0 }} />}
      </span>
      {/* English gloss below */}
      {word.found && word.english && (
        <span style={{
          fontSize: 10,
          color: isHighlighted ? '#5b21b6' : '#7c55de',
          lineHeight: 1.2,
          fontWeight: 500,
          maxWidth: 90,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          opacity: 0.85,
        }}>
          {word.english}
        </span>
      )}
      {!word.found && (
        <span style={{ fontSize: 9, color: '#e03131', opacity: 0.7, lineHeight: 1.2 }}>
          ?
        </span>
      )}
    </span>
  )

  const tooltip = word.found ? (
    <Stack gap={2} p={4}>
      <Text size="sm" fw={700}>{word.english}</Text>
      {word.grammar && (
        <Badge size="xs" color={getGrammarColor(word.grammar)} variant="filled">{word.grammar}</Badge>
      )}
      {word.definition && <Text size="xs" c="dimmed" maw={200}>{word.definition}</Text>}
      {isAdmin && <Text size="xs" c="violet.3" mt={2}>Click to edit</Text>}
    </Stack>
  ) : isAdmin ? (
    <Stack gap={2} p={4}>
      <Text size="xs" c="red.3">Not in dictionary</Text>
      <Text size="xs" c="violet.3">Click to add</Text>
    </Stack>
  ) : null

  if (!tooltip) return chip
  return <Tooltip label={tooltip} withArrow multiline w={220}>{chip}</Tooltip>
}

// ── EnglishSentence ───────────────────────────────────────────────────────────

function EnglishSentence({ sentence, highlightIndices }: {
  sentence: AnalyzedSentence
  highlightIndices: number[]
}) {
  if (sentence.english_tokens && sentence.english_tokens.length > 0) {
    return (
      <Text size="md" fw={600} c="teal.8" style={{ lineHeight: 1.9 }}>
        {sentence.english_tokens.map((tok, ti) => {
          const hl = highlightIndices.includes(ti)
          return (
            <span key={ti} style={{
              background: hl ? 'rgba(91,33,182,0.15)' : 'transparent',
              borderRadius: 3,
              padding: '1px 3px',
              fontWeight: hl ? 700 : 600,
              color: hl ? '#3b1898' : undefined,
              transition: 'background 0.12s',
            }}>
              {tok}{' '}
            </span>
          )
        })}
      </Text>
    )
  }
  return (
    <Stack gap={4}>
      <Text size="xs" c="dimmed" fs="italic">Assembled from dictionary:</Text>
      <Text size="sm" fw={500} c="teal.8" style={{ lineHeight: 1.7 }}>
        {sentence.english_assembled || <Text component="span" c="dimmed" fs="italic">No matches</Text>}
      </Text>
    </Stack>
  )
}

// ── SentenceRow ───────────────────────────────────────────────────────────────

function SentenceRow({ sentence, index, isAdmin, onEditWord }: {
  sentence: AnalyzedSentence
  index: number
  isAdmin: boolean
  onEditWord: (word: WordAnalysis) => void
}) {
  const [hoveredWordIdx, setHoveredWordIdx] = useState<number | null>(null)
  const foundCount = sentence.words.filter(w => w.found).length
  const coveragePct = sentence.words.length > 0 ? Math.round((foundCount / sentence.words.length) * 100) : 0
  const highlightIndices = hoveredWordIdx !== null
    ? sentence.words[hoveredWordIdx]?.english_token_indices ?? []
    : []

  return (
    <Paper withBorder radius="md" p="md" style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'stretch' }}>

        {/* Chuukese side */}
        <Stack gap={6} style={{ flex: '0 0 50%', minWidth: 0 }}>
          <Group gap={6} wrap="nowrap">
            <Badge size="xs" variant="outline" color="violet" style={{ flexShrink: 0 }}>#{index + 1}</Badge>
            <Text size="xs" c="dimmed">Chuukese</Text>
            <Badge size="xs"
              color={coveragePct >= 80 ? 'green' : coveragePct >= 50 ? 'yellow' : 'red'}
              variant="light"
              style={{ marginLeft: 'auto', flexShrink: 0 }}
            >{coveragePct}%</Badge>
          </Group>
          <div style={{ lineHeight: 2.4 }}>
            {sentence.words.map((word, wi) => (
              <WordChip
                key={wi}
                word={word}
                isHighlighted={hoveredWordIdx === wi}
                isAdmin={isAdmin}
                onHoverEnter={() => setHoveredWordIdx(wi)}
                onHoverLeave={() => setHoveredWordIdx(null)}
                onEdit={onEditWord}
              />
            ))}
          </div>
          {sentence.scriptures.length > 0 && (
            <Stack gap={3} mt={4}>
              {sentence.scriptures.map((ref, ri) => (
                <Group key={ri} gap={6} wrap="nowrap">
                  <IconBookmark size={12} color="#7950f2" style={{ flexShrink: 0 }} />
                  <Text size="xs" fw={600} c="violet.7">{cleanScripture(ref)}</Text>
                </Group>
              ))}
            </Stack>
          )}
        </Stack>

        {/* Divider */}
        <Divider orientation="vertical" />

        {/* English side */}
        <Stack gap={6} style={{ flex: 1, minWidth: 0 }}>
          <Text size="xs" c="dimmed">{sentence.english_text ? 'English' : 'English (assembled)'}</Text>
          <EnglishSentence sentence={sentence} highlightIndices={highlightIndices} />
          {hoveredWordIdx !== null && sentence.words[hoveredWordIdx]?.found && (
            <Box p={6} style={{
              borderRadius: 6,
              background: 'rgba(91,33,182,0.06)',
              border: '1px solid rgba(91,33,182,0.2)',
            }}>
              <Group gap={6}>
                <Text size="xs" fw={700} c="violet.7">{sentence.words[hoveredWordIdx].original}</Text>
                <Text size="xs" c="dimmed">→</Text>
                <Text size="xs" fw={700} c="teal.7">{sentence.words[hoveredWordIdx].english}</Text>
                {sentence.words[hoveredWordIdx].grammar && (
                  <Badge size="xs"
                    color={getGrammarColor(sentence.words[hoveredWordIdx].grammar)}
                    variant="light">
                    {sentence.words[hoveredWordIdx].grammar}
                  </Badge>
                )}
              </Group>
            </Box>
          )}
        </Stack>

      </div>
    </Paper>
  )
}

// ── ParagraphBlock ────────────────────────────────────────────────────────────

function ParagraphBlock({ para, paraIndex, isAdmin, onEditWord }: {
  para: StreamedParagraph
  paraIndex: number
  isAdmin: boolean
  onEditWord: (word: WordAnalysis) => void
}) {
  if (para.is_heading) {
    return (
      <Paper withBorder radius="md" p="md"
        style={{ background: 'rgba(91,33,182,0.06)', borderColor: 'rgba(91,33,182,0.2)', marginBottom: 12 }}>
        <Group gap={8}>
          <IconChevronRight size={16} color="#7c55de" />
          <Text fw={700} size="lg" c="violet.8">{para.raw_text}</Text>
          <Badge size="xs" color="violet" variant="outline" style={{ marginLeft: 'auto' }}>
            §{paraIndex + 1}
          </Badge>
        </Group>
      </Paper>
    )
  }
  if (para.sentences.length === 0) return null
  return (
    <Stack gap={6} mb="md">
      {para.sentences.map((s, si) => (
        <SentenceRow key={si} sentence={s} index={si} isAdmin={isAdmin} onEditWord={onEditWord} />
      ))}
    </Stack>
  )
}

// ── HistorySidebar ────────────────────────────────────────────────────────────

function HistorySidebar({ saved, activeId, onSelect, onDelete, isAdmin, loading, sidebarError }: {
  saved: SavedAnalysis[]
  activeId: string | null
  onSelect: (a: SavedAnalysis) => void
  onDelete: (id: string) => void
  isAdmin: boolean
  loading: boolean
  sidebarError: string
}) {
  return (
    <Box style={{ width: 260, flexShrink: 0 }}>
      <Paper withBorder radius="md" p="sm" style={{ position: 'sticky', top: 16 }}>
        <Group gap={6} mb="sm">
          <IconHistory size={16} color="#7c55de" />
          <Text size="sm" fw={700} c="violet.8">Saved Articles</Text>
          {loading && <Loader size="xs" style={{ marginLeft: 'auto' }} />}
        </Group>
        <Divider mb="sm" />
        {sidebarError && (
          <Text size="xs" c="red" mb="xs">{sidebarError}</Text>
        )}
        <ScrollArea h={500} type="auto">
          {saved.length === 0 && (
            <Text size="xs" c="dimmed" ta="center" py="md">No saved analyses yet</Text>
          )}
          {saved.map(a => (
            <Box key={a._id} mb={4} style={{ position: 'relative' }}>
              <MantineNavLink
                label={
                  <Stack gap={2}>
                    <Group gap={4} wrap="nowrap" align="flex-start">
                      <Text size="xs" fw={700} lineClamp={2} style={{ flex: 1 }}
                        c={activeId === a._id ? 'violet.9' : undefined}>
                        {a.chuukese_title || 'Untitled'}
                      </Text>
                      <Anchor
                        href={a.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={e => e.stopPropagation()}
                        style={{ flexShrink: 0, lineHeight: 1 }}
                      >
                        <IconExternalLink size={11} color="#7c55de" />
                      </Anchor>
                    </Group>
                    {a.english_title && (
                      <Text size="xs" c="dimmed" lineClamp={1}>{a.english_title}</Text>
                    )}
                    <Group gap={4} mt={2}>
                      <Badge size="xs" variant="light" color="violet">{a.paragraph_count}¶</Badge>
                      <Badge size="xs" variant="light" color="teal">{a.sentence_count}s</Badge>
                      {a.has_english && <Badge size="xs" variant="dot" color="green">EN</Badge>}
                    </Group>
                  </Stack>
                }
                active={activeId === a._id}
                onClick={() => onSelect(a)}
                style={{ borderRadius: 6, paddingRight: isAdmin ? 32 : undefined }}
              />
              {isAdmin && (
                <ActionIcon
                  size="xs"
                  color="red"
                  variant="subtle"
                  style={{ position: 'absolute', top: 8, right: 4 }}
                  onClick={(e) => { e.stopPropagation(); onDelete(a._id) }}
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

// ── Main component ────────────────────────────────────────────────────────────

export default function ArticleAnalysis() {
  const { role } = useUser()
  const isAdmin = role === 'admin'

  // URL inputs
  const [url, setUrl] = useState('')
  const [englishUrl, setEnglishUrl] = useState('')

  // Streaming state
  const [meta, setMeta] = useState<ArticleMeta | null>(null)
  const [paragraphs, setParagraphs] = useState<StreamedParagraph[]>([])
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')
  const [progress, setProgress] = useState(0)
  const abortRef = useRef<AbortController | null>(null)

  // Sidebar
  const [saved, setSaved] = useState<SavedAnalysis[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [sidebarLoading, setSidebarLoading] = useState(false)
  const [sidebarError, setSidebarError] = useState('')

  // Admin edit modal
  const [editWord, setEditWord] = useState<WordAnalysis | null>(null)
  const [editEnglish, setEditEnglish] = useState('')
  const [editGrammar, setEditGrammar] = useState('')
  const [editDefinition, setEditDefinition] = useState('')
  const [editLoading, setEditLoading] = useState(false)
  const [editError, setEditError] = useState('')

  const totalWords = paragraphs.reduce((s, p) => s + p.sentences.reduce((s2, ss) => s2 + ss.words.length, 0), 0)
  const foundWords = paragraphs.reduce((s, p) => s + p.sentences.reduce((s2, ss) => s2 + ss.words.filter(w => w.found).length, 0), 0)
  const coveragePct = totalWords > 0 ? Math.round((foundWords / totalWords) * 100) : 0
  const progressPct = meta ? Math.round((progress / meta.paragraph_count) * 100) : 0

  // ── Load sidebar on mount ──────────────────────────────────────────────────
  const loadSaved = useCallback(async () => {
    setSidebarLoading(true)
    setSidebarError('')
    try {
      const res = await fetch('/api/article-analyses', { credentials: 'include' })
      if (res.ok) {
        const data = await res.json()
        console.log('[ArticleAnalysis] loaded saved:', data.length, 'items')
        setSaved(data)
      } else {
        const json = await res.json().catch(() => ({}))
        console.error('[ArticleAnalysis] list failed:', res.status, json)
        setSidebarError(`Load failed: ${json.error || res.status}`)
      }
    } catch (err: any) {
      console.error('[ArticleAnalysis] list error:', err)
      setSidebarError(err.message)
    }
    finally { setSidebarLoading(false) }
  }, [])

  useEffect(() => { loadSaved() }, [loadSaved])

  // ── Save completed analysis to DB ─────────────────────────────────────────
  const saveAnalysis = useCallback(async (
    metaArg: ArticleMeta,
    parasArg: StreamedParagraph[],
    sentenceCount: number,
  ) => {
    try {
      const body = {
        url: metaArg.url,
        chuukese_title: metaArg.title,
        english_title: metaArg.english_title || '',
        english_url: metaArg.english_url || '',
        source_label: metaArg.source_label || '',
        has_english: metaArg.has_english,
        paragraph_count: metaArg.paragraph_count,
        sentence_count: sentenceCount,
        paragraphs: parasArg,
      }
      console.log('[ArticleAnalysis] saving analysis, paragraphs:', parasArg.length, 'sentences:', sentenceCount)
      const res = await fetch('/api/article-analyses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
      })
      if (res.ok) {
        const json = await res.json()
        console.log('[ArticleAnalysis] save OK, id:', json.id)
        setActiveId(json.id)
        await loadSaved()
      } else {
        const json = await res.json().catch(() => ({}))
        console.error('[ArticleAnalysis] save failed:', res.status, json)
        setError(`Save failed: ${json.error || res.status}`)
      }
    } catch (err: any) {
      console.error('[ArticleAnalysis] save error:', err)
      setError(`Save failed: ${err.message}`)
    }
  }, [loadSaved])

  // ── Load a saved analysis ─────────────────────────────────────────────────
  const loadAnalysis = async (a: SavedAnalysis) => {
    setActiveId(a._id)
    setError('')
    setLoading(true)
    try {
      const res = await fetch(`/api/article-analyses/${a._id}`, { credentials: 'include' })
      if (!res.ok) throw new Error('Failed to load')
      const doc = await res.json()
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
    } catch (err: any) {
      setError(err.message || 'Failed to load saved analysis')
    } finally {
      setLoading(false)
    }
  }

  // ── Delete saved analysis ─────────────────────────────────────────────────
  const deleteAnalysis = async (id: string) => {
    try {
      await fetch(`/api/article-analyses/${id}`, { method: 'DELETE', credentials: 'include' })
      if (activeId === id) {
        setMeta(null); setParagraphs([]); setDone(false); setActiveId(null)
      }
      await loadSaved()
    } catch { /* silent */ }
  }

  // ── Admin edit modal ──────────────────────────────────────────────────────
  const openEdit = (word: WordAnalysis) => {
    setEditWord(word)
    setEditEnglish(word.english || '')
    setEditGrammar(word.grammar || '')
    setEditDefinition(word.definition || '')
    setEditError('')
  }

  const saveEdit = async () => {
    if (!editWord) return
    setEditLoading(true)
    setEditError('')
    try {
      let updatedEntryId = editWord.entry_id
      if (editWord.found && editWord.entry_id) {
        const res = await fetch('/api/dictionary/update', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ entry_id: editWord.entry_id, english_translation: editEnglish, grammar: editGrammar, definition: editDefinition }),
        })
        const json = await res.json()
        if (!res.ok) throw new Error(json.error || 'Update failed')
      } else {
        const res = await fetch('/api/dictionary/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ chuukese_word: editWord.original, english_translation: editEnglish, grammar: editGrammar, definition: editDefinition, confidence: 100, verified: true }),
        })
        const json = await res.json()
        if (!res.ok) throw new Error(json.error || 'Add failed')
        updatedEntryId = json.entry_id ?? updatedEntryId
      }
      const updatedParagraphs = paragraphs.map(para => ({
        ...para,
        sentences: para.sentences.map(s => ({
          ...s,
          words: s.words.map(w =>
            w.original === editWord.original
              ? { ...w, english: editEnglish, grammar: editGrammar, definition: editDefinition, found: true, entry_id: updatedEntryId }
              : w
          ),
        })),
      }))
      setParagraphs(updatedParagraphs)
      setEditWord(null)
      // Re-persist so changes survive navigation
      if (meta) {
        const sc = updatedParagraphs.reduce((sum, p) => sum + (p.sentence_count ?? p.sentences.length), 0)
        await saveAnalysis(meta, updatedParagraphs, sc)
      }
    } catch (err: any) {
      setEditError(err.message || 'Save failed')
    } finally {
      setEditLoading(false)
    }
  }

  // ── Stop stream ───────────────────────────────────────────────────────────
  const handleStop = () => {
    abortRef.current?.abort()
    setLoading(false)
    setDone(true)
  }

  // ── Fetch & analyze ───────────────────────────────────────────────────────
  const handleAnalyze = async () => {
    if (!url.trim()) { setError('Please enter a URL'); return }
    setLoading(true); setDone(false); setError('')
    setMeta(null); setParagraphs([]); setProgress(0); setActiveId(null)
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
        try { setError(JSON.parse(text).error || 'Request failed') }
        catch { setError(`HTTP ${response.status}`) }
        setLoading(false)
        return
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      const processLine = async (trimmed: string) => {
        if (!trimmed) return
        let event: any
        try { event = JSON.parse(trimmed) } catch { return }

        if (event.type === 'meta') {
          finalMeta = event as ArticleMeta
          setMeta(finalMeta)
          if (event.english_url && !englishUrl) setEnglishUrl(event.english_url)
        } else if (event.type === 'paragraph') {
          const para = event as StreamedParagraph
          finalParas = [...finalParas, para]
          finalSentenceCount += para.sentence_count
          setParagraphs(prev => [...prev, para])
          setProgress(prev => prev + 1)
        } else if (event.type === 'done') {
          finalSentenceCount = event.total_sentences || finalSentenceCount
          setDone(true)
          setLoading(false)
          if (finalMeta) {
            await saveAnalysis(finalMeta, finalParas, finalSentenceCount)
          }
        } else if (event.type === 'error') {
          setError(event.message)
          setLoading(false)
        }
      }

      while (true) {
        const { value, done: streamDone } = await reader.read()
        if (value) buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        // Keep last partial line in buffer unless stream is done
        buffer = streamDone ? '' : (lines.pop() ?? '')
        for (const line of lines) await processLine(line.trim())
        // Flush remaining buffer on stream end
        if (streamDone) {
          if (buffer.trim()) await processLine(buffer.trim())
          break
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') setError(err.message || 'Failed to fetch article')
      setLoading(false)
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <Container size="xl" py="xl">
      <Group align="flex-start" gap="lg" wrap="nowrap">

        {/* ── Left sidebar: saved articles ── */}
        <HistorySidebar
          saved={saved}
          activeId={activeId}
          onSelect={loadAnalysis}
          onDelete={deleteAnalysis}
          isAdmin={isAdmin}
          loading={sidebarLoading}
          sidebarError={sidebarError}
        />

        {/* ── Main content ── */}
        <Stack gap="xl" style={{ flex: 1, minWidth: 0 }}>

          {/* Header */}
          <Paper p="xl" radius="md" withBorder style={{ background: 'var(--mantine-color-violet-9)' }}>
            <Group gap="md">
              <ThemeIcon size={48} radius="md" variant="white" color="violet">
                <IconWorld size={28} />
              </ThemeIcon>
              <div>
                <Title order={1} c="white">Article Analysis</Title>
                <Text c="violet.2" size="sm">
                  Fetch a Chuukese article — every word matched against the dictionary, aligned with the English parallel
                </Text>
              </div>
            </Group>
          </Paper>

          {/* URL inputs */}
          <Card withBorder radius="md" p="xl">
            <Stack gap="md">
              <TextInput
                label="Chuukese Article URL"
                placeholder="https://wol.jw.org/chk/wol/d/r303/lp-te/2026281"
                value={url}
                onChange={e => setUrl(e.target.value)}
                size="md"
                leftSection={<IconWorld size={16} />}
                onKeyDown={e => e.key === 'Enter' && !loading && handleAnalyze()}
                disabled={loading}
              />
              <TextInput
                label="English Article URL (optional — auto-detected for wol.jw.org)"
                placeholder="https://wol.jw.org/en/wol/d/r1/lp-e/2026281"
                value={englishUrl}
                onChange={e => setEnglishUrl(e.target.value)}
                size="sm"
                leftSection={<IconLanguage size={14} />}
                disabled={loading}
              />
              <Group grow>
                <Button
                  onClick={handleAnalyze}
                  loading={loading}
                  size="lg"
                  leftSection={<IconSearch size={20} />}
                  disabled={loading}
                  color="violet"
                >
                  {loading ? 'Analyzing…' : 'Fetch & Analyze Article'}
                </Button>
                {loading && (
                  <Button size="lg" color="red" variant="light" onClick={handleStop}>Stop</Button>
                )}
                {done && activeId && (
                  <Button
                    size="lg"
                    variant="light"
                    color="violet"
                    leftSection={<IconRefresh size={16} />}
                    onClick={handleAnalyze}
                  >
                    Re-analyze
                  </Button>
                )}
              </Group>
            </Stack>
          </Card>

          {/* Error */}
          {error && (
            <Alert icon={<IconAlertCircle size={16} />} color="red" title="Error" radius="md">{error}</Alert>
          )}

          {/* Article meta banner */}
          {meta && (
            <Paper withBorder radius="md" p="xl" style={{ background: 'white' }}>
              <Stack gap="sm">
                <Group justify="space-between" wrap="wrap" align="flex-start">
                  <Stack gap={4} style={{ flex: 1 }}>
                    <Title order={2} c="violet.9">{meta.title}</Title>
                    {meta.source_label && <Text size="xs" c="violet.6">{meta.source_label}</Text>}
                    <Group gap="lg" wrap="wrap">
                      <Anchor href={meta.url} target="_blank" rel="noopener noreferrer" size="sm" c="violet">
                        <Group gap={4}><IconExternalLink size={14} />Chuukese article</Group>
                      </Anchor>
                      {meta.english_url && (
                        <Anchor href={meta.english_url} target="_blank" rel="noopener noreferrer" size="sm" c="teal">
                          <Group gap={4}><IconExternalLink size={14} />
                            {meta.english_title ? `English: ${meta.english_title}` : 'English article'}
                          </Group>
                        </Anchor>
                      )}
                      {!meta.has_english && (
                        <Badge color="orange" variant="light" size="sm">No English article — assembled translations</Badge>
                      )}
                    </Group>
                  </Stack>

                  {!done && loading && (
                    <Center>
                      <RingProgress size={90} thickness={8} roundCaps
                        sections={[{ value: progressPct, color: 'violet' }]}
                        label={<Text ta="center" size="xs" fw={700}>{progress}/{meta.paragraph_count}</Text>}
                      />
                    </Center>
                  )}

                  {done && (
                    <Stack gap={4} align="flex-end">
                      <Group gap={6}>
                        <ThemeIcon size="sm"
                          color={coveragePct >= 80 ? 'green' : coveragePct >= 50 ? 'yellow' : 'red'}
                          variant="light">
                          {coveragePct >= 80 ? <IconCheck size={12} /> : <IconX size={12} />}
                        </ThemeIcon>
                        <Text size="sm" c="dimmed"><strong>{foundWords}</strong> / {totalWords} matched</Text>
                      </Group>
                      <Badge color={coveragePct >= 80 ? 'green' : coveragePct >= 50 ? 'yellow' : 'red'} size="lg">
                        {coveragePct}% coverage
                      </Badge>
                    </Stack>
                  )}
                </Group>

                {(loading || done) && (
                  <Stack gap={4}>
                    <Group justify="space-between">
                      <Text size="xs" c="dimmed">
                        {done
                          ? `Completed — ${meta.paragraph_count} paragraphs`
                          : `Analyzing paragraph ${progress} of ${meta.paragraph_count}…`}
                      </Text>
                      {loading && <Loader size="xs" />}
                    </Group>
                    <Progress value={progressPct} animated={loading} color="violet" size="sm" radius="xl" />
                  </Stack>
                )}
              </Stack>
            </Paper>
          )}

          {/* Legend */}
          {paragraphs.length > 0 && (
            <Paper withBorder radius="md" p="md">
              <Group gap="lg" wrap="wrap">
                <Text size="sm" fw={600} c="dimmed">Legend:</Text>
                <Group gap={6}>
                  <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: 2, background: 'rgba(91,33,182,0.1)', border: '1px solid rgba(91,33,182,0.3)' }} />
                  <Text size="sm">Found — shows English gloss + hover to highlight</Text>
                </Group>
                <Group gap={6}>
                  <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: 2, background: 'rgba(250,82,82,0.12)', border: '1px solid rgba(250,82,82,0.4)' }} />
                  <Text size="sm">Not in dictionary</Text>
                </Group>
                <Group gap={6}><IconBookmark size={12} color="#7950f2" /><Text size="sm">Scripture</Text></Group>
                {isAdmin && (
                  <Group gap={6}><IconPencil size={12} color="#7c55de" />
                    <Text size="sm" c="violet.6">Click any word to edit</Text>
                  </Group>
                )}
              </Group>
            </Paper>
          )}

          {/* Paragraphs */}
          {paragraphs.map((para, idx) => (
            <ParagraphBlock key={para.index} para={para} paraIndex={idx}
              isAdmin={isAdmin} onEditWord={openEdit} />
          ))}

          {loading && meta && (
            <Card withBorder radius="md" p="md" style={{ opacity: 0.4 }}>
              <Group gap="md">
                <Loader size="sm" color="violet" />
                <Text size="sm" c="dimmed">
                  Analyzing paragraph {progress + 1} of {meta.paragraph_count}…
                </Text>
              </Group>
            </Card>
          )}
        </Stack>
      </Group>

      {/* Admin edit / add modal */}
      <Modal
        opened={!!editWord}
        onClose={() => setEditWord(null)}
        title={
          <Group gap={8}>
            {editWord?.found ? <IconPencil size={16} /> : <IconPlus size={16} />}
            <Text fw={700}>
              {editWord?.found ? 'Edit' : 'Add'} — <Text component="span" c="violet.7">{editWord?.original}</Text>
            </Text>
          </Group>
        }
        size="md"
      >
        {editWord && (
          <Stack gap="md">
            <TextInput label="Chuukese word" value={editWord.original} readOnly disabled />
            <TextInput label="English translation" value={editEnglish}
              onChange={e => setEditEnglish(e.target.value)} placeholder="English meaning…" required />
            <Select label="Grammar type" value={editGrammar || null}
              onChange={v => setEditGrammar(v ?? '')}
              data={GRAMMAR_OPTIONS} placeholder="Select grammar type" searchable />
            <Textarea label="Definition / notes" value={editDefinition}
              onChange={e => setEditDefinition(e.target.value)}
              placeholder="Extended definition…" minRows={2} />
            {editError && (
              <Alert icon={<IconAlertCircle size={14} />} color="red" p="xs">{editError}</Alert>
            )}
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setEditWord(null)}>Cancel</Button>
              <Button onClick={saveEdit} loading={editLoading}
                disabled={!editEnglish.trim()} color="violet"
                leftSection={editWord.found ? <IconPencil size={14} /> : <IconPlus size={14} />}>
                {editWord.found ? 'Save changes' : 'Add to dictionary'}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Container>
  )
}
