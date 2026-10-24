/**
 * ReviewQueue — admin page for proposals produced by scripts/verify_verbs_wol.py.
 *
 * Each row compares a dictionary entry with how wol.jw.org actually renders the
 * word in English: the different renderings seen, how many sentences support
 * the current translation, and the evidence sentence pairs. Nothing changes in
 * the dictionary until a row is accepted here; the reviewer can edit the
 * proposed wording first. Mechanical grammar fixes (tier "auto") can be applied
 * in bulk.
 */
import { useCallback, useEffect, useState } from 'react'
import {
  Container, Title, Text, Group, Stack, Badge, Button, Paper, Tabs, Select, TextInput,
  Loader, Alert, Table, Collapse, Anchor, ActionIcon, Tooltip, Pagination, Divider,
} from '@mantine/core'
import {
  IconCheck, IconX, IconRefresh, IconChevronDown, IconChevronUp, IconExternalLink,
  IconAlertCircle, IconBolt, IconRotate, IconPlus,
} from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import axios from 'axios'

interface Pair {
  chk: string
  en: string
  form?: string | null
  link?: string | null
  english_link?: string | null
  citation?: string | null
  title?: string | null
}

interface Rendering {
  stem: string
  word: string
  count: number
  share: number
  lift: number
  examples: number[]
}

interface SenseSupport {
  sense: string
  count: number
  examples: number[]
}

interface Review {
  id: string
  entry_id: string
  headword: string
  kind: 'translation' | 'grammar'
  outcome: string
  tier: 'auto' | 'review' | null
  status: 'pending' | 'applied' | 'rejected' | 'info'
  current: Record<string, unknown>
  proposed: Record<string, unknown> | null
  evidence: {
    pair_count?: number
    support_share?: number
    senses?: SenseSupport[]
    renderings?: Rendering[]
    forms?: string[]
    suggestions?: string[]
    pairs?: Pair[]
    notes?: string[]
  }
  decided_by?: string
  decided_at?: string
  applied_changes?: Record<string, unknown>
  updated_at?: string
}

interface SummaryRow { kind: string; outcome: string; status: string; count: number }
interface Summary {
  counts: SummaryRow[]
  last_run: { id: string; started_at?: string; finished_at?: string; status: string; verbs_checked?: number } | null
}

const OUTCOME_LABEL: Record<string, { label: string; color: string }> = {
  needs_review: { label: 'Translation differs', color: 'red' },
  add_senses: { label: 'More senses on WOL', color: 'orange' },
  confirmed: { label: 'Confirmed by WOL', color: 'teal' },
  insufficient: { label: 'Too few sentences', color: 'gray' },
  no_evidence: { label: 'Not found on WOL', color: 'gray' },
  normalize: { label: 'Grammar fix', color: 'violet' },
  merge_conflict: { label: 'Merged copies disagree', color: 'orange' },
}

/** The Chuukese sentence with the matched form of the verb emphasised. */
function Highlighted({ text, form }: { text: string; form?: string | null }) {
  if (!form) return <>{text}</>
  const idx = text.toLowerCase().indexOf(form.toLowerCase())
  if (idx < 0) return <>{text}</>
  return (
    <>
      {text.slice(0, idx)}
      <mark style={{ background: '#fff3bf', fontWeight: 700 }}>{text.slice(idx, idx + form.length)}</mark>
      {text.slice(idx + form.length)}
    </>
  )
}

function ReviewCard({ review, onDecide }: { review: Review; onDecide: (r: Review, action: 'accept' | 'reject' | 'reopen', proposed?: Record<string, unknown>) => Promise<void> }) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [english, setEnglish] = useState<string>(String(review.proposed?.english_translation ?? ''))
  const [showPairs, setShowPairs] = useState<number[] | null>(null)
  const ev = review.evidence || {}
  const pairs = ev.pairs || []
  const meta = OUTCOME_LABEL[review.outcome] || { label: review.outcome, color: 'gray' }
  const isTranslation = review.kind === 'translation'
  const pending = review.status === 'pending'

  const decide = async (action: 'accept' | 'reject' | 'reopen') => {
    setBusy(true)
    try {
      const proposed = action === 'accept' && isTranslation && review.proposed && 'english_translation' in review.proposed
        ? { ...review.proposed, english_translation: english.trim() }
        : undefined
      await onDecide(review, action, proposed)
    } finally {
      setBusy(false)
    }
  }

  const visiblePairs = showPairs ? showPairs.map((i) => pairs[i]).filter(Boolean) : pairs

  return (
    <Paper withBorder p="md" radius="md">
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
          <Group gap="xs">
            <Text fw={700} size="lg" style={{ fontFamily: 'Georgia, serif' }}>{review.headword}</Text>
            <Badge color={meta.color} variant="light">{meta.label}</Badge>
            {review.tier === 'auto' && <Badge color="violet" variant="outline" leftSection={<IconBolt size={10} />}>auto</Badge>}
            {review.status !== 'pending' && <Badge color={review.status === 'applied' ? 'teal' : review.status === 'rejected' ? 'red' : 'gray'}>{review.status}</Badge>}
            {typeof ev.pair_count === 'number' && isTranslation && (
              <Badge variant="light" color="blue">{ev.pair_count} sentence pair{ev.pair_count === 1 ? '' : 's'}</Badge>
            )}
            {ev.forms && ev.forms.length > 0 && (
              <Text size="xs" c="dimmed">forms seen: {ev.forms.join(', ')}</Text>
            )}
          </Group>

          {isTranslation ? (
            <Group gap="lg" align="flex-start">
              <Stack gap={2} style={{ minWidth: 220 }}>
                <Text size="xs" c="dimmed" tt="uppercase">Dictionary</Text>
                <Text size="sm">{String(review.current.english_translation || '—')}</Text>
                <Text size="xs" c="dimmed">{String(review.current.grammar || '')}{review.current.definition ? ` · ${review.current.definition}` : ''}</Text>
                {typeof ev.support_share === 'number' && ev.pair_count ? (
                  <Text size="xs" c={ev.support_share >= 0.4 ? 'teal' : 'red'}>
                    current wording appears in {Math.round(ev.support_share * 100)}% of sentences
                  </Text>
                ) : null}
              </Stack>
              {review.proposed && 'english_translation' in review.proposed && (
                <Stack gap={2} style={{ flex: 1, minWidth: 240 }}>
                  <Text size="xs" c="dimmed" tt="uppercase">New wording (edit before accepting)</Text>
                  <TextInput value={english} onChange={(e) => setEnglish(e.currentTarget.value)} disabled={!pending} size="sm" />
                  {review.outcome === 'needs_review' && (
                    <Text size="xs" c="dimmed">
                      {ev.suggestions && ev.suggestions.length > 0
                        ? 'WOL does not use the dictionary wording here. Click a rendering below to add it, or type your own.'
                        : 'WOL does not use the dictionary wording, and no single English word recurs. Read the sentences below and decide.'}
                    </Text>
                  )}
                </Stack>
              )}
              {review.proposed && review.proposed.wol_verified === true && (
                <Text size="sm" c="teal">Mark as verified by WOL usage.</Text>
              )}
            </Group>
          ) : (
            <Stack gap={2}>
              {(ev.notes || []).map((n, i) => <Text key={i} size="sm">• {n}</Text>)}
              <Text size="xs" c="dimmed">
                now: {String(review.current.grammar || '—')}{review.current.grammar_modifier ? ` / ${review.current.grammar_modifier}` : ''}
                {review.proposed ? ` → ${Object.entries(review.proposed).map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`).join('; ')}` : ''}
              </Text>
            </Stack>
          )}
        </Stack>

        <Group gap="xs" wrap="nowrap">
          {pending ? (
            <>
              <Tooltip label={isTranslation ? 'Apply this wording to the dictionary' : 'Apply this fix'}>
                <Button size="xs" color="teal" leftSection={<IconCheck size={14} />} loading={busy} onClick={() => decide('accept')}>Accept</Button>
              </Tooltip>
              <Button size="xs" color="red" variant="light" leftSection={<IconX size={14} />} loading={busy} onClick={() => decide('reject')}>Reject</Button>
            </>
          ) : review.status !== 'info' ? (
            <Button size="xs" variant="subtle" leftSection={<IconRotate size={14} />} loading={busy} onClick={() => decide('reopen')}>Reopen</Button>
          ) : null}
          {isTranslation && pairs.length > 0 && (
            <ActionIcon variant="subtle" onClick={() => setOpen((o) => !o)} aria-label="Toggle evidence">
              {open ? <IconChevronUp size={16} /> : <IconChevronDown size={16} />}
            </ActionIcon>
          )}
        </Group>
      </Group>

      {isTranslation && (ev.renderings?.length || ev.senses?.length) ? (
        <Group gap="xl" mt="sm" align="flex-start">
          {ev.renderings && ev.renderings.length > 0 && (
            <Stack gap={2}>
              <Text size="xs" c="dimmed" tt="uppercase">How WOL renders it</Text>
              <Group gap={6}>
                {ev.renderings.map((r) => (
                  <Group key={r.stem} gap={2} wrap="nowrap">
                    <Tooltip label={`in ${r.count} of ${ev.pair_count} sentences · ${r.lift}× more than usual · click to show those sentences`}>
                      <Badge
                        variant={showPairs && showPairs === r.examples ? 'filled' : 'light'}
                        color={ev.suggestions?.includes(r.word) ? 'blue' : 'gray'}
                        style={{ cursor: 'pointer' }}
                        onClick={() => { setShowPairs(showPairs === r.examples ? null : r.examples); setOpen(true) }}
                      >
                        {r.word} · {r.count}
                      </Badge>
                    </Tooltip>
                    {pending && review.proposed && 'english_translation' in review.proposed && (
                      <Tooltip label={`Add “${r.word}” to the new wording`}>
                        <ActionIcon
                          size="xs"
                          variant="subtle"
                          color="blue"
                          aria-label={`Add ${r.word}`}
                          onClick={() => setEnglish((cur) => {
                            const parts = cur.split(',').map((x) => x.trim()).filter(Boolean)
                            return parts.includes(r.word) ? cur : [...parts, r.word].join(', ')
                          })}
                        >
                          <IconPlus size={12} />
                        </ActionIcon>
                      </Tooltip>
                    )}
                  </Group>
                ))}
              </Group>
            </Stack>
          )}
          {ev.senses && ev.senses.length > 0 && (
            <Stack gap={2}>
              <Text size="xs" c="dimmed" tt="uppercase">Dictionary senses in evidence</Text>
              <Group gap={6}>
                {ev.senses.map((s) => (
                  <Badge key={s.sense} variant="light" color={s.count > 0 ? 'teal' : 'gray'}>{s.sense} · {s.count}</Badge>
                ))}
              </Group>
            </Stack>
          )}
        </Group>
      ) : null}

      <Collapse in={open}>
        <Divider my="sm" />
        <Table withRowBorders={false} verticalSpacing={6} fz="sm">
          <Table.Tbody>
            {visiblePairs.map((p, i) => (
              <Table.Tr key={i}>
                <Table.Td style={{ width: '50%', verticalAlign: 'top', fontFamily: 'Georgia, serif' }}>
                  <Highlighted text={p.chk} form={p.form} />
                  {p.link && (
                    <Anchor href={p.link} target="_blank" rel="noopener noreferrer" size="xs" ml={6}>
                      <IconExternalLink size={11} /> {p.citation || p.title || 'WOL'}
                    </Anchor>
                  )}
                </Table.Td>
                <Table.Td style={{ verticalAlign: 'top', color: '#343a40' }}>{p.en}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        {showPairs && <Button size="xs" variant="subtle" onClick={() => setShowPairs(null)}>Show all sentences</Button>}
      </Collapse>
    </Paper>
  )
}

function ReviewQueue() {
  const [status, setStatus] = useState<string | null>('pending')
  const [kind, setKind] = useState<string | null>('translation')
  const [outcome, setOutcome] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [items, setItems] = useState<Review[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [summary, setSummary] = useState<Summary | null>(null)
  const perPage = 25

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await axios.get('/api/reviews', {
        params: { status: status || '', kind: kind || '', outcome: outcome || '', q, page, per_page: perPage },
      })
      setItems(res.data.items || [])
      setTotal(res.data.total || 0)
    } catch (e) {
      setError(axios.isAxiosError(e) ? e.response?.data?.error || 'Could not load reviews' : 'Could not load reviews')
    } finally {
      setLoading(false)
    }
  }, [status, kind, outcome, q, page])

  const loadSummary = useCallback(async () => {
    try {
      const res = await axios.get('/api/reviews/summary')
      setSummary(res.data)
    } catch {
      // summary is decoration
    }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => { loadSummary() }, [loadSummary])

  const count = (pred: (r: SummaryRow) => boolean) => (summary?.counts || []).filter(pred).reduce((n, r) => n + r.count, 0)
  const pendingAuto = count((r) => r.status === 'pending' && r.kind === 'grammar')
  const pendingConfirmed = count((r) => r.status === 'pending' && r.outcome === 'confirmed')

  const decide = async (r: Review, action: 'accept' | 'reject' | 'reopen', proposed?: Record<string, unknown>) => {
    try {
      const res = await axios.post(`/api/reviews/${r.id}/decide`, { action, proposed })
      notifications.show({
        title: action === 'accept' ? 'Applied' : action === 'reject' ? 'Rejected' : 'Reopened',
        message: `${r.headword}${res.data.applied ? ' · ' + Object.keys(res.data.applied).join(', ') : ''}`,
        color: action === 'accept' ? 'teal' : action === 'reject' ? 'red' : 'blue',
      })
      setItems((prev) => prev.filter((x) => x.id !== r.id))
      setTotal((t) => Math.max(0, t - 1))
      loadSummary()
    } catch (e) {
      notifications.show({ title: 'Error', message: axios.isAxiosError(e) ? e.response?.data?.error || 'Request failed' : 'Request failed', color: 'red' })
    }
  }

  const bulk = async (filter: Record<string, string>, label: string) => {
    if (!window.confirm(`Apply all pending ${label}? Each change is recorded in the entry's history.`)) return
    try {
      const res = await axios.post('/api/reviews/bulk', { action: 'accept', filter })
      notifications.show({ title: 'Applied', message: `${res.data.done} applied${res.data.failed?.length ? `, ${res.data.failed.length} failed` : ''}`, color: 'teal' })
      load(); loadSummary()
    } catch (e) {
      notifications.show({ title: 'Error', message: axios.isAxiosError(e) ? e.response?.data?.error || 'Request failed' : 'Request failed', color: 'red' })
    }
  }

  const outcomes = kind === 'grammar'
    ? [{ value: 'normalize', label: 'Grammar fix' }, { value: 'merge_conflict', label: 'Merged copies disagree' }]
    : [
        { value: 'needs_review', label: 'Translation differs' },
        { value: 'add_senses', label: 'More senses on WOL' },
        { value: 'confirmed', label: 'Confirmed by WOL' },
        { value: 'insufficient', label: 'Too few sentences' },
        { value: 'no_evidence', label: 'Not found on WOL' },
      ]

  return (
    <Container size="xl" py="md">
      <Group justify="space-between" align="flex-start" mb="xs">
        <div>
          <Title order={2}>Translation Review</Title>
          <Text c="dimmed" size="sm">
            Dictionary verbs checked against real usage on wol.jw.org. Accepting a row changes the dictionary; the previous values are kept in the entry's history.
          </Text>
        </div>
        <ActionIcon variant="subtle" onClick={() => { load(); loadSummary() }} aria-label="Refresh"><IconRefresh size={18} /></ActionIcon>
      </Group>

      {summary && (
        <Paper withBorder p="sm" radius="md" mb="md">
          <Group gap="lg" wrap="wrap">
            {summary.last_run && (
              <Text size="xs" c="dimmed">
                Last run {summary.last_run.id} · {summary.last_run.status}
                {summary.last_run.verbs_checked ? ` · ${summary.last_run.verbs_checked} verbs checked` : ''}
              </Text>
            )}
            <Badge color="red" variant="light">{count((r) => r.status === 'pending' && r.outcome === 'needs_review')} differ</Badge>
            <Badge color="orange" variant="light">{count((r) => r.status === 'pending' && r.outcome === 'add_senses')} more senses</Badge>
            <Badge color="teal" variant="light">{pendingConfirmed} confirmed</Badge>
            <Badge color="violet" variant="light">{pendingAuto} grammar fixes</Badge>
            <Badge color="gray" variant="light">{count((r) => r.status === 'info')} no usable evidence</Badge>
            <Badge color="teal">{count((r) => r.status === 'applied')} applied</Badge>
            <Group gap="xs" ml="auto">
              {pendingConfirmed > 0 && (
                <Button size="xs" variant="light" color="teal" onClick={() => bulk({ kind: 'translation', outcome: 'confirmed' }, 'confirmations (marks entries verified)')}>
                  Mark {pendingConfirmed} confirmed as verified
                </Button>
              )}
              {pendingAuto > 0 && (
                <Button size="xs" variant="light" color="violet" leftSection={<IconBolt size={14} />} onClick={() => bulk({ kind: 'grammar', tier: 'auto' }, 'grammar fixes')}>
                  Apply {pendingAuto} grammar fixes
                </Button>
              )}
            </Group>
          </Group>
        </Paper>
      )}

      <Tabs value={kind} onChange={(v) => { setKind(v); setOutcome(null); setPage(1) }} mb="sm">
        <Tabs.List>
          <Tabs.Tab value="translation">Translations</Tabs.Tab>
          <Tabs.Tab value="grammar">Grammar tags</Tabs.Tab>
        </Tabs.List>
      </Tabs>

      <Group gap="sm" mb="md" align="flex-end">
        <Select label="Status" data={[{ value: 'pending', label: 'Pending' }, { value: 'applied', label: 'Applied' }, { value: 'rejected', label: 'Rejected' }, { value: 'info', label: 'No usable evidence' }]}
          value={status} onChange={(v) => { setStatus(v); setPage(1) }} w={190} allowDeselect={false} />
        <Select label="Outcome" data={outcomes} value={outcome} onChange={(v) => { setOutcome(v); setPage(1) }} w={220} clearable placeholder="All" />
        <TextInput label="Search headword" value={q} onChange={(e) => { setQ(e.currentTarget.value); setPage(1) }} w={220} />
        <Text size="sm" c="dimmed" ml="auto">{total} row{total === 1 ? '' : 's'}</Text>
      </Group>

      {error && <Alert icon={<IconAlertCircle size={16} />} color="red" mb="md">{error}</Alert>}
      {loading && <Group justify="center" py="xl"><Loader /></Group>}

      <Stack gap="sm">
        {!loading && items.length === 0 && <Text c="dimmed" ta="center" py="xl">Nothing here.</Text>}
        {items.map((r) => <ReviewCard key={r.id} review={r} onDecide={decide} />)}
      </Stack>

      {total > perPage && (
        <Group justify="center" mt="md">
          <Pagination total={Math.ceil(total / perPage)} value={page} onChange={setPage} />
        </Group>
      )}
    </Container>
  )
}

export default ReviewQueue
