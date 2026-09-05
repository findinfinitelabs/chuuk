import { useState, useEffect, useCallback } from 'react'
import {
  Container, Title, Text, TextInput, Button, Stack, Card, Group, Badge,
  Loader, Alert, Paper, Tabs, Select, Anchor, ScrollArea, Divider,
  Box, NavLink as MantineNavLink, ActionIcon,
} from '@mantine/core'
import {
  IconSearch, IconAlertCircle, IconExternalLink, IconBooks,
  IconUser, IconQuote, IconHistory, IconTrash, IconDatabase,
} from '@tabler/icons-react'
import axios from 'axios'
import styles from './WolSearch.module.css'

// ── Types ─────────────────────────────────────────────────────────────────────

/** A run of text within a sentence; `match` marks the searched term. */
interface Segment {
  text: string
  match: boolean
}

interface Reference {
  raw: string | null
  pub: string | null
  year: number | null
  month: number | null
  day: number | null
  pages: string | null
  title: string | null
}

interface Subject {
  subject: string
  marker: string
  tense: string | null
  kind: 'pronoun' | 'possessive' | 'name'
  standalone?: string
}

interface WolResult {
  text: string
  segments: Segment[]
  title: string | null
  link: string | null
  reference: Reference
  citation: string | null
  subject?: Subject | null
}

interface SubjectCount {
  subject: string
  count: number
}

/** A dictionary entry for one Chuukese word, keyed by its lowercase form. */
interface DictEntry {
  english: string
  grammar: string
  grammar_modifier: string | null
  definition: string
  status: 'translated' | 'untranslated'
}

type Dictionary = Record<string, DictEntry>

/** A dictionary word that looks related to one we don't hold. */
interface SimilarWord {
  word: string
  english: string
}

/** Related words for each unknown word, already in alphabetical order. */
type SimilarMap = Record<string, SimilarWord[]>

/** What the floating gloss is currently describing: either a dictionary entry
 *  or, for an unknown word, the related entries we do hold. */
interface Gloss {
  word: string
  entry?: DictEntry
  similar?: SimilarWord[]
  x: number
  y: number
}

interface WolResponse {
  query: string
  results: WolResult[]
  totalFound: number
  pagesFetched: number
  /** Most frequent first. A list, not a map, so the order survives JSON. */
  subjectCounts?: SubjectCount[]
  /** Every word in the results that our Cosmos dictionary knows about. */
  dictionary?: Dictionary
  /** For words we don't hold: related entries we do, alphabetically. */
  similar?: SimilarMap
}

/** One row in the saved-search sidebar. */
interface SavedSearch {
  id: string
  query: string
  mode: 'sentences' | 'verbs'
  sort: string
  pages: number
  result_count: number
  dictionary_count: number
  similar_count: number
  created_at?: string
  updated_at?: string
  created_by?: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const MONTHS = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "Apr 2001" / "2017" / "undated" */
function formatDate(ref: Reference): string {
  if (!ref.year) return 'undated'
  if (ref.month) return `${MONTHS[ref.month]} ${ref.year}`
  return String(ref.year)
}

/** Pull the server's error message off a failed request, if there is one. */
function errorMessage(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) return e.response?.data?.error || fallback
  return fallback
}

const SUBJECT_COLOR: Record<Subject['kind'], string> = {
  pronoun: 'blue',
  possessive: 'grape',
  name: 'teal',
}

/** Splits on non-letters, keeping the separators so the sentence rebuilds exactly.
 *  Mirrors the backend's `[^\W\d_]+`, so both sides agree on what a word is. */
const TOKENS = /([^\p{L}]+)/u
const IS_WORD = /^\p{L}+$/u

/** Renders the sentence: every word tinted by its dictionary status, and the
 *  searched term marked on top of that. */
function Sentence({
  segments, dictionary, similar, onGloss,
}: {
  segments: Segment[]
  dictionary: Dictionary
  similar: SimilarMap
  onGloss: (g: Gloss | null) => void
}) {
  return (
    <Text className={styles.sentence}>
      {segments.map((seg, si) => {
        const body = seg.text.split(TOKENS).map((tok, ti) => {
          if (!tok) return null
          const key = `${si}-${ti}`
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
                  ? (e) =>
                      onGloss({
                        word: tok,
                        entry,
                        similar: near,
                        x: e.clientX,
                        y: e.clientY,
                      })
                  : undefined
              }
              onMouseLeave={hoverable ? () => onGloss(null) : undefined}
            >
              {tok}
            </span>
          )
        })
        return seg.match ? (
          <mark key={si} className={styles.hit}>{body}</mark>
        ) : (
          <span key={si}>{body}</span>
        )
      })}
    </Text>
  )
}

/** The floating gloss. One instance for the page, following the cursor. */
function GlossCard({ gloss }: { gloss: Gloss }) {
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
function Legend() {
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

/** Citation, date and source link shared by both tabs. */
function ResultMeta({ result }: { result: WolResult }) {
  const { reference: ref } = result
  return (
    <Group gap="xs" wrap="wrap" mt="xs">
      <Badge variant="light" color={ref.year ? 'blue' : 'gray'} size="sm">
        {formatDate(ref)}
      </Badge>
      {ref.pub && <Badge variant="outline" size="sm">{ref.pub}</Badge>}
      {ref.pages && <Text size="xs" c="dimmed">p. {ref.pages}</Text>}
      {result.citation && (
        <Text size="xs" c="dimmed" className={styles.citation}>{result.citation}</Text>
      )}
      {result.link && (
        <Anchor href={result.link} target="_blank" rel="noopener noreferrer" size="xs">
          <Group gap={4} wrap="nowrap">
            <IconExternalLink size={13} />
            Open on WOL
          </Group>
        </Anchor>
      )}
    </Group>
  )
}

/** Saved searches. Reopening one costs a single database read instead of a
 *  live round trip to WOL. */
function HistorySidebar({
  saved, activeId, loading, error, onSelect, onDelete,
}: {
  saved: SavedSearch[]
  activeId: string | null
  loading: boolean
  error: string
  onSelect: (s: SavedSearch) => void
  onDelete: (id: string) => void
}) {
  return (
    <Box style={{ width: 250, flexShrink: 0 }}>
      <Paper withBorder radius="md" p="sm" style={{ position: 'sticky', top: 16 }}>
        <Group gap={6} mb="sm">
          <IconHistory size={16} color="#7c55de" />
          <Text size="sm" fw={700} c="violet.8">Saved Searches</Text>
          {loading && <Loader size="xs" style={{ marginLeft: 'auto' }} />}
        </Group>
        <Divider mb="sm" />
        {error && <Text size="xs" c="red" mb="xs">{error}</Text>}
        <ScrollArea h={520} type="auto">
          {saved.length === 0 && !loading && (
            <Text size="xs" c="dimmed" ta="center" py="md">
              Searches you run are saved here automatically.
            </Text>
          )}
          {saved.map((item) => (
            <Box key={item.id} mb={4} style={{ position: 'relative' }}>
              <MantineNavLink
                label={
                  <Stack gap={2}>
                    <Text
                      size="xs"
                      fw={700}
                      lineClamp={2}
                      c={activeId === item.id ? 'violet.9' : undefined}
                    >
                      {item.query}
                    </Text>
                    <Group gap={4} mt={2}>
                      <Badge size="xs" variant="light" color={item.mode === 'verbs' ? 'teal' : 'violet'}>
                        {item.mode === 'verbs' ? 'verbs' : 'sentences'}
                      </Badge>
                      <Badge size="xs" variant="light" color="blue">{item.result_count}</Badge>
                      {item.dictionary_count > 0 && (
                        <Badge size="xs" variant="dot" color="green">{item.dictionary_count}</Badge>
                      )}
                    </Group>
                    {item.updated_at && (
                      <Text size="xs" c="dimmed">
                        {new Date(item.updated_at).toLocaleDateString()}
                      </Text>
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
                aria-label={`Delete saved search ${item.query}`}
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

function WolSearch() {
  const [tab, setTab] = useState<string | null>('sentences')

  // Sentence search
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<string | null>('newest')
  const [pages, setPages] = useState<string | null>('2')
  const [data, setData] = useState<WolResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Verb examples
  const [verb, setVerb] = useState('')
  const [verbData, setVerbData] = useState<WolResponse | null>(null)
  const [verbLoading, setVerbLoading] = useState(false)
  const [verbError, setVerbError] = useState('')
  const [subjectFilter, setSubjectFilter] = useState<string | null>(null)

  // Shared by both tabs: the word gloss that follows the cursor.
  const [gloss, setGloss] = useState<Gloss | null>(null)

  // Saved-search sidebar
  const [saved, setSaved] = useState<SavedSearch[]>([])
  const [savedLoading, setSavedLoading] = useState(false)
  const [savedError, setSavedError] = useState('')
  const [activeId, setActiveId] = useState<string | null>(null)
  const [fromSaved, setFromSaved] = useState(false)

  const refreshSaved = useCallback(async () => {
    setSavedLoading(true)
    try {
      const res = await axios.get('/api/wol/searches')
      setSaved(Array.isArray(res.data) ? res.data : [])
      setSavedError('')
    } catch (e) {
      setSavedError(errorMessage(e, 'Could not load saved searches'))
    } finally {
      setSavedLoading(false)
    }
  }, [])

  useEffect(() => { refreshSaved() }, [refreshSaved])

  /** Persist a completed search so it can be reopened without hitting WOL. */
  const persist = useCallback(async (mode: 'sentences' | 'verbs', payload: WolResponse, term: string) => {
    if (!payload.results?.length) return
    try {
      const res = await axios.post('/api/wol/searches', {
        query: term,
        mode,
        sort: mode === 'sentences' ? sort : 'newest',
        pages: Number(pages) || 2,
        results: payload.results,
        dictionary: payload.dictionary || {},
        similar: payload.similar || {},
        subjectCounts: payload.subjectCounts || [],
      })
      if (res.data?.id) setActiveId(res.data.id)
      refreshSaved()
    } catch {
      // Saving is a convenience; a failure must not disturb the results on screen.
    }
  }, [sort, pages, refreshSaved])

  /** Reopen a saved search from the database. */
  const openSaved = async (item: SavedSearch) => {
    setActiveId(item.id)
    setFromSaved(true)
    setGloss(null)
    const target = item.mode === 'verbs' ? 'verbs' : 'sentences'
    setTab(target)
    if (target === 'verbs') { setVerbLoading(true); setVerbError('') } else { setLoading(true); setError('') }
    try {
      const res = await axios.get(`/api/wol/searches/${item.id}`)
      if (target === 'verbs') {
        setVerb(item.query); setVerbData(res.data); setSubjectFilter(null)
      } else {
        setQuery(item.query); setData(res.data)
      }
    } catch (e) {
      const msg = errorMessage(e, 'Could not open that saved search')
      if (target === 'verbs') setVerbError(msg); else setError(msg)
    } finally {
      if (target === 'verbs') setVerbLoading(false); else setLoading(false)
    }
  }

  const removeSaved = async (id: string) => {
    try {
      await axios.delete(`/api/wol/searches/${id}`)
      if (activeId === id) setActiveId(null)
      refreshSaved()
    } catch (e) {
      setSavedError(errorMessage(e, 'Could not delete that saved search'))
    }
  }

  const runSearch = async () => {
    if (!query.trim()) return
    setLoading(true); setError(''); setData(null)
    try {
      const res = await axios.post('/api/wol/search', {
        query: query.trim(),
        sort,
        pages: Number(pages) || 2,
      })
      setData(res.data)
      setFromSaved(false)
      setActiveId(null)
      if (!res.data.results?.length) setError(`No results on wol.jw.org for "${query.trim()}".`)
      else persist('sentences', res.data, query.trim())
    } catch (e) {
      setError(errorMessage(e, 'Search failed. Please try again.'))
    } finally {
      setLoading(false)
    }
  }

  const runVerbSearch = async () => {
    if (!verb.trim()) return
    setVerbLoading(true); setVerbError(''); setVerbData(null); setSubjectFilter(null)
    try {
      const res = await axios.post('/api/wol/verb-examples', {
        verb: verb.trim(),
        pages: Number(pages) || 2,
      })
      setVerbData(res.data)
      setFromSaved(false)
      setActiveId(null)
      if (!res.data.results?.length) setVerbError(`No examples on wol.jw.org for "${verb.trim()}".`)
      else persist('verbs', res.data, verb.trim())
    } catch (e) {
      setVerbError(errorMessage(e, 'Search failed. Please try again.'))
    } finally {
      setVerbLoading(false)
    }
  }

  const visibleVerbResults = (verbData?.results || []).filter((r) => {
    if (!subjectFilter) return true
    if (subjectFilter === 'unknown') return !r.subject
    return r.subject?.subject === subjectFilter
  })

  return (
    <Container size="xl" py="md">
      <Title order={2} mb={4}>Watchtower Library Search</Title>
      <Text c="dimmed" size="sm" mb="lg">
        Search Chuukese publications on wol.jw.org for real sentences in context, newest first.
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
      <Tabs value={tab} onChange={setTab}>
        <Tabs.List mb="md">
          <Tabs.Tab value="sentences" leftSection={<IconQuote size={16} />}>
            Sentence Search
          </Tabs.Tab>
          <Tabs.Tab value="verbs" leftSection={<IconUser size={16} />}>
            Verb Examples
          </Tabs.Tab>
        </Tabs.List>

        {/* ── Sentence search ───────────────────────────────────────────── */}
        <Tabs.Panel value="sentences">
          <Paper p="md" withBorder mb="md">
            <Group align="flex-end" gap="sm" wrap="wrap">
              <TextInput
                label="Word or phrase"
                description="Paste a word or phrase from a publication"
                placeholder="e.g. chapur"
                value={query}
                onChange={(e) => setQuery(e.currentTarget.value)}
                onKeyDown={(e) => e.key === 'Enter' && runSearch()}
                style={{ flex: 1, minWidth: 260 }}
              />
              <Select
                label="Order"
                data={[
                  { value: 'newest', label: 'Newest first' },
                  { value: 'oldest', label: 'Oldest first' },
                  { value: 'relevance', label: 'Relevance' },
                ]}
                value={sort}
                onChange={setSort}
                w={150}
                allowDeselect={false}
              />
              <Select
                label="Depth"
                description="Pages to scan"
                data={['1', '2', '3', '4']}
                value={pages}
                onChange={setPages}
                w={110}
                allowDeselect={false}
              />
              <Button
                onClick={runSearch}
                loading={loading}
                leftSection={<IconSearch size={16} />}
                disabled={!query.trim()}
              >
                Search
              </Button>
            </Group>
            <Legend />
          </Paper>

          {error && (
            <Alert icon={<IconAlertCircle size={16} />} color="red" mb="md">{error}</Alert>
          )}
          {loading && (
            <Group justify="center" py="xl">
              <Loader />
              <Text c="dimmed">Searching wol.jw.org…</Text>
            </Group>
          )}

          {data && data.results.length > 0 && (
            <>
              {fromSaved && (
                <Alert icon={<IconDatabase size={16} />} color="violet" variant="light" mb="sm" py={6}>
                  <Text size="xs">Reopened from your saved searches — no request to wol.jw.org.</Text>
                </Alert>
              )}
              <Text size="sm" c="dimmed" mb="sm">
                {data.totalFound} sentence{data.totalFound === 1 ? '' : 's'} found
                {data.pagesFetched > 0 && ` across ${data.pagesFetched} page${data.pagesFetched === 1 ? '' : 's'}`}
                {data.results.length < data.totalFound && ` — showing ${data.results.length}`}
              </Text>
              <Stack gap="sm">
                {data.results.map((r, i) => (
                  <Card key={i} withBorder padding="md" className={styles.result}>
                    {r.title && (
                      <Text fw={600} size="sm" mb={6} className={styles.title}>{r.title}</Text>
                    )}
                    <Sentence
                      segments={r.segments}
                      dictionary={data?.dictionary || {}}
                      similar={data?.similar || {}}
                      onGloss={setGloss}
                    />
                    <ResultMeta result={r} />
                  </Card>
                ))}
              </Stack>
            </>
          )}
        </Tabs.Panel>

        {/* ── Verb examples ─────────────────────────────────────────────── */}
        <Tabs.Panel value="verbs">
          <Paper p="md" withBorder mb="md">
            <Group align="flex-end" gap="sm" wrap="wrap">
              <TextInput
                label="Verb"
                description="Find real uses of a verb and who is doing it"
                placeholder="e.g. tongei"
                value={verb}
                onChange={(e) => setVerb(e.currentTarget.value)}
                onKeyDown={(e) => e.key === 'Enter' && runVerbSearch()}
                style={{ flex: 1, minWidth: 260 }}
              />
              <Button
                onClick={runVerbSearch}
                loading={verbLoading}
                leftSection={<IconSearch size={16} />}
                disabled={!verb.trim()}
              >
                Find examples
              </Button>
            </Group>
            <Text size="xs" c="dimmed" mt="sm">
              Chuukese marks the subject just before the verb, so the subject and often the
              tense can be read straight off each example. A possessive before the verb
              (<em>ach tongei</em> — “our love”) is labelled as such rather than as a subject.
            </Text>
            <Legend />
          </Paper>

          {verbError && (
            <Alert icon={<IconAlertCircle size={16} />} color="red" mb="md">{verbError}</Alert>
          )}
          {verbLoading && (
            <Group justify="center" py="xl">
              <Loader />
              <Text c="dimmed">Searching wol.jw.org…</Text>
            </Group>
          )}

          {verbData && verbData.results.length > 0 && (
            <>
              {fromSaved && (
                <Alert icon={<IconDatabase size={16} />} color="violet" variant="light" mb="sm" py={6}>
                  <Text size="xs">Reopened from your saved searches — no request to wol.jw.org.</Text>
                </Alert>
              )}
              {verbData.subjectCounts && verbData.subjectCounts.length > 0 && (
                <Paper p="sm" withBorder mb="md">
                  <Text size="xs" fw={600} c="dimmed" mb={8}>
                    SUBJECTS FOUND — click to filter
                  </Text>
                  <ScrollArea>
                    <Group gap={6} wrap="wrap">
                      <Badge
                        variant={subjectFilter === null ? 'filled' : 'light'}
                        color="gray"
                        style={{ cursor: 'pointer' }}
                        onClick={() => setSubjectFilter(null)}
                      >
                        all ({verbData.results.length})
                      </Badge>
                      {verbData.subjectCounts.map(({ subject, count }) => (
                        <Badge
                          key={subject}
                          variant={subjectFilter === subject ? 'filled' : 'light'}
                          color={subject === 'unknown' ? 'gray' : 'blue'}
                          style={{ cursor: 'pointer' }}
                          onClick={() => setSubjectFilter(subjectFilter === subject ? null : subject)}
                        >
                          {subject} ({count})
                        </Badge>
                      ))}
                    </Group>
                  </ScrollArea>
                </Paper>
              )}

              <Stack gap="sm">
                {visibleVerbResults.map((r, i) => (
                  <Card key={i} withBorder padding="md" className={styles.result}>
                    <Group gap="xs" mb={8} wrap="wrap">
                      {r.subject ? (
                        <>
                          <Badge color={SUBJECT_COLOR[r.subject.kind]} variant="filled" size="sm">
                            {r.subject.subject}
                          </Badge>
                          <Badge variant="outline" size="sm" color="gray">
                            {r.subject.marker}
                          </Badge>
                          {r.subject.tense && (
                            <Badge variant="light" size="sm" color="orange">
                              {r.subject.tense}
                            </Badge>
                          )}
                          {r.subject.standalone && (
                            <Text size="xs" c="dimmed">with “{r.subject.standalone}”</Text>
                          )}
                          <Text size="xs" c="dimmed">({r.subject.kind})</Text>
                        </>
                      ) : (
                        <Badge color="gray" variant="light" size="sm">subject not identified</Badge>
                      )}
                    </Group>
                    {r.title && (
                      <Text fw={600} size="sm" mb={6} className={styles.title}>{r.title}</Text>
                    )}
                    <Sentence
                      segments={r.segments}
                      dictionary={verbData?.dictionary || {}}
                      similar={verbData?.similar || {}}
                      onGloss={setGloss}
                    />
                    <ResultMeta result={r} />
                  </Card>
                ))}
              </Stack>

              {visibleVerbResults.length === 0 && (
                <Alert color="gray" icon={<IconBooks size={16} />}>
                  No examples with that subject. Clear the filter to see all.
                </Alert>
              )}
            </>
          )}
        </Tabs.Panel>
      </Tabs>

        </Box>
      </Group>

      <Divider my="xl" />
      <Text size="xs" c="dimmed" ta="center">
        Results are fetched live from wol.jw.org and saved so you can reopen them here.
        Word tints come from our Chuukese dictionary.
      </Text>

      {gloss && <GlossCard gloss={gloss} />}
    </Container>
  )
}

export default WolSearch
