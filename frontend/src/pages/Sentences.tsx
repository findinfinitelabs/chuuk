/**
 * Sentences — word-by-word analysis of a Chuukese sentence against the
 * dictionary, in the same idiom as the Watchtower Library page: every word
 * tinted by its dictionary status with a hover gloss, the sentence's English
 * under it, and a word table with edit / suggest / examples actions.
 *
 * The English block prefers, in order: a translation the user added (which
 * replaces the model's), the exact source text found on wol.jw.org, and only
 * then the model's guess. Completed analyses are saved and listed in the
 * sidebar so they can be reopened without re-running the lookups.
 */
import { useCallback, useEffect, useState } from 'react'
import {
  Container, Title, Text, Textarea, Button, Stack, Card, Group, Badge, Loader, Alert, Paper, Table, ActionIcon,
  Tooltip, Box, Divider, Anchor, ScrollArea, NavLink as MantineNavLink,
} from '@mantine/core'
import {
  IconLanguage, IconAlertCircle, IconPencil, IconPlus, IconSparkles, IconQuote, IconRobot, IconExternalLink,
  IconDeviceFloppy, IconBooks, IconHistory, IconTrash, IconUserCheck,
} from '@tabler/icons-react'
import axios from 'axios'
import { GlossedWords, GlossCard, GlossLegend } from '../components/GlossedText'
import type { Dictionary, SimilarMap, Gloss, DictEntry, SimilarWord } from '../components/GlossedText'
import { glossStatus, GLOSS_COLOR } from '../components/glossUtils'
import type { PhraseMap } from '../components/glossUtils'
import { EntryEditor } from '../components/analysis/EntryEditor'
import type { EntryPrefill } from '../components/analysis/EntryEditor'
import { SuggestModal } from '../components/analysis/SuggestModal'
import { WolExamplesDrawer } from '../components/analysis/WolExamples'
import { SavePairModal } from '../components/analysis/SavePairModal'
import type { PairSource } from '../components/analysis/SavePairModal'
import styles from '../components/analysis/analysis.module.css'
import AddToTalk from '../components/AddToTalk'

// ── Types ─────────────────────────────────────────────────────────────────────

interface SentenceAnalysis {
  sentence: string
  words: { word: string; key: string }[]
  dictionary: Dictionary
  similar: SimilarMap
  phrases: PhraseMap
}

/** The sentence as found on wol.jw.org, with its English. */
interface SourceMatch {
  chuukese: string
  segments: { text: string; match: boolean }[]
  title: string | null
  link: string | null
  citation: string | null
  english: { text: string; scope: 'sentence' | 'paragraph' | 'verse'; citation: string | null; link: string; title: string | null } | null
  score: number
  exact: boolean
}

type Source =
  | { state: 'idle' }
  | { state: 'loading' }
  | { state: 'found'; match: SourceMatch }
  | { state: 'none' }
  | { state: 'error'; message: string }

type Translation =
  | { state: 'idle' }
  | { state: 'loading' }
  | { state: 'done'; text: string; engine: string }
  | { state: 'unavailable'; engine: string }
  | { state: 'error'; message: string }

/** A translation the user confirmed or typed, saved as a training pair. */
interface UserTranslation {
  english: string
  source: 'wol.jw.org' | 'user'
  citation?: string | null
  link?: string | null
  title?: string | null
  saved_at?: string
  saved_by?: string
}

/** One row in the saved-analyses sidebar. */
interface SavedAnalysis {
  id: string
  sentence: string
  word_count: number
  known_count: number
  has_source: boolean
  has_user_translation: boolean
  created_by?: string
  updated_at?: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function errorMessage(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) return e.response?.data?.error || fallback
  return fallback
}

/** One row per distinct word, in order of first appearance. */
function distinctWords(words: { word: string; key: string }[]) {
  const seen = new Set<string>()
  return words.filter((w) => {
    if (/^\d+$/.test(w.key)) return false // numbers are never headwords
    if (seen.has(w.key)) return false
    seen.add(w.key)
    return true
  })
}

function StatusBadge({ entry, near }: { entry?: DictEntry; near?: SimilarWord[] }) {
  const status = glossStatus(entry, near)
  if (status === 'accent') return <Badge size="sm" variant="light" color={GLOSS_COLOR.accent}>as “{entry!.variant_of}”</Badge>
  if (status === 'translated') return <Badge size="sm" variant="light" color={GLOSS_COLOR.translated}>in dictionary</Badge>
  if (status === 'untranslated') return <Badge size="sm" variant="light" color={GLOSS_COLOR.untranslated}>no translation</Badge>
  if (status === 'similar') return <Badge size="sm" variant="light" color={GLOSS_COLOR.similar}>{near!.length} similar</Badge>
  return <Badge size="sm" variant="outline" color="gray">not found</Badge>
}

function formatWhen(iso?: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString()
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

function HistorySidebar({
  saved, activeId, loading, error, onSelect, onDelete,
}: {
  saved: SavedAnalysis[]
  activeId: string | null
  loading: boolean
  error: string
  onSelect: (s: SavedAnalysis) => void
  onDelete: (id: string) => void
}) {
  return (
    <Box style={{ width: 250, flexShrink: 0 }}>
      <Paper withBorder radius="md" p="sm" style={{ position: 'sticky', top: 16 }}>
        <Group gap={6} mb="sm">
          <IconHistory size={16} color="#7c55de" />
          <Text size="sm" fw={700} c="violet.8">Saved Sentences</Text>
          {loading && <Loader size="xs" style={{ marginLeft: 'auto' }} />}
        </Group>
        <Divider mb="sm" />
        {error && <Text size="xs" c="red" mb="xs">{error}</Text>}
        <ScrollArea h={520} type="auto">
          {saved.length === 0 && !loading && !error && (
            <Text size="xs" c="dimmed" ta="center" py="md">Sentences you analyze are saved here automatically.</Text>
          )}
          {saved.map((item) => (
            <Box key={item.id} mb={4} style={{ position: 'relative' }}>
              <MantineNavLink
                label={
                  <Stack gap={2}>
                    <Text size="xs" fw={700} lineClamp={2} c={activeId === item.id ? 'violet.9' : undefined}>
                      {item.sentence}
                    </Text>
                    <Group gap={4} mt={2}>
                      <Badge size="xs" variant="light" color="blue">{item.known_count}/{item.word_count}</Badge>
                      {item.has_user_translation && <Badge size="xs" variant="dot" color="green">translated</Badge>}
                      {!item.has_user_translation && item.has_source && <Badge size="xs" variant="dot" color="teal">on WOL</Badge>}
                    </Group>
                    {item.updated_at && <Text size="xs" c="dimmed">{new Date(item.updated_at).toLocaleDateString()}</Text>}
                  </Stack>
                }
                active={activeId === item.id}
                onClick={() => onSelect(item)}
                style={{ borderRadius: 6, paddingRight: 30 }}
              />
              <ActionIcon
                size="xs" color="red" variant="subtle"
                style={{ position: 'absolute', top: 8, right: 4 }}
                onClick={(e) => { e.stopPropagation(); onDelete(item.id) }}
                aria-label={`Delete saved sentence ${item.sentence}`}
              >
                <IconTrash size={12} />
              </ActionIcon>
            </Box>
          ))}
        </ScrollArea>
      </Paper>
    </Box>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

function Sentences() {
  const [sentence, setSentence] = useState('')
  const [analysis, setAnalysis] = useState<SentenceAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [translation, setTranslation] = useState<Translation>({ state: 'idle' })
  const [source, setSource] = useState<Source>({ state: 'idle' })
  const [userTranslation, setUserTranslation] = useState<UserTranslation | null>(null)
  const [gloss, setGloss] = useState<Gloss | null>(null)
  const [savePair, setSavePair] = useState<{ english: string; origin: PairSource } | null>(null)

  // Modals and the examples drawer
  const [editor, setEditor] = useState<{ word: string; entry?: DictEntry | null; prefill?: EntryPrefill | null } | null>(null)
  const [suggestWord, setSuggestWord] = useState<string | null>(null)
  const [examplesWord, setExamplesWord] = useState<string | null>(null)

  // Saved analyses
  const [saved, setSaved] = useState<SavedAnalysis[]>([])
  const [savedLoading, setSavedLoading] = useState(false)
  const [savedError, setSavedError] = useState('')
  const [activeId, setActiveId] = useState<string | null>(null)
  const [fromSaved, setFromSaved] = useState(false)

  const refreshSaved = useCallback(async () => {
    setSavedLoading(true)
    try {
      const res = await axios.get('/api/sentence-analyses')
      setSaved(Array.isArray(res.data) ? res.data : [])
      setSavedError('')
    } catch (e) {
      setSavedError(axios.isAxiosError(e) && e.response?.status === 404
        ? 'Saving needs the server restarted with the latest code.'
        : errorMessage(e, 'Could not load saved sentences'))
    } finally {
      setSavedLoading(false)
    }
  }, [])

  useEffect(() => { refreshSaved() }, [refreshSaved])

  /** Store the analysis so it can be reopened. A failure never disturbs the page. */
  const persist = useCallback(async (
    a: SentenceAnalysis,
    t: Translation,
    s: Source,
    ut: UserTranslation | null,
  ) => {
    try {
      const res = await axios.post('/api/sentence-analyses', {
        sentence: a.sentence,
        words: a.words,
        dictionary: a.dictionary,
        similar: a.similar,
        phrases: a.phrases,
        translation: t.state === 'done' ? { text: t.text, engine: t.engine } : null,
        source: s.state === 'found' ? s.match : null,
        user_translation: ut,
      })
      if (res.data?.id) setActiveId(res.data.id)
      refreshSaved()
    } catch {
      // Saving is a convenience; the analysis on screen is what matters.
    }
  }, [refreshSaved])

  /** Look for the sentence itself on wol.jw.org; its English is the real
   *  translation, where the model's is only a guess. */
  const findSource = async (text: string): Promise<Source> => {
    try {
      const res = await axios.post('/api/sentences/source', { sentence: text })
      return res.data?.match ? { state: 'found', match: res.data.match } : { state: 'none' }
    } catch (e) {
      return { state: 'error', message: errorMessage(e, 'Could not reach wol.jw.org') }
    }
  }

  const translate = async (text: string): Promise<Translation> => {
    try {
      const res = await axios.post('/api/sentences/translate', { text })
      if (res.data?.available === false) return { state: 'unavailable', engine: res.data.engine_name || 'model' }
      return { state: 'done', text: res.data.translation || '', engine: res.data.engine_name || 'model' }
    } catch (e) {
      return { state: 'error', message: errorMessage(e, 'Translation failed') }
    }
  }

  /** Full analysis of a new sentence: dictionary, WOL source and model in parallel, then saved. */
  const analyze = useCallback(async (text: string) => {
    setLoading(true); setError('')
    setTranslation({ state: 'loading' }); setSource({ state: 'loading' })
    setUserTranslation(null); setActiveId(null); setFromSaved(false)
    // Already analysed by someone? Reuse it (and file it in my list) rather
    // than running the dictionary, WOL and model lookups again.
    try {
      const res = await axios.get('/api/sentence-analyses/lookup', { params: { sentence: text } })
      if (res.data?.found) {
        const doc = res.data
        setSentence(doc.sentence)
        setAnalysis({ sentence: doc.sentence, words: doc.words || [], dictionary: doc.dictionary || {}, similar: doc.similar || {}, phrases: doc.phrases || {} })
        setTranslation(doc.translation?.text !== undefined ? { state: 'done', text: doc.translation.text, engine: doc.translation.engine || 'model' } : { state: 'idle' })
        setSource(doc.source ? { state: 'found', match: doc.source } : { state: 'none' })
        setUserTranslation(doc.user_translation || null)
        setActiveId(doc.id); setFromSaved(true); setLoading(false)
        refreshSaved()
        return
      }
    } catch {
      // Not saved yet (404) or lookup failed: analyse afresh.
    }
    const sourceP = findSource(text).then((s) => { setSource(s); return s })
    const translationP = translate(text).then((t) => { setTranslation(t); return t })
    let a: SentenceAnalysis | null = null
    try {
      const res = await axios.post('/api/sentences/analyze', { sentence: text })
      a = res.data
      setAnalysis(a)
    } catch (e) {
      setError(errorMessage(e, 'Could not analyze the sentence'))
      setAnalysis(null)
    } finally {
      setLoading(false)
    }
    if (!a) return
    const [s, t] = await Promise.all([sourceP, translationP])
    persist(a, t, s, null)
  }, [persist, refreshSaved])

  /** After an add or edit, re-read the dictionary so the tints update. */
  const refresh = async () => {
    if (!analysis) return
    try {
      const res = await axios.post('/api/sentences/analyze', { sentence: analysis.sentence })
      setAnalysis(res.data)
      persist(res.data, translation, source, userTranslation)
    } catch (e) {
      setError(errorMessage(e, 'Could not refresh the analysis'))
    }
  }

  const run = () => {
    const text = sentence.trim()
    if (!text) { setError('Enter a sentence first'); return }
    setGloss(null)
    analyze(text)
  }

  /** Reopen a saved analysis: one database read, no lookups. */
  const openSaved = async (item: SavedAnalysis) => {
    setActiveId(item.id)
    setGloss(null); setError('')
    setLoading(true)
    try {
      const res = await axios.get(`/api/sentence-analyses/${item.id}`)
      const doc = res.data
      setSentence(doc.sentence)
      setAnalysis({ sentence: doc.sentence, words: doc.words || [], dictionary: doc.dictionary || {}, similar: doc.similar || {}, phrases: doc.phrases || {} })
      setTranslation(doc.translation?.text !== undefined ? { state: 'done', text: doc.translation.text, engine: doc.translation.engine || 'model' } : { state: 'idle' })
      setSource(doc.source ? { state: 'found', match: doc.source } : { state: 'none' })
      setUserTranslation(doc.user_translation || null)
      setFromSaved(true)
    } catch (e) {
      setError(errorMessage(e, 'Could not open that saved sentence'))
    } finally {
      setLoading(false)
    }
  }

  const removeSaved = async (id: string) => {
    try {
      await axios.delete(`/api/sentence-analyses/${id}`)
      if (activeId === id) setActiveId(null)
      refreshSaved()
    } catch (e) {
      setSavedError(errorMessage(e, 'Could not delete that saved sentence'))
    }
  }

  /** The user confirmed or typed a translation: it replaces the model's and is saved. */
  const onPairSaved = (english: string) => {
    if (!analysis || !savePair) return
    const ut: UserTranslation = {
      english,
      source: savePair.origin.source === 'wol.jw.org' && english.trim() === savePair.english.trim() ? 'wol.jw.org' : 'user',
      citation: savePair.origin.citation,
      link: savePair.origin.link,
      title: savePair.origin.title,
      saved_at: new Date().toISOString(),
    }
    setUserTranslation(ut)
    persist(analysis, translation, source, ut)
  }

  const openEditor = (word: string, prefill?: EntryPrefill | null) => {
    const entry = analysis?.dictionary[word.toLowerCase()]
    setEditor({ word, entry, prefill: prefill ?? null })
  }

  const rows = analysis ? distinctWords(analysis.words) : []
  const phrases = analysis ? Object.values(analysis.phrases) : []
  const known = rows.filter((r) => analysis!.dictionary[r.key]).length
  const sourceEnglish = source.state === 'found' && source.match.english ? source.match.english.text : null
  /** The English to use as evidence for word suggestions. */
  const bestEnglish = userTranslation?.english || sourceEnglish || (translation.state === 'done' ? translation.text : null)
  const bestEnglishSource: 'article' | 'model' = userTranslation || sourceEnglish ? 'article' : 'model'

  return (
    <Container size="xl" py="md">
      <Title order={2} mb={4}>Sentence Analysis</Title>
      <Text c="dimmed" size="sm" mb="lg">
        Paste a Chuukese sentence to see what the dictionary knows about each word, its English from wol.jw.org,
        and real examples. Add or correct entries without leaving the page.
      </Text>

      <Group align="flex-start" gap="lg" wrap="nowrap" className={styles.layout}>
        <HistorySidebar
          saved={saved}
          activeId={activeId}
          loading={savedLoading}
          error={savedError}
          onSelect={openSaved}
          onDelete={removeSaved}
        />

        <Box style={{ flex: 1, minWidth: 0 }}>
          <Paper p="md" withBorder mb="md">
            <Textarea
              label="Chuukese sentence"
              placeholder="e.g. Jiowa a tongei aramas meinisin."
              value={sentence}
              onChange={(e) => setSentence(e.currentTarget.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) run() }}
              minRows={2}
              autosize
              styles={{ input: { fontSize: '1.05rem' } }}
            />
            <Group justify="space-between" mt="sm" wrap="wrap">
              <GlossLegend />
              <Button onClick={run} loading={loading} leftSection={<IconLanguage size={16} />} disabled={!sentence.trim()}>
                Analyze
              </Button>
            </Group>
          </Paper>

          {error && <Alert icon={<IconAlertCircle size={16} />} color="red" mb="md">{error}</Alert>}
          {loading && !analysis && (
            <Group justify="center" py="xl"><Loader /><Text c="dimmed">Looking up every word…</Text></Group>
          )}

          {analysis && (
            <Stack gap="md">
              {fromSaved && (
                <Alert icon={<IconHistory size={16} />} color="violet" variant="light" py={6}>
                  <Text size="xs">Reopened from your saved sentences — no new lookups were made.</Text>
                </Alert>
              )}

              <Card withBorder padding="md" className={styles.result}>
                <Text className={`${styles.sentence} ${styles.sentenceLarge}`}>
                  <GlossedWords
                    text={analysis.sentence}
                    dictionary={analysis.dictionary}
                    similar={analysis.similar}
                    phrases={analysis.phrases}
                    onGloss={setGloss}
                    onWordClick={(w) => openEditor(w)}
                  />
                </Text>
                <Group justify="flex-end" mt={4}><AddToTalk chk={analysis.sentence} en={bestEnglish || ''} source="sentence analysis" variant="button" size="xs" /></Group>

                {/* The translation the user added: replaces the model's */}
                {userTranslation && (
                  <Box className={styles.english} style={{ borderLeftColor: '#40c057' }}>
                    <Text className={styles.englishText} fw={600}>{userTranslation.english}</Text>
                    <Group gap="xs" mt={4} wrap="wrap">
                      <Badge variant="light" color="green" size="xs" leftSection={<IconUserCheck size={10} />}>
                        added by you{userTranslation.saved_at ? ` · ${formatWhen(userTranslation.saved_at)}` : ''}
                      </Badge>
                      <Badge variant="outline" color={userTranslation.source === 'wol.jw.org' ? 'teal' : 'gray'} size="xs">
                        {userTranslation.source === 'wol.jw.org' ? 'exact text from wol.jw.org' : 'typed in'}
                      </Badge>
                      {userTranslation.citation && <Text size="xs" c="dimmed" className={styles.citation}>{userTranslation.citation}</Text>}
                      {userTranslation.link && (
                        <Anchor href={userTranslation.link} target="_blank" rel="noopener noreferrer" size="xs">
                          <Group gap={4} wrap="nowrap"><IconExternalLink size={12} />Open source</Group>
                        </Anchor>
                      )}
                      <Text size="xs" c="dimmed">Saved as a confirmed training pair.</Text>
                    </Group>
                  </Box>
                )}

                {/* The real English, when the sentence is on wol.jw.org */}
                {!userTranslation && (
                  <Box className={styles.english} style={{ borderLeftColor: '#20c997' }}>
                    {source.state === 'loading' && (
                      <Group gap={6}><Loader size={12} /><Text size="xs" c="dimmed">Looking for this sentence on wol.jw.org…</Text></Group>
                    )}
                    {source.state === 'error' && <Text size="xs" c="red">{source.message}</Text>}
                    {(source.state === 'none' || source.state === 'idle') && (
                      <Group gap="xs" wrap="wrap">
                        <Text size="xs" c="dimmed">Not found on wol.jw.org, so there is no source English to check against.</Text>
                        <Button size="compact-xs" variant="subtle" leftSection={<IconDeviceFloppy size={12} />} onClick={() => setSavePair({ english: '', origin: { source: 'user' } })}>
                          Enter the translation
                        </Button>
                      </Group>
                    )}
                    {source.state === 'found' && (
                      <>
                        {source.match.english ? (
                          <Text className={styles.englishText} fw={600}>{source.match.english.text}</Text>
                        ) : (
                          <Text size="sm" c="dimmed" fs="italic">Found on wol.jw.org, but its English edition could not be lined up.</Text>
                        )}
                        {!source.match.exact && (
                          <Text size="xs" c="dimmed" mt={2}>Closest text on WOL (partial match): “{source.match.chuukese}”</Text>
                        )}
                        <Group gap="xs" mt={4} wrap="wrap">
                          <Badge variant="light" color="teal" size="xs" leftSection={<IconBooks size={10} />}>
                            {source.match.exact ? 'exact source on wol.jw.org' : 'partial match on wol.jw.org'}
                          </Badge>
                          {source.match.english?.scope === 'paragraph' && (
                            <Text size="xs" c="dimmed" fs="italic">whole paragraph — sentence could not be lined up</Text>
                          )}
                          {(source.match.english?.citation || source.match.citation) && (
                            <Text size="xs" c="dimmed" className={styles.citation}>{source.match.english?.citation || source.match.citation}</Text>
                          )}
                          {source.match.title && <Text size="xs" c="dimmed">{source.match.title}</Text>}
                          {source.match.english?.link && (
                            <Anchor href={source.match.english.link} target="_blank" rel="noopener noreferrer" size="xs">
                              <Group gap={4} wrap="nowrap"><IconExternalLink size={12} />Open English</Group>
                            </Anchor>
                          )}
                          {source.match.link && (
                            <Anchor href={source.match.link} target="_blank" rel="noopener noreferrer" size="xs">
                              <Group gap={4} wrap="nowrap"><IconExternalLink size={12} />Open on WOL</Group>
                            </Anchor>
                          )}
                          <Button
                            size="compact-xs"
                            variant="light"
                            color="teal"
                            leftSection={<IconDeviceFloppy size={12} />}
                            onClick={() => setSavePair({
                              english: source.match.english?.text || '',
                              origin: { source: 'wol.jw.org', citation: source.match.english?.citation || source.match.citation, link: source.match.english?.link || source.match.link, title: source.match.title },
                            })}
                          >
                            {source.match.english ? 'Save as the translation' : 'Enter the translation'}
                          </Button>
                        </Group>
                      </>
                    )}
                  </Box>
                )}

                {/* The model's guess: only while there is no better English */}
                {!userTranslation && translation.state !== 'idle' && (
                  <Box className={styles.english} style={{ opacity: sourceEnglish ? 0.75 : 1 }}>
                    {translation.state === 'loading' && (
                      <Group gap={6}><Loader size={12} /><Text size="xs" c="dimmed">Translating with the model…</Text></Group>
                    )}
                    {translation.state === 'done' && (
                      <>
                        <Text className={styles.englishText}>{translation.text || <Text component="span" c="dimmed" fs="italic">The model returned nothing.</Text>}</Text>
                        <Group gap="xs" mt={4}>
                          <Badge variant="light" color="grape" size="xs" leftSection={<IconRobot size={10} />}>{translation.engine}</Badge>
                          <Text size="xs" c="dimmed">
                            {sourceEnglish
                              ? 'Model translation, for comparison only — the source text above is the real English.'
                              : 'Model translation — a guess. Check it against the words below and the WOL examples.'}
                          </Text>
                        </Group>
                      </>
                    )}
                    {translation.state === 'unavailable' && (
                      <Text size="xs" c="dimmed">The {translation.engine} model is not loaded on this server, so there is no sentence translation.</Text>
                    )}
                    {translation.state === 'error' && <Text size="xs" c="red">{translation.message}</Text>}
                  </Box>
                )}

                <Group gap="xs" mt="sm" wrap="wrap">
                  <Badge variant="light" color="blue" size="sm">{known} of {rows.length} words in dictionary</Badge>
                  {phrases.length > 0 && <Badge variant="light" color="violet" size="sm">{phrases.length} dictionary phrase{phrases.length === 1 ? '' : 's'}</Badge>}
                  <Text size="xs" c="dimmed">Hover a word for its gloss; click it to edit or add.</Text>
                </Group>
              </Card>

              {/* Phrases held as one headword */}
              {phrases.length > 0 && (
                <Paper withBorder p="md" radius="md">
                  <Text size="xs" c="dimmed" tt="uppercase" fw={700} mb="xs">Dictionary phrases in this sentence</Text>
                  <Stack gap={4}>
                    {phrases.map((p) => (
                      <Group key={p.text} gap="xs" wrap="wrap">
                        <Text fw={700} className={styles.headword} c="violet.8">{p.text}</Text>
                        <Text size="sm">{p.english || <Text component="span" c="dimmed" fs="italic">no translation yet</Text>}</Text>
                        {p.grammar && <Badge size="xs" variant="outline">{p.grammar}</Badge>}
                        {p.definition && <Text size="xs" c="dimmed">{p.definition}</Text>}
                      </Group>
                    ))}
                  </Stack>
                </Paper>
              )}

              {/* Word table */}
              <Paper withBorder radius="md" p={0}>
                <Table verticalSpacing="xs" highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Word</Table.Th>
                      <Table.Th>Status</Table.Th>
                      <Table.Th>English</Table.Th>
                      <Table.Th>Grammar</Table.Th>
                      <Table.Th style={{ width: 130 }} />
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {rows.map((r) => {
                      const entry = analysis.dictionary[r.key]
                      const near = analysis.similar[r.key]
                      const needsHelp = !entry || entry.status === 'untranslated'
                      return (
                        <Table.Tr key={r.key}>
                          <Table.Td>
                            <Text fw={700} className={styles.headword} c="blue.8">{r.word}</Text>
                            {entry?.variant_of && <Text size="xs" c="dimmed">dictionary: {entry.variant_of}</Text>}
                          </Table.Td>
                          <Table.Td><StatusBadge entry={entry} near={near} /></Table.Td>
                          <Table.Td>
                            {entry?.english
                              ? <Text size="sm">{entry.english}</Text>
                              : near && near.length > 0
                                ? <Text size="xs" c="dimmed">similar: {near.slice(0, 4).map((s) => s.english ? `${s.word} (${s.english})` : s.word).join(', ')}{near.length > 4 ? '…' : ''}</Text>
                                : <Text size="xs" c="dimmed">—</Text>}
                            {entry?.definition && <Text size="xs" c="dimmed" lineClamp={1}>{entry.definition}</Text>}
                          </Table.Td>
                          <Table.Td>
                            {entry?.grammar && <Badge size="xs" variant="outline">{entry.grammar}</Badge>}
                            {entry?.grammar_modifier && <Text size="xs" c="dimmed">{entry.grammar_modifier}</Text>}
                          </Table.Td>
                          <Table.Td>
                            <Group gap={4} wrap="nowrap" justify="flex-end">
                              <Tooltip label={entry ? 'Edit entry' : 'Add to dictionary'}>
                                <ActionIcon variant="subtle" color="blue" onClick={() => openEditor(r.word)} aria-label={entry ? `Edit ${r.word}` : `Add ${r.word}`}>
                                  {entry ? <IconPencil size={16} /> : <IconPlus size={16} />}
                                </ActionIcon>
                              </Tooltip>
                              {needsHelp && (
                                <Tooltip label="Suggest an entry from accents, WOL usage and the model">
                                  <ActionIcon variant="subtle" color="violet" onClick={() => setSuggestWord(r.word)} aria-label={`Suggest entry for ${r.word}`}>
                                    <IconSparkles size={16} />
                                  </ActionIcon>
                                </Tooltip>
                              )}
                              <Tooltip label="Examples on wol.jw.org, with English">
                                <ActionIcon variant="subtle" color="teal" onClick={() => setExamplesWord(r.word)} aria-label={`Examples of ${r.word}`}>
                                  <IconQuote size={16} />
                                </ActionIcon>
                              </Tooltip>
                            </Group>
                          </Table.Td>
                        </Table.Tr>
                      )
                    })}
                  </Table.Tbody>
                </Table>
              </Paper>
            </Stack>
          )}
        </Box>
      </Group>

      <Divider my="xl" />
      <Text size="xs" c="dimmed" ta="center">
        Word tints come from our Chuukese dictionary. Source text and examples are fetched live from wol.jw.org; analyses are saved so you can reopen them here.
      </Text>

      {gloss && <GlossCard gloss={gloss} />}

      <EntryEditor
        opened={!!editor}
        onClose={() => setEditor(null)}
        word={editor?.word || ''}
        entry={editor?.entry}
        prefill={editor?.prefill}
        example={analysis?.sentence}
        onSaved={refresh}
      />
      <SuggestModal
        word={suggestWord}
        sentence={analysis?.sentence || sentence}
        english={bestEnglish}
        englishSource={bestEnglishSource}
        onClose={() => setSuggestWord(null)}
        onUse={(prefill) => { const w = suggestWord!; setSuggestWord(null); openEditor(w, prefill) }}
      />
      <WolExamplesDrawer word={examplesWord} onClose={() => setExamplesWord(null)} />
      <SavePairModal
        opened={!!savePair}
        onClose={() => setSavePair(null)}
        chuukese={analysis?.sentence || sentence}
        english={savePair?.english || ''}
        origin={savePair?.origin || { source: 'user' }}
        onSaved={onPairSaved}
      />
    </Container>
  )
}

export default Sentences
