import { useState, useRef } from 'react'
import {
  Container,
  Title,
  Text,
  TextInput,
  Textarea,
  Select,
  Button,
  Stack,
  Card,
  Group,
  Badge,
  Divider,
  Loader,
  Alert,
  Paper,
  Grid,
  Tooltip,
  Anchor,
  ThemeIcon,
  Progress,
  RingProgress,
  Center,
  Modal,
  Box,
} from '@mantine/core'
import {
  IconWorld,
  IconLanguage,
  IconAlertCircle,
  IconSearch,
  IconBookmark,
  IconCheck,
  IconX,
  IconExternalLink,
  IconChevronRight,
  IconPencil,
  IconPlus,
} from '@tabler/icons-react'
import { useUser } from '../contexts/UserContext'

// ── Interfaces ────────────────────────────────────────────────────────────────

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

interface ArticleMeta {
  title: string
  url: string
  source_label: string
  paragraph_count: number
  english_url?: string
  english_title?: string
  has_english: boolean
}

interface StreamedParagraph {
  index: number
  is_heading: boolean
  raw_text: string
  sentences: AnalyzedSentence[]
  sentence_count: number
}

// ── Helpers ───────────────────────────────────────────────────────────────────

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
  const clickable = isAdmin
  const chip = (
    <span
      onMouseEnter={onHoverEnter}
      onMouseLeave={onHoverLeave}
      onClick={clickable ? () => onEdit(word) : undefined}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 3,
        margin: '2px 3px',
        padding: '2px 8px',
        borderRadius: 4,
        fontSize: 15,
        fontWeight: 600,
        cursor: clickable ? 'pointer' : word.found ? 'help' : 'default',
        background: isHighlighted
          ? 'rgba(12,166,120,0.22)'
          : word.found
            ? 'rgba(34,139,230,0.12)'
            : 'rgba(250,82,82,0.10)',
        border: `1px solid ${
          isHighlighted
            ? 'rgba(12,166,120,0.5)'
            : word.found
              ? 'rgba(34,139,230,0.35)'
              : 'rgba(250,82,82,0.35)'
        }`,
        color: isHighlighted ? '#0b7a56' : word.found ? '#1971c2' : '#c0392b',
        lineHeight: 1.6,
        transition: 'all 0.15s',
      }}
    >
      {word.original}
      {clickable && (
        <IconPencil size={10} style={{ opacity: 0.5, flexShrink: 0 }} />
      )}
    </span>
  )

  const tooltip = word.found ? (
    <Stack gap={2} p={4}>
      <Text size="sm" fw={700}>{word.english}</Text>
      {word.grammar && (
        <Badge size="xs" color={getGrammarColor(word.grammar)} variant="filled">
          {word.grammar}
        </Badge>
      )}
      {word.definition && <Text size="xs" c="dimmed" maw={200}>{word.definition}</Text>}
      {isAdmin && <Text size="xs" c="blue.3" mt={2}>Click to edit</Text>}
    </Stack>
  ) : isAdmin ? (
    <Stack gap={2} p={4}>
      <Text size="xs" c="red.3">Not in dictionary</Text>
      <Text size="xs" c="blue.3">Click to add</Text>
    </Stack>
  ) : null

  if (!tooltip) return chip

  return (
    <Tooltip label={tooltip} withArrow multiline w={220}>
      {chip}
    </Tooltip>
  )
}

// ── EnglishSentence ───────────────────────────────────────────────────────────

function EnglishSentence({
  sentence,
  highlightIndices,
}: {
  sentence: AnalyzedSentence
  highlightIndices: number[]
}) {
  if (sentence.english_tokens && sentence.english_tokens.length > 0) {
    return (
      <Text size="md" fw={600} c="teal.8" style={{ lineHeight: 1.9 }}>
        {sentence.english_tokens.map((tok, ti) => {
          const hl = highlightIndices.includes(ti)
          return (
            <span
              key={ti}
              style={{
                background: hl ? 'rgba(12,166,120,0.25)' : 'transparent',
                borderRadius: 3,
                padding: '1px 3px',
                fontWeight: hl ? 700 : 600,
                color: hl ? '#0b7a56' : undefined,
                transition: 'background 0.12s',
              }}
            >
              {tok}{' '}
            </span>
          )
        })}
      </Text>
    )
  }
  // Fallback: assembled from dictionary
  return (
    <Stack gap={4}>
      <Text size="xs" c="dimmed" fs="italic">No English article — assembled from dictionary:</Text>
      <Text size="sm" fw={500} c="teal.8" style={{ lineHeight: 1.7 }}>
        {sentence.english_assembled || (
          <Text component="span" c="dimmed" fs="italic">No matches found</Text>
        )}
      </Text>
    </Stack>
  )
}

// ── SentenceRow ───────────────────────────────────────────────────────────────

interface SentenceRowProps {
  sentence: AnalyzedSentence
  index: number
  isAdmin: boolean
  onEditWord: (word: WordAnalysis) => void
}

function SentenceRow({ sentence, index, isAdmin, onEditWord }: SentenceRowProps) {
  const [hoveredWordIdx, setHoveredWordIdx] = useState<number | null>(null)
  const foundCount = sentence.words.filter(w => w.found).length
  const totalCount = sentence.words.length
  const coveragePct = totalCount > 0 ? Math.round((foundCount / totalCount) * 100) : 0

  const highlightIndices =
    hoveredWordIdx !== null
      ? sentence.words[hoveredWordIdx]?.english_token_indices ?? []
      : []

  return (
    <Paper withBorder radius="md" p="md" style={{ marginBottom: 8 }}>
      <Grid gutter="md">
        {/* Left: Chuukese word chips */}
        <Grid.Col span={{ base: 12, sm: 6 }}>
          <Stack gap={6}>
            <Group gap={6} wrap="nowrap">
              <Badge size="xs" variant="outline" color="blue" style={{ flexShrink: 0 }}>
                #{index + 1}
              </Badge>
              <Text size="xs" c="dimmed">Chuukese</Text>
              <Badge
                size="xs"
                color={coveragePct >= 80 ? 'green' : coveragePct >= 50 ? 'yellow' : 'red'}
                variant="light"
                style={{ marginLeft: 'auto', flexShrink: 0 }}
              >
                {coveragePct}%
              </Badge>
            </Group>
            <div style={{ lineHeight: 2 }}>
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
              <Group gap={4} mt={2}>
                <IconBookmark size={12} color="#868e96" />
                {sentence.scriptures.map((ref, ri) => (
                  <Badge key={ri} size="xs" color="violet" variant="light">{ref}</Badge>
                ))}
              </Group>
            )}
          </Stack>
        </Grid.Col>

        <Grid.Col
          span={{ base: 12, sm: 'auto' }}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <Divider orientation="vertical" style={{ height: '100%' }} />
        </Grid.Col>

        {/* Right: real English sentence with token highlights */}
        <Grid.Col span={{ base: 12, sm: 6 }}>
          <Stack gap={6}>
            <Text size="xs" c="dimmed">
              {sentence.english_text ? 'English' : 'English (assembled)'}
            </Text>
            <EnglishSentence sentence={sentence} highlightIndices={highlightIndices} />
            {/* Word-pair legend */}
            {hoveredWordIdx !== null && sentence.words[hoveredWordIdx]?.found && (
              <Box
                p={6}
                style={{
                  borderRadius: 6,
                  background: 'rgba(12,166,120,0.08)',
                  border: '1px solid rgba(12,166,120,0.25)',
                }}
              >
                <Group gap={6}>
                  <Text size="xs" fw={700} c="blue.7">
                    {sentence.words[hoveredWordIdx].original}
                  </Text>
                  <Text size="xs" c="dimmed">→</Text>
                  <Text size="xs" fw={700} c="teal.7">
                    {sentence.words[hoveredWordIdx].english}
                  </Text>
                  {sentence.words[hoveredWordIdx].grammar && (
                    <Badge size="xs" color={getGrammarColor(sentence.words[hoveredWordIdx].grammar)} variant="light">
                      {sentence.words[hoveredWordIdx].grammar}
                    </Badge>
                  )}
                </Group>
              </Box>
            )}
          </Stack>
        </Grid.Col>
      </Grid>
    </Paper>
  )
}

// ── ParagraphBlock ────────────────────────────────────────────────────────────

interface ParagraphBlockProps {
  para: StreamedParagraph
  paraIndex: number
  isAdmin: boolean
  onEditWord: (word: WordAnalysis) => void
}

function ParagraphBlock({ para, paraIndex, isAdmin, onEditWord }: ParagraphBlockProps) {
  if (para.is_heading) {
    return (
      <Paper withBorder radius="md" p="md" bg="dark.6" style={{ marginBottom: 12 }}>
        <Group gap={8}>
          <IconChevronRight size={16} color="#74c0fc" />
          <Text fw={700} size="lg" c="blue.3">{para.raw_text}</Text>
          <Badge size="xs" color="blue" variant="outline" style={{ marginLeft: 'auto' }}>
            Section {paraIndex + 1}
          </Badge>
        </Group>
      </Paper>
    )
  }

  if (para.sentences.length === 0) return null

  return (
    <Stack gap={6} mb="md">
      {para.sentences.map((sentence, si) => (
        <SentenceRow
          key={si}
          sentence={sentence}
          index={si}
          isAdmin={isAdmin}
          onEditWord={onEditWord}
        />
      ))}
    </Stack>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

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

  // Admin edit state
  const [editWord, setEditWord] = useState<WordAnalysis | null>(null)
  const [editEnglish, setEditEnglish] = useState('')
  const [editGrammar, setEditGrammar] = useState('')
  const [editDefinition, setEditDefinition] = useState('')
  const [editLoading, setEditLoading] = useState(false)
  const [editError, setEditError] = useState('')

  const totalWords = paragraphs.reduce((sum, p) => sum + p.sentences.reduce((s2, s) => s2 + s.words.length, 0), 0)
  const foundWords = paragraphs.reduce((sum, p) => sum + p.sentences.reduce((s2, s) => s2 + s.words.filter(w => w.found).length, 0), 0)
  const coveragePct = totalWords > 0 ? Math.round((foundWords / totalWords) * 100) : 0
  const progressPct = meta ? Math.round((progress / meta.paragraph_count) * 100) : 0

  const openEditModal = (word: WordAnalysis) => {
    setEditWord(word)
    setEditEnglish(word.english || '')
    setEditGrammar(word.grammar || '')
    setEditDefinition(word.definition || '')
    setEditError('')
  }

  const closeEditModal = () => {
    setEditWord(null)
    setEditError('')
  }

  const saveEdit = async () => {
    if (!editWord) return
    setEditLoading(true)
    setEditError('')
    try {
      if (editWord.found && editWord.entry_id) {
        // Update existing entry
        const res = await fetch('/api/dictionary/update', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            entry_id: editWord.entry_id,
            english_translation: editEnglish,
            grammar: editGrammar,
            definition: editDefinition,
          }),
        })
        const json = await res.json()
        if (!res.ok) throw new Error(json.error || 'Update failed')
      } else {
        // Add new entry
        const res = await fetch('/api/dictionary/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            chuukese_word: editWord.original,
            english_translation: editEnglish,
            grammar: editGrammar,
            definition: editDefinition,
            confidence: 100,
            verified: true,
          }),
        })
        const json = await res.json()
        if (!res.ok) throw new Error(json.error || 'Add failed')
      }
      // Patch the word in-place in paragraphs state
      setParagraphs(prev => prev.map(para => ({
        ...para,
        sentences: para.sentences.map(s => ({
          ...s,
          words: s.words.map(w =>
            w.original === editWord.original
              ? { ...w, english: editEnglish, grammar: editGrammar, definition: editDefinition, found: true }
              : w
          ),
        })),
      })))
      closeEditModal()
    } catch (err: any) {
      setEditError(err.message || 'Save failed')
    } finally {
      setEditLoading(false)
    }
  }

  const handleStop = () => {
    abortRef.current?.abort()
    setLoading(false)
    setDone(true)
  }

  const handleAnalyze = async () => {
    if (!url.trim()) { setError('Please enter a URL'); return }
    setLoading(true)
    setDone(false)
    setError('')
    setMeta(null)
    setParagraphs([])
    setProgress(0)

    abortRef.current = new AbortController()

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

      while (true) {
        const { value, done: streamDone } = await reader.read()
        if (streamDone) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed) continue
          let event: any
          try { event = JSON.parse(trimmed) } catch { continue }

          if (event.type === 'meta') {
            setMeta(event as ArticleMeta)
            if (event.english_url && !englishUrl) setEnglishUrl(event.english_url)
          } else if (event.type === 'paragraph') {
            setParagraphs(prev => [...prev, event as StreamedParagraph])
            setProgress(prev => prev + 1)
          } else if (event.type === 'done') {
            setDone(true)
            setLoading(false)
          } else if (event.type === 'error') {
            setError(event.message)
            setLoading(false)
            return
          }
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') setError(err.message || 'Failed to fetch article')
      setLoading(false)
    }
  }

  return (
    <Container size="xl" py="xl">
      <Stack gap="xl">
        {/* Header */}
        <Paper p="xl" radius="md" withBorder style={{ background: 'var(--mantine-color-violet-9)' }}>
          <Group gap="md">
            <ThemeIcon size={48} radius="md" variant="white" color="violet">
              <IconWorld size={28} />
            </ThemeIcon>
            <div>
              <Title order={1} c="white">Article Analysis</Title>
              <Text c="violet.2" size="sm">
                Fetch a Chuukese article URL — every word matched against the dictionary, aligned with the English parallel article
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
              onChange={(e) => setUrl(e.target.value)}
              size="md"
              leftSection={<IconWorld size={16} />}
              onKeyDown={(e) => e.key === 'Enter' && !loading && handleAnalyze()}
              disabled={loading}
            />
            <TextInput
              label="English Article URL (optional — auto-detected for wol.jw.org)"
              placeholder="https://wol.jw.org/en/wol/d/r1/lp-e/2026281"
              value={englishUrl}
              onChange={(e) => setEnglishUrl(e.target.value)}
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
              >
                {loading ? 'Analyzing…' : 'Fetch & Analyze Article'}
              </Button>
              {loading && (
                <Button size="lg" color="red" variant="light" onClick={handleStop}>
                  Stop
                </Button>
              )}
            </Group>
          </Stack>
        </Card>

        {/* Error */}
        {error && (
          <Alert icon={<IconAlertCircle size={16} />} color="red" title="Error" radius="md">
            {error}
          </Alert>
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
                    <Anchor href={meta.url} target="_blank" rel="noopener noreferrer" size="sm">
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
                      <Badge color="orange" variant="light" size="sm">No English article — using assembled translations</Badge>
                    )}
                  </Group>
                </Stack>

                {!done && loading && (
                  <Center>
                    <RingProgress
                      size={90}
                      thickness={8}
                      roundCaps
                      sections={[{ value: progressPct, color: 'blue' }]}
                      label={<Text ta="center" size="xs" fw={700}>{progress}/{meta.paragraph_count}</Text>}
                    />
                  </Center>
                )}

                {done && (
                  <Stack gap={4} align="flex-end">
                    <Group gap={6}>
                      <ThemeIcon size="sm" color={coveragePct >= 80 ? 'green' : coveragePct >= 50 ? 'yellow' : 'red'} variant="light">
                        {coveragePct >= 80 ? <IconCheck size={12} /> : <IconX size={12} />}
                      </ThemeIcon>
                      <Text size="sm" c="dimmed"><strong>{foundWords}</strong> / {totalWords} words matched</Text>
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
                  <Progress value={progressPct} animated={loading} color="blue" size="sm" radius="xl" />
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
                <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: 2, background: 'rgba(34,139,230,0.15)', border: '1px solid rgba(34,139,230,0.4)' }} />
                <Text size="sm">Found — hover to highlight English word</Text>
              </Group>
              <Group gap={6}>
                <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: 2, background: 'rgba(250,82,82,0.12)', border: '1px solid rgba(250,82,82,0.4)' }} />
                <Text size="sm">Not in dictionary</Text>
              </Group>
              <Group gap={6}>
                <IconBookmark size={12} color="#7950f2" />
                <Text size="sm">Scripture reference</Text>
              </Group>
              {isAdmin && (
                <Group gap={6}>
                  <IconPencil size={12} color="#228be6" />
                  <Text size="sm" c="blue.6">Click any word to edit translation</Text>
                </Group>
              )}
            </Group>
          </Paper>
        )}

        {/* Streamed paragraphs */}
        {paragraphs.map((para, idx) => (
          <ParagraphBlock
            key={para.index}
            para={para}
            paraIndex={idx}
            isAdmin={isAdmin}
            onEditWord={openEditModal}
          />
        ))}

        {/* Loading next paragraph */}
        {loading && meta && (
          <Card withBorder radius="md" p="md" style={{ opacity: 0.4 }}>
            <Group gap="md">
              <Loader size="sm" />
              <Text size="sm" c="dimmed">
                Analyzing paragraph {progress + 1} of {meta.paragraph_count}…
              </Text>
            </Group>
          </Card>
        )}
      </Stack>

      {/* Admin edit / add modal */}
      <Modal
        opened={!!editWord}
        onClose={closeEditModal}
        title={
          <Group gap={8}>
            {editWord?.found ? <IconPencil size={16} /> : <IconPlus size={16} />}
            <Text fw={700}>
              {editWord?.found ? 'Edit' : 'Add'} — <Text component="span" c="blue.7">{editWord?.original}</Text>
            </Text>
          </Group>
        }
        size="md"
      >
        {editWord && (
          <Stack gap="md">
            <TextInput label="Chuukese word" value={editWord.original} readOnly disabled />
            <TextInput
              label="English translation"
              value={editEnglish}
              onChange={(e) => setEditEnglish(e.target.value)}
              placeholder="English meaning…"
              required
            />
            <Select
              label="Grammar type"
              value={editGrammar || null}
              onChange={(v) => setEditGrammar(v ?? '')}
              data={GRAMMAR_OPTIONS}
              placeholder="Select grammar type"
              searchable
            />
            <Textarea
              label="Definition / notes"
              value={editDefinition}
              onChange={(e) => setEditDefinition(e.target.value)}
              placeholder="Extended definition or usage notes…"
              minRows={2}
            />
            {editError && (
              <Alert icon={<IconAlertCircle size={14} />} color="red" p="xs">
                {editError}
              </Alert>
            )}
            <Group justify="flex-end">
              <Button variant="default" onClick={closeEditModal}>Cancel</Button>
              <Button
                onClick={saveEdit}
                loading={editLoading}
                disabled={!editEnglish.trim()}
                leftSection={editWord.found ? <IconPencil size={14} /> : <IconPlus size={14} />}
              >
                {editWord.found ? 'Save changes' : 'Add to dictionary'}
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Container>
  )
}
