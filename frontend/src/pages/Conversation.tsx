/**
 * Conversation.tsx
 * Purpose: Conversation Builder — learn to hold a Bible conversation in Chuukese.
 *
 * Pick a subject and statement from "Truths We Love to Teach" (or this week's
 * meeting-workbook part), then walk a branching flow from the greeting down:
 * at every step the page offers lines to say (Chuukese with English), shows
 * what the person may answer, and each answer leads to the next step. The Map
 * view shows every split at once. Lines quoted from Love People—Make Disciples
 * are authentic; authored lines are machine translated until corrected here.
 * Conversations are saved per user.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ActionIcon, Alert, Badge, Box, Button, Card, Collapse, Divider, Group, Loader, Paper, ScrollArea,
  SegmentedControl, Select, Stack, Switch, Text, TextInput, Textarea, Title, Tooltip,
} from '@mantine/core'
import {
  IconArrowBackUp, IconCheck, IconChevronDown, IconChevronRight, IconDeviceFloppy, IconEdit, IconLanguage,
  IconMessages, IconPlus, IconPrinter, IconTrash, IconX,
} from '@tabler/icons-react'
import axios from 'axios'
import styles from './Conversation.module.css'

// ── Types ────────────────────────────────────────────────────────────────────

interface Bi { chk: string; en: string }
interface Phrase { id: string; en: string; chk: string; mt?: boolean; source?: string; engine?: string; scriptures?: Bi; point?: string }
interface Response { kind: string; label: Bi; they: Phrase[]; next: string }
interface FlowNode {
  id: string; title: Bi; stage: string; guidance: string; lessons: number[]
  think: Phrase[]; say: Phrase[]; lesson_phrases: Phrase[]; responses: Response[]
}
interface Statement { n: number; chk: string; en: string; scriptures: Bi }
interface Subject { id: string; title: Bi; statements: Statement[] }
interface WeekPart { n: number; title: Bi; minutes: number | null; setting: Bi; refs: { lmd?: { lesson: number; points: string }; lff?: { lesson: number; points: string } } }
interface Week { doc_id: string; title: Bi; start: string | null; end: string | null; parts: WeekPart[] }
interface LessonMeta { number: number; title: Bi; stage: Bi; principle: Bi }
interface Sources { has_sources: boolean; subjects: Subject[]; lessons: LessonMeta[]; weeks: Week[]; current_week: Week | null }
interface LessonPoint { n: number | null; pid: string; chk: string; en: string; items: { pid: string; chk: string; en: string; quoted: boolean }[] }
interface Lesson { number: number; stage: Bi; title: Bi; principle: Bi; sections: { heading: Bi; points: LessonPoint[] }[]; see_also: Bi }
interface Flow { start: string; nodes: Record<string, FlowNode>; subject: { id: string; title: Bi } | null; statement: Statement | null; next_statement: Statement | null; lesson: Lesson | null }
interface Step { node: string; line?: Phrase; custom?: Bi; response?: string }
interface SavedMeta { id: string; title: string; subject?: string; statement?: number; lesson?: number; step_count: number; updated_at?: string }

const errorMessage = (e: unknown, fallback: string) =>
  (axios.isAxiosError(e) && (e.response?.data?.error as string)) || (e instanceof Error ? e.message : fallback)

const RESPONSE_COLOR: Record<string, string> = { yes: 'green', no: 'red', busy: 'orange', question: 'blue', unsure: 'gray', later: 'teal', angry: 'red' }

// ── Line (one thing to say) ─────────────────────────────────────────────────

function Line({ phrase, selected, showEnglish, onSelect, onCorrected }: {
  phrase: Phrase; selected: boolean; showEnglish: boolean; onSelect: () => void; onCorrected: (p: Phrase) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(phrase.chk)
  const [saving, setSaving] = useState(false)
  const editable = !phrase.id.startsWith('lesson:') && !phrase.id.startsWith('truth-')

  const save = async () => {
    if (!draft.trim()) return
    setSaving(true)
    try {
      await axios.put(`/api/conversation/phrases/${encodeURIComponent(phrase.id)}`, { chk: draft.trim(), en: phrase.en })
      onCorrected({ ...phrase, chk: draft.trim(), mt: false })
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Paper withBorder p="sm" radius="md" className={`${styles.line} ${selected ? styles.lineSelected : ''}`} onClick={onSelect}>
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Box style={{ flex: 1 }}>
          {editing ? (
            <Group gap="xs" onClick={(e) => e.stopPropagation()}>
              <Textarea autosize minRows={1} value={draft} onChange={(e) => setDraft(e.currentTarget.value)} style={{ flex: 1 }} />
              <ActionIcon color="green" variant="light" onClick={save} loading={saving}><IconCheck size={16} /></ActionIcon>
              <ActionIcon color="gray" variant="light" onClick={() => setEditing(false)}><IconX size={16} /></ActionIcon>
            </Group>
          ) : (
            <Text className={styles.chk}>{phrase.chk || <Text span c="dimmed" fs="italic">No Chuukese yet</Text>}</Text>
          )}
          {showEnglish && <Text size="sm" c="dimmed" mt={2}>{phrase.en}</Text>}
          {phrase.scriptures && (
            <Text size="sm" mt={4} c="violet">{phrase.scriptures.chk}{showEnglish && phrase.scriptures.en !== phrase.scriptures.chk ? ` · ${phrase.scriptures.en}` : ''}</Text>
          )}
          <Group gap={6} mt={6}>
            {phrase.source && phrase.source !== 'authored' && <Badge size="xs" variant="light" color="violet">{phrase.source}</Badge>}
            {phrase.mt && <Tooltip label="Machine translated. Click the pencil to correct it."><Badge size="xs" variant="outline" color="orange">machine translated</Badge></Tooltip>}
            {!phrase.mt && phrase.source === 'authored' && phrase.chk && <Badge size="xs" variant="outline" color="green">corrected</Badge>}
          </Group>
        </Box>
        {editable && !editing && (
          <ActionIcon variant="subtle" color="gray" onClick={(e) => { e.stopPropagation(); setDraft(phrase.chk); setEditing(true) }} title="Correct the Chuukese">
            <IconEdit size={16} />
          </ActionIcon>
        )}
      </Group>
    </Paper>
  )
}

// ── One step of the path ────────────────────────────────────────────────────

function StepCard({ index, node, step, isLast, showEnglish, onChoose, onCustom, onRespond, onRewind, onCorrected }: {
  index: number; node: FlowNode; step: Step; isLast: boolean; showEnglish: boolean
  onChoose: (p: Phrase) => void; onCustom: (line: Bi) => void; onRespond: (kind: string) => void; onRewind: () => void
  onCorrected: (p: Phrase) => void
}) {
  const [custom, setCustom] = useState('')
  const [customChk, setCustomChk] = useState('')
  const [translating, setTranslating] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const [guideOpen, setGuideOpen] = useState(index === 0)
  const chosen = step.response ? node.responses.find((r) => r.kind === step.response) : null

  const translate = async () => {
    if (!custom.trim()) return
    setTranslating(true)
    try {
      const isEnglish = [...custom].every((c) => c.charCodeAt(0) < 128 || !/\p{L}/u.test(c))
      const res = await axios.post('/api/translate', { text: custom.trim(), direction: isEnglish ? 'en_to_chk' : 'chk_to_en' })
      const t = res.data?.translations || {}
      const pick = ['helsinki', 'madlad', 'model', 'google', 'ollama'].map((k) => t[k]?.text ?? t[k]).find((v) => typeof v === 'string' && v.trim())
      if (isEnglish) setCustomChk(String(pick || ''))
      else setCustomChk(custom.trim())
      if (!isEnglish && pick) setCustom(String(pick))
    } finally {
      setTranslating(false)
    }
  }

  return (
    <Card withBorder radius="md" className={`${styles.step} ${isLast ? styles.stepActive : ''}`}>
      <Group justify="space-between" mb="xs">
        <Group gap="sm">
          <Text className={styles.stepNumber}>{index + 1}</Text>
          <div>
            <Title order={4}>{node.title.chk || node.title.en}</Title>
            {node.title.chk && showEnglish && <Text size="sm" c="dimmed">{node.title.en}</Text>}
          </div>
        </Group>
        <Group gap="xs">
          <Badge variant="light" color={node.stage === 'start' ? 'blue' : node.stage === 'teach' ? 'violet' : 'teal'}>{node.stage}</Badge>
          {!isLast && <Button size="xs" variant="subtle" leftSection={<IconArrowBackUp size={14} />} onClick={onRewind}>Change from here</Button>}
        </Group>
      </Group>

      {node.guidance && (
        <Box mb="sm">
          <Button size="compact-xs" variant="subtle" color="gray" onClick={() => setGuideOpen((o) => !o)} rightSection={guideOpen ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}>
            Guidance
          </Button>
          <Collapse in={guideOpen}><Text size="sm" c="dimmed" pl="xs">{node.guidance}</Text></Collapse>
        </Box>
      )}

      {node.think.length > 0 && (
        <Paper bg="var(--mantine-color-gray-light)" p="xs" radius="sm" mb="sm">
          <Text size="xs" fw={700} c="dimmed" tt="uppercase">Ask yourself first</Text>
          {node.think.map((t) => (
            <Text key={t.id} size="sm" fs="italic">{t.chk}{showEnglish ? ` — ${t.en}` : ''}</Text>
          ))}
        </Paper>
      )}

      {node.say.length > 0 && (
        <>
          <Text fw={700} size="sm" mb={4}>You say</Text>
          <Stack gap="xs">
            {node.say.map((p) => (
              <Line key={p.id} phrase={p} selected={step.line?.id === p.id} showEnglish={showEnglish} onSelect={() => onChoose(p)} onCorrected={onCorrected} />
            ))}
          </Stack>
        </>
      )}

      {node.lesson_phrases.length > 0 && (
        <Box mt="sm">
          <Button size="compact-sm" variant="light" color="violet" onClick={() => setMoreOpen((o) => !o)} rightSection={moreOpen ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}>
            {node.lesson_phrases.length} lines from Love People—Make Disciples
          </Button>
          <Collapse in={moreOpen}>
            <Stack gap="xs" mt="xs">
              {node.lesson_phrases.map((p) => (
                <Line key={p.id} phrase={p} selected={step.line?.id === p.id} showEnglish={showEnglish} onSelect={() => onChoose(p)} onCorrected={onCorrected} />
              ))}
            </Stack>
          </Collapse>
        </Box>
      )}

      {node.responses.length > 0 && (
        <Box mt="sm">
          <Text fw={700} size="sm" mb={4}>Or write your own line</Text>
          <Group gap="xs" align="flex-start">
            <TextInput placeholder="English or Chuukese" value={custom} onChange={(e) => setCustom(e.currentTarget.value)} style={{ flex: 1 }}
              onKeyDown={(e) => e.key === 'Enter' && translate()} />
            <Button variant="light" leftSection={<IconLanguage size={16} />} onClick={translate} loading={translating}>Translate</Button>
          </Group>
          {customChk && (
            <Paper withBorder p="sm" mt="xs" radius="md" className={`${styles.line} ${step.custom?.chk === customChk ? styles.lineSelected : ''}`} onClick={() => onCustom({ chk: customChk, en: custom })}>
              <Text className={styles.chk}>{customChk}</Text>
              {showEnglish && <Text size="sm" c="dimmed">{custom}</Text>}
              <Badge size="xs" variant="outline" color="orange" mt={6}>machine translated</Badge>
            </Paper>
          )}
        </Box>
      )}

      {node.responses.length > 0 && (
        <Box mt="md">
          <Text fw={700} size="sm" mb={6}>They respond…</Text>
          <Stack gap="xs">
            {node.responses.map((r) => {
              const active = step.response === r.kind
              return (
                <Paper key={r.kind} withBorder p="sm" radius="md" className={`${styles.response} ${active ? styles.responseActive : ''}`}>
                  <Group justify="space-between" wrap="nowrap" align="flex-start">
                    <Box style={{ flex: 1 }}>
                      <Group gap="xs">
                        <Badge color={RESPONSE_COLOR[r.kind] || 'gray'} variant={active ? 'filled' : 'light'}>{r.kind}</Badge>
                        <Text fw={600} size="sm">{r.label.chk || r.label.en}</Text>
                        {r.label.chk && showEnglish && <Text size="sm" c="dimmed">({r.label.en})</Text>}
                      </Group>
                      {r.they.map((t) => (
                        <Text key={t.id} size="sm" mt={4} pl="xs" className={styles.they}>
                          “{t.chk || t.en}”{t.chk && showEnglish ? <Text span c="dimmed"> — {t.en}</Text> : null}
                        </Text>
                      ))}
                    </Box>
                    <Button size="xs" variant={active ? 'filled' : 'default'} color={RESPONSE_COLOR[r.kind] || 'gray'} onClick={() => onRespond(r.kind)} disabled={!isLast && !active}>
                      {active ? 'Chosen' : 'Then…'}
                    </Button>
                  </Group>
                </Paper>
              )
            })}
          </Stack>
          {chosen && <Text size="xs" c="dimmed" mt={6}>Next: {chosen.next}</Text>}
        </Box>
      )}
    </Card>
  )
}

// ── Map of every split ──────────────────────────────────────────────────────

function MapNode({ id, nodes, showEnglish, depth, trail }: { id: string; nodes: Record<string, FlowNode>; showEnglish: boolean; depth: number; trail: string[] }) {
  const node = nodes[id]
  const [open, setOpen] = useState(depth < 2)
  if (!node) return null
  const repeated = trail.includes(id)
  return (
    <Box className={styles.mapNode}>
      <Group gap="xs" wrap="nowrap" align="flex-start">
        {node.responses.length > 0 && !repeated ? (
          <ActionIcon size="sm" variant="subtle" onClick={() => setOpen((o) => !o)}>{open ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}</ActionIcon>
        ) : <Box w={22} />}
        <Box>
          <Text fw={700}>{node.title.chk || node.title.en}{node.title.chk && showEnglish ? <Text span c="dimmed" fw={400}> · {node.title.en}</Text> : null}</Text>
          {repeated ? (
            <Text size="xs" c="dimmed">(continues as above)</Text>
          ) : (
            node.say.slice(0, 2).map((p) => <Text key={p.id} size="sm" className={styles.mapSay}>“{p.chk || p.en}”</Text>)
          )}
        </Box>
      </Group>
      {!repeated && (
        <Collapse in={open}>
          <Stack gap={6} mt={6} className={styles.mapBranches}>
            {node.responses.map((r) => (
              <Box key={r.kind}>
                <Group gap={6}>
                  <Text size="sm" c="dimmed">If they say</Text>
                  <Badge color={RESPONSE_COLOR[r.kind] || 'gray'} variant="light" size="sm">{r.label.chk || r.label.en}</Badge>
                  {r.label.chk && showEnglish && <Text size="xs" c="dimmed">({r.label.en})</Text>}
                  <Text size="sm" c="dimmed">→</Text>
                </Group>
                <MapNode id={r.next} nodes={nodes} showEnglish={showEnglish} depth={depth + 1} trail={[...trail, id]} />
              </Box>
            ))}
          </Stack>
        </Collapse>
      )}
    </Box>
  )
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function Conversation() {
  const [sources, setSources] = useState<Sources | null>(null)
  const [subjectId, setSubjectId] = useState<string | null>(null)
  const [statementN, setStatementN] = useState<number | null>(null)
  const [lessonN, setLessonN] = useState<number | null>(null)
  const [weekPart, setWeekPart] = useState<WeekPart | null>(null)
  const [flow, setFlow] = useState<Flow | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [path, setPath] = useState<Step[]>([])
  const [view, setView] = useState<'path' | 'map'>('path')
  const [showEnglish, setShowEnglish] = useState(true)
  const [saved, setSaved] = useState<SavedMeta[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [saving, setSaving] = useState(false)
  const pendingPath = useRef<Step[] | null>(null)

  const subject = useMemo(() => sources?.subjects.find((s) => s.id === subjectId) || null, [sources, subjectId])

  const loadSaved = useCallback(async () => {
    try { setSaved((await axios.get('/api/conversations')).data) } catch { /* sidebar only */ }
  }, [])

  useEffect(() => {
    (async () => {
      try {
        const res = await axios.get<Sources>('/api/conversation/sources')
        setSources(res.data)
        if (res.data.subjects[0]) {
          setSubjectId(res.data.subjects[0].id)
          setStatementN(res.data.subjects[0].statements[0]?.n ?? null)
        }
      } catch (e) {
        setError(errorMessage(e, 'Could not load the conversation sources'))
      }
      loadSaved()
    })()
  }, [loadSaved])

  // Reload the flow whenever the subject, statement or lesson changes.
  useEffect(() => {
    if (!subjectId) return
    let cancelled = false
    setLoading(true)
    axios.get<Flow>('/api/conversation/flow', { params: { subject: subjectId, statement: statementN ?? undefined, lesson: lessonN ?? undefined } })
      .then((res) => {
        if (cancelled) return
        setFlow(res.data)
        setPath(pendingPath.current ?? [{ node: res.data.start }])
        pendingPath.current = null
      })
      .catch((e) => !cancelled && setError(errorMessage(e, 'Could not load the flow')))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [subjectId, statementN, lessonN])

  const chooseSubject = (id: string | null) => {
    setSubjectId(id)
    const s = sources?.subjects.find((x) => x.id === id)
    setStatementN(s?.statements[0]?.n ?? null)
    setActiveId(null)
  }

  const applyWeekPart = (part: WeekPart) => {
    setWeekPart(part)
    if (part.refs.lmd) setLessonN(part.refs.lmd.lesson)
  }

  // ── Path edits ──
  const updateStep = (i: number, patch: Partial<Step>) => setPath((p) => p.map((s, k) => (k === i ? { ...s, ...patch } : s)))
  const respond = (i: number, kind: string) => {
    if (!flow) return
    const node = flow.nodes[path[i].node]
    const r = node.responses.find((x) => x.kind === kind)
    if (!r) return
    setPath((p) => [...p.slice(0, i), { ...p[i], response: kind }, { node: r.next }])
  }
  const rewind = (i: number) => setPath((p) => p.slice(0, i + 1).map((s, k) => (k === i ? { ...s, response: undefined } : s)))
  const restart = () => flow && setPath([{ node: flow.start }])
  const correctPhrase = (updated: Phrase) => {
    setFlow((f) => {
      if (!f) return f
      const nodes = Object.fromEntries(Object.entries(f.nodes).map(([k, n]) => [k, {
        ...n,
        say: n.say.map((p) => (p.id === updated.id ? updated : p)),
        think: n.think.map((p) => (p.id === updated.id ? updated : p)),
        responses: n.responses.map((r) => ({ ...r, they: r.they.map((p) => (p.id === updated.id ? updated : p)) })),
      }]))
      return { ...f, nodes }
    })
    setPath((p) => p.map((s) => (s.line?.id === updated.id ? { ...s, line: updated } : s)))
  }

  // ── Save / load ──
  const defaultTitle = () => {
    const st = flow?.statement
    return subject && st ? `${subject.title.chk}: ${st.chk}` : subject?.title.chk || 'Conversation'
  }
  const save = async () => {
    setSaving(true)
    try {
      const res = await axios.post('/api/conversations', {
        id: activeId || undefined, title: title.trim() || defaultTitle(), subject: subjectId, statement: statementN, lesson: lessonN,
        week: weekPart ? { part: weekPart.n, setting: weekPart.setting } : null, path,
      })
      setActiveId(res.data.id)
      await loadSaved()
    } catch (e) {
      setError(errorMessage(e, 'Could not save'))
    } finally {
      setSaving(false)
    }
  }
  const open = async (id: string) => {
    try {
      const doc = (await axios.get(`/api/conversations/${id}`)).data
      setActiveId(id)
      setTitle(doc.title || '')
      pendingPath.current = doc.path
      setLessonN(doc.lesson ?? null)
      if (doc.subject === subjectId && doc.statement === statementN) {
        setPath(doc.path); pendingPath.current = null
      } else {
        setSubjectId(doc.subject); setStatementN(doc.statement)
      }
    } catch (e) {
      setError(errorMessage(e, 'Could not open the conversation'))
    }
  }
  const remove = async (id: string) => {
    await axios.delete(`/api/conversations/${id}`)
    if (activeId === id) setActiveId(null)
    loadSaved()
  }

  const transcript = useMemo(() => path.filter((s) => s.line || s.custom), [path])

  if (!sources) return <Group justify="center" p="xl">{error ? <Alert color="red">{error}</Alert> : <Loader />}</Group>

  if (!sources.has_sources) {
    return (
      <Alert color="yellow" title="Sources not harvested yet">
        Run <code>scripts/harvest_conversation_sources.py</code> once to pull Love People—Make Disciples and the meeting workbook from wol.jw.org.
      </Alert>
    )
  }

  return (
    <div className={styles.page}>
      <Group justify="space-between" mb="md" wrap="wrap">
        <div>
          <Title order={2}><IconMessages size={26} style={{ verticalAlign: 'middle' }} /> Conversation Builder</Title>
          <Text c="dimmed" size="sm">Choose a Bible truth, then follow the conversation from the greeting down. Every answer the person gives opens the next step.</Text>
        </div>
        <Group gap="sm">
          <Switch label="Show English" checked={showEnglish} onChange={(e) => setShowEnglish(e.currentTarget.checked)} />
          <SegmentedControl value={view} onChange={(v) => setView(v as 'path' | 'map')} data={[{ label: 'Path', value: 'path' }, { label: 'Map of every split', value: 'map' }]} />
        </Group>
      </Group>

      {error && <Alert color="red" mb="md" withCloseButton onClose={() => setError('')}>{error}</Alert>}

      <div className={styles.layout}>
        {/* ── Left: subject & saved ── */}
        <Stack gap="md" className={styles.side}>
          <Card withBorder radius="md" p="sm">
            <Text fw={700} size="sm" mb={6}>Subject · Truths We Love to Teach</Text>
            <Select data={sources.subjects.map((s) => ({ value: s.id, label: `${s.title.chk} · ${s.title.en}` }))} value={subjectId} onChange={chooseSubject} allowDeselect={false} />
            <Stack gap={4} mt="sm">
              {subject?.statements.map((st) => (
                <Paper key={st.n} withBorder p="xs" radius="sm" className={`${styles.statement} ${statementN === st.n ? styles.statementActive : ''}`} onClick={() => { setStatementN(st.n); setActiveId(null) }}>
                  <Text size="sm" fw={600}>{st.n}. {st.chk}</Text>
                  {showEnglish && <Text size="xs" c="dimmed">{st.en}</Text>}
                  <Text size="xs" c="violet">{st.scriptures.chk}</Text>
                </Paper>
              ))}
            </Stack>
          </Card>

          {sources.current_week && (
            <Card withBorder radius="md" p="sm">
              <Text fw={700} size="sm">This week in the workbook</Text>
              <Text size="xs" c="dimmed" mb={6}>{sources.current_week.title.en}</Text>
              <Stack gap={4}>
                {sources.current_week.parts.map((p) => (
                  <Paper key={p.n} withBorder p="xs" radius="sm" className={`${styles.statement} ${weekPart?.n === p.n ? styles.statementActive : ''}`} onClick={() => applyWeekPart(p)}>
                    <Text size="sm" fw={600}>{p.n}. {p.title.chk}</Text>
                    {showEnglish && <Text size="xs" c="dimmed">{p.title.en}</Text>}
                    {p.setting.chk && <Text size="xs" mt={2}>{p.setting.chk}</Text>}
                    {p.setting.en && showEnglish && <Text size="xs" c="dimmed">{p.setting.en}</Text>}
                    {p.refs.lmd && <Badge size="xs" variant="light" color="violet" mt={4}>Love People lesson {p.refs.lmd.lesson} point {p.refs.lmd.points}</Badge>}
                  </Paper>
                ))}
              </Stack>
            </Card>
          )}

          <Card withBorder radius="md" p="sm">
            <Text fw={700} size="sm" mb={6}>Love People lesson</Text>
            <Select clearable placeholder="Optional: focus a lesson" value={lessonN ? String(lessonN) : null} onChange={(v) => setLessonN(v ? Number(v) : null)}
              data={sources.lessons.map((l) => ({ value: String(l.number), label: `${l.number}. ${l.title.chk} · ${l.title.en}` }))} />
            {flow?.lesson && (
              <Box mt="sm">
                <Text size="xs" c="dimmed">{flow.lesson.stage.chk}</Text>
                <Text size="sm" fs="italic">{flow.lesson.principle.chk}</Text>
                {showEnglish && <Text size="xs" c="dimmed">{flow.lesson.principle.en}</Text>}
                {flow.lesson.sections.map((sec) => (
                  <Box key={sec.heading.en} mt="xs">
                    <Text size="xs" fw={700} tt="uppercase" c="dimmed">{sec.heading.chk}</Text>
                    {sec.points.filter((p) => p.n).map((p) => (
                      <Text key={p.pid} size="xs" mt={2}><b>{p.n}.</b> {p.chk}</Text>
                    ))}
                  </Box>
                ))}
              </Box>
            )}
          </Card>

          <Card withBorder radius="md" p="sm">
            <Text fw={700} size="sm" mb={6}>My conversations</Text>
            {saved.length === 0 && <Text size="xs" c="dimmed">Nothing saved yet.</Text>}
            <Stack gap={4}>
              {saved.map((s) => (
                <Group key={s.id} justify="space-between" wrap="nowrap" className={`${styles.savedRow} ${activeId === s.id ? styles.statementActive : ''}`}>
                  <Text size="sm" lineClamp={2} style={{ cursor: 'pointer', flex: 1 }} onClick={() => open(s.id)}>{s.title}</Text>
                  <ActionIcon size="sm" variant="subtle" color="red" onClick={() => remove(s.id)}><IconTrash size={14} /></ActionIcon>
                </Group>
              ))}
            </Stack>
          </Card>
        </Stack>

        {/* ── Main ── */}
        <Box className={styles.main}>
          {flow?.statement && (
            <Paper withBorder radius="md" p="md" mb="md" className={styles.truth}>
              <Text size="xs" fw={700} tt="uppercase" c="dimmed">The truth you will share</Text>
              <Text className={styles.truthChk}>{flow.statement.chk}</Text>
              {showEnglish && <Text c="dimmed">{flow.statement.en}</Text>}
              <Text c="violet" fw={600} mt={4}>{flow.statement.scriptures.chk}{showEnglish ? ` · ${flow.statement.scriptures.en}` : ''}</Text>
              {weekPart && <Text size="sm" mt={6}><b>Setting:</b> {weekPart.setting.chk}{showEnglish && weekPart.setting.en ? ` — ${weekPart.setting.en}` : ''}</Text>}
            </Paper>
          )}

          {loading && <Group justify="center" p="md"><Loader size="sm" /></Group>}

          {flow && view === 'map' && (
            <Card withBorder radius="md" p="md">
              <Text c="dimmed" size="sm" mb="sm">Every step, and where each answer leads. Open a branch to follow it.</Text>
              <ScrollArea.Autosize mah="75vh">
                <MapNode id={flow.start} nodes={flow.nodes} showEnglish={showEnglish} depth={0} trail={[]} />
              </ScrollArea.Autosize>
            </Card>
          )}

          {flow && view === 'path' && (
            <Stack gap="md">
              {path.map((step, i) => {
                const node = flow.nodes[step.node]
                if (!node) return null
                return (
                  <StepCard key={`${step.node}-${i}`} index={i} node={node} step={step} isLast={i === path.length - 1} showEnglish={showEnglish}
                    onChoose={(p) => updateStep(i, { line: p, custom: undefined })} onCustom={(line) => updateStep(i, { custom: line, line: undefined })}
                    onRespond={(kind) => respond(i, kind)} onRewind={() => rewind(i)} onCorrected={correctPhrase} />
                )
              })}

              <Card withBorder radius="md" p="md">
                <Group justify="space-between" wrap="wrap">
                  <TextInput placeholder={defaultTitle()} value={title} onChange={(e) => setTitle(e.currentTarget.value)} style={{ flex: 1, minWidth: 220 }} label="Name" />
                  <Group gap="xs" mt={24}>
                    <Button variant="default" leftSection={<IconPlus size={16} />} onClick={() => { restart(); setActiveId(null); setTitle('') }}>Start over</Button>
                    <Button variant="light" leftSection={<IconPrinter size={16} />} onClick={() => window.print()}>Print</Button>
                    <Button leftSection={<IconDeviceFloppy size={16} />} onClick={save} loading={saving}>{activeId ? 'Save changes' : 'Save'}</Button>
                  </Group>
                </Group>
                {transcript.length > 0 && (
                  <>
                    <Divider my="sm" label="Your conversation so far" />
                    <Stack gap={6} className={styles.transcript}>
                      {transcript.map((s, i) => {
                        const node = flow.nodes[s.node]
                        const r = s.response ? node?.responses.find((x) => x.kind === s.response) : null
                        const line = s.line ? { chk: s.line.chk, en: s.line.en } : s.custom!
                        return (
                          <Box key={i}>
                            <Text size="sm"><b>You:</b> {line.chk || line.en}</Text>
                            {showEnglish && line.chk && <Text size="xs" c="dimmed" pl="lg">{line.en}</Text>}
                            {r?.they[0] && <Text size="sm" c="dimmed"><b>They:</b> {r.they[0].chk || r.they[0].en}</Text>}
                          </Box>
                        )
                      })}
                    </Stack>
                  </>
                )}
              </Card>
            </Stack>
          )}
        </Box>
      </div>
    </div>
  )
}
