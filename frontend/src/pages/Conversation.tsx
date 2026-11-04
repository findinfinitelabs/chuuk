/**
 * Conversation.tsx
 * Purpose: Conversation Builder — learn to hold a Bible conversation in Chuukese.
 *
 * The conversation is a flow diagram: each step is a node, each answer the
 * person may give is a labelled edge to the next step. Pick a subject and
 * statement from "Truths We Love to Teach" (or this week's workbook part),
 * click a node to see what to say there, click an answer edge to walk down
 * it; the path you take lights up and becomes the transcript. Lines quoted
 * from Love People—Make Disciples are authentic; authored lines are machine
 * translated until corrected here (correcting one side suggests the other by
 * back-translation). Conversations are saved per user.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ActionIcon, Alert, Badge, Box, Button, Card, Collapse, Divider, Group, Loader, Menu, Paper, ScrollArea,
  Select, Stack, Switch, Text, TextInput, Textarea, Title, Tooltip,
} from '@mantine/core'
import {
  IconCheck, IconChevronDown, IconChevronRight, IconDeviceFloppy, IconEdit, IconFolderOpen, IconLanguage,
  IconMessages, IconPlus, IconPrinter, IconTrash, IconX,
} from '@tabler/icons-react'
import {
  Background, Controls, Handle, MiniMap, Position, ReactFlow, ReactFlowProvider, useReactFlow,
  type Edge, type Node, type NodeProps, type EdgeMouseHandler, type NodeMouseHandler,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from '@dagrejs/dagre'
import axios from 'axios'
import styles from './Conversation.module.css'
import AddToTalk from '../components/AddToTalk'

// ── Types ────────────────────────────────────────────────────────────────────

interface Bi { chk: string; en: string }
interface Phrase { id: string; en: string; chk: string; mt?: boolean; source?: string; scriptures?: Bi; point?: string }
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

const KIND_COLOR: Record<string, string> = { yes: '#2f9e44', no: '#e03131', busy: '#f08c00', question: '#1971c2', unsure: '#868e96', later: '#0c8599', angry: '#c2255c' }
const STAGE_COLOR: Record<string, string> = { start: '#1971c2', teach: '#7048e8', close: '#0c8599' }

/** Translate one way with the site's models; returns '' when nothing usable came back. */
async function machineTranslate(text: string, direction: 'en_to_chk' | 'chk_to_en'): Promise<string> {
  const res = await axios.post('/api/translate', { text, direction })
  const t = res.data?.translations || {}
  // The server says which engine to show first (Google on the hosted site, the neural model locally).
  const order = [res.data?.preferred === 'google' ? 'google' : 'helsinki', 'helsinki', 'madlad', 'model', 'google']
  const pick = order.map((k) => (typeof t[k] === 'string' ? t[k] : t[k]?.text)).find((v) => typeof v === 'string' && v.trim() && !/error|not available|not configured/i.test(v))
  return pick ? String(pick).trim() : ''
}

const looksEnglish = (s: string) => [...s].every((c) => c.charCodeAt(0) < 128 || !/\p{L}/u.test(c))

// ── Diagram node ────────────────────────────────────────────────────────────

type StepNodeData = { node: FlowNode; index: number | null; selected: boolean; onPath: boolean; showEnglish: boolean; dim: boolean }

function StepNode({ data }: NodeProps<Node<StepNodeData>>) {
  const { node, index, selected, onPath, showEnglish, dim } = data
  const first = node.say[0]
  return (
    <div className={`${styles.node} ${onPath ? styles.nodeOnPath : ''} ${selected ? styles.nodeSelected : ''} ${dim ? styles.nodeDim : ''}`} style={{ borderTopColor: STAGE_COLOR[node.stage] || '#868e96' }}>
      <Handle type="target" position={Position.Top} className={styles.handle} />
      <div className={styles.nodeHead}>
        <span className={styles.nodeIndex} style={{ background: index !== null ? STAGE_COLOR[node.stage] : '#adb5bd' }}>{index !== null ? index + 1 : '·'}</span>
        <span className={styles.nodeTitle}>{node.title.chk || node.title.en}</span>
      </div>
      {node.title.chk && showEnglish && <div className={styles.nodeSub}>{node.title.en}</div>}
      {first && <div className={styles.nodeLine}>“{first.chk || first.en}”</div>}
      {node.responses.length === 0 && <div className={styles.nodeSub}>End</div>}
      <Handle type="source" position={Position.Bottom} className={styles.handle} />
    </div>
  )
}
const nodeTypes = { step: StepNode }

const NODE_W = 260
const NODE_H = 96

function layout(flow: Flow, path: Step[], selectedId: string | null, showEnglish: boolean): { nodes: Node<StepNodeData>[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'TB', nodesep: 36, ranksep: 64, marginx: 20, marginy: 20 })
  Object.keys(flow.nodes).forEach((id) => g.setNode(id, { width: NODE_W, height: NODE_H }))
  Object.values(flow.nodes).forEach((n) => n.responses.forEach((r) => g.setEdge(n.id, r.next)))
  dagre.layout(g)

  const pathIndex = new Map<string, number>()
  path.forEach((s, i) => { if (!pathIndex.has(s.node)) pathIndex.set(s.node, i) })
  const takenEdges = new Set(path.filter((s) => s.response).map((s) => `${s.node}:${s.response}`))
  const anyPath = path.length > 1

  const nodes: Node<StepNodeData>[] = Object.values(flow.nodes).map((n) => {
    const p = g.node(n.id)
    const onPath = pathIndex.has(n.id)
    return {
      id: n.id, type: 'step', position: { x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 },
      data: { node: n, index: onPath ? pathIndex.get(n.id)! : null, selected: selectedId === n.id, onPath, showEnglish, dim: anyPath && !onPath && selectedId !== n.id },
      draggable: false, selectable: true,
    }
  })
  const edges: Edge[] = []
  Object.values(flow.nodes).forEach((n) => n.responses.forEach((r) => {
    const taken = takenEdges.has(`${n.id}:${r.kind}`)
    const color = KIND_COLOR[r.kind] || '#868e96'
    edges.push({
      id: `${n.id}:${r.kind}`, source: n.id, target: r.next, data: { from: n.id, kind: r.kind },
      label: r.label.chk || r.label.en, labelStyle: { fill: color, fontWeight: 700, fontSize: 11 },
      labelBgStyle: { fill: 'white', stroke: color, strokeWidth: taken ? 2 : 1 }, labelBgPadding: [6, 3], labelBgBorderRadius: 6,
      style: { stroke: color, strokeWidth: taken ? 3.5 : 1.6, opacity: anyPath && !taken ? 0.45 : 1 },
      animated: taken, type: 'smoothstep', markerEnd: 'url(#arrow)',
    })
  }))
  return { nodes, edges }
}

function Canvas({ flow, path, selectedId, showEnglish, onSelect, onEdge }: {
  flow: Flow; path: Step[]; selectedId: string | null; showEnglish: boolean; onSelect: (id: string) => void; onEdge: (from: string, kind: string) => void
}) {
  const { nodes, edges } = useMemo(() => layout(flow, path, selectedId, showEnglish), [flow, path, selectedId, showEnglish])
  const rf = useReactFlow()
  const onNodeClick: NodeMouseHandler = useCallback((_, n) => onSelect(n.id), [onSelect])
  const onEdgeClick: EdgeMouseHandler = useCallback((_, e) => { const d = e.data as { from: string; kind: string }; onEdge(d.from, d.kind) }, [onEdge])
  useEffect(() => { const t = setTimeout(() => rf.fitView({ padding: 0.15, duration: 300 }), 50); return () => clearTimeout(t) }, [flow.start, rf])
  return (
    <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodeClick={onNodeClick} onEdgeClick={onEdgeClick}
      fitView minZoom={0.2} maxZoom={1.6} nodesConnectable={false} elementsSelectable proOptions={{ hideAttribution: true }}>
      <svg><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#868e96" /></marker></defs></svg>
      <Background gap={18} size={1} />
      <Controls showInteractive={false} />
      <MiniMap pannable zoomable nodeColor={(n) => STAGE_COLOR[(n.data as StepNodeData).node.stage] || '#ccc'} />
    </ReactFlow>
  )
}

// ── One line to say ─────────────────────────────────────────────────────────

function Line({ phrase, selected, showEnglish, onSelect, onCorrected }: {
  phrase: Phrase; selected: boolean; showEnglish: boolean; onSelect: () => void; onCorrected: (p: Phrase) => void
}) {
  const [editing, setEditing] = useState(false)
  const [chk, setChk] = useState(phrase.chk)
  const [en, setEn] = useState(phrase.en)
  const [suggesting, setSuggesting] = useState<'en' | 'chk' | null>(null)
  const [saving, setSaving] = useState(false)
  const timer = useRef<number | null>(null)
  const editable = !phrase.id.startsWith('lesson:') && !phrase.id.startsWith('truth-')

  // Changing one language suggests the other by back-translation, after a pause.
  const suggest = (side: 'en' | 'chk', text: string) => {
    if (timer.current) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(async () => {
      if (!text.trim()) return
      setSuggesting(side)
      try {
        const out = await machineTranslate(text.trim(), side === 'en' ? 'chk_to_en' : 'en_to_chk')
        if (out) (side === 'en' ? setEn : setChk)(out)
      } finally {
        setSuggesting(null)
      }
    }, 900)
  }

  const save = async () => {
    if (!chk.trim()) return
    setSaving(true)
    try {
      await axios.put(`/api/conversation/phrases/${encodeURIComponent(phrase.id)}`, { chk: chk.trim(), en: en.trim() })
      onCorrected({ ...phrase, chk: chk.trim(), en: en.trim() || phrase.en, mt: false })
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Paper withBorder p="sm" radius="md" className={`${styles.line} ${selected ? styles.lineSelected : ''}`} onClick={onSelect}>
      {editing ? (
        <Stack gap={6} onClick={(e) => e.stopPropagation()}>
          <Textarea autosize minRows={1} label="Chuukese" value={chk} onChange={(e) => { setChk(e.currentTarget.value); suggest('en', e.currentTarget.value) }} rightSection={suggesting === 'chk' ? <Loader size={14} /> : null} />
          <Textarea autosize minRows={1} label="English" value={en} onChange={(e) => { setEn(e.currentTarget.value); suggest('chk', e.currentTarget.value) }} rightSection={suggesting === 'en' ? <Loader size={14} /> : null} />
          <Text size="xs" c="dimmed">Edit either side; the other is suggested by the translator and you can change it before saving.</Text>
          <Group gap="xs" justify="flex-end">
            <Button size="xs" variant="default" leftSection={<IconX size={14} />} onClick={() => { setEditing(false); setChk(phrase.chk); setEn(phrase.en) }}>Cancel</Button>
            <Button size="xs" color="green" leftSection={<IconCheck size={14} />} onClick={save} loading={saving}>Save correction</Button>
          </Group>
        </Stack>
      ) : (
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Box style={{ flex: 1 }}>
            <Text className={styles.chk}>{phrase.chk || <Text span c="dimmed" fs="italic">No Chuukese yet</Text>}</Text>
            {showEnglish && <Text size="sm" c="dimmed" mt={2}>{phrase.en}</Text>}
            {phrase.scriptures && <Text size="sm" mt={4} c="violet">{phrase.scriptures.chk}{showEnglish && phrase.scriptures.en !== phrase.scriptures.chk ? ` · ${phrase.scriptures.en}` : ''}</Text>}
            <Group gap={6} mt={6}>
              {phrase.source && phrase.source !== 'authored' && <Badge size="xs" variant="light" color="violet">{phrase.source}</Badge>}
              {phrase.mt && <Tooltip label="Machine translated. Click the pencil to correct it."><Badge size="xs" variant="outline" color="orange">machine translated</Badge></Tooltip>}
              {!phrase.mt && phrase.source === 'authored' && phrase.chk && <Badge size="xs" variant="outline" color="green">corrected</Badge>}
            </Group>
          </Box>
          <Group gap={2} wrap="nowrap">
            {phrase.chk && <AddToTalk chk={phrase.chk} en={phrase.en} source="conversation" reference={phrase.source && phrase.source !== 'authored' ? phrase.source : ''} />}
            {editable && (
              <ActionIcon variant="subtle" color="gray" onClick={(e) => { e.stopPropagation(); setChk(phrase.chk); setEn(phrase.en); setEditing(true) }} title="Correct this line">
                <IconEdit size={16} />
              </ActionIcon>
            )}
          </Group>
        </Group>
      )}
    </Paper>
  )
}

// ── Side panel for the selected step ────────────────────────────────────────

function StepPanel({ node, step, stepIndex, isCurrent, showEnglish, onChoose, onCustom, onRespond, onCorrected }: {
  node: FlowNode; step: Step | null; stepIndex: number | null; isCurrent: boolean; showEnglish: boolean
  onChoose: (p: Phrase) => void; onCustom: (line: Bi) => void; onRespond: (kind: string) => void; onCorrected: (p: Phrase) => void
}) {
  const [custom, setCustom] = useState('')
  const [customOut, setCustomOut] = useState<Bi | null>(null)
  const [translating, setTranslating] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const [guideOpen, setGuideOpen] = useState(true)
  useEffect(() => { setCustom(''); setCustomOut(null); setMoreOpen(false) }, [node.id])

  const translate = async () => {
    if (!custom.trim()) return
    setTranslating(true)
    try {
      const en = looksEnglish(custom)
      const out = await machineTranslate(custom.trim(), en ? 'en_to_chk' : 'chk_to_en')
      setCustomOut(en ? { en: custom.trim(), chk: out } : { chk: custom.trim(), en: out })
    } finally {
      setTranslating(false)
    }
  }

  return (
    <Stack gap="sm">
      <Group gap="sm" align="flex-start" wrap="nowrap">
        <Text className={styles.stepNumber} style={{ borderColor: STAGE_COLOR[node.stage], color: STAGE_COLOR[node.stage] }}>{stepIndex !== null ? stepIndex + 1 : '·'}</Text>
        <div>
          <Title order={4}>{node.title.chk || node.title.en}</Title>
          {node.title.chk && showEnglish && <Text size="sm" c="dimmed">{node.title.en}</Text>}
          {stepIndex === null && node.responses.length > 0 && <Text size="xs" c="orange">Not on your path yet. Click an answer on the diagram to get here.</Text>}
        </div>
      </Group>

      {node.guidance && (
        <Box>
          <Button size="compact-xs" variant="subtle" color="gray" onClick={() => setGuideOpen((o) => !o)} rightSection={guideOpen ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}>Guidance</Button>
          <Collapse in={guideOpen}><Text size="sm" c="dimmed" pl="xs">{node.guidance}</Text></Collapse>
        </Box>
      )}

      {node.think.length > 0 && (
        <Paper bg="var(--mantine-color-gray-light)" p="xs" radius="sm">
          <Text size="xs" fw={700} c="dimmed" tt="uppercase">Ask yourself first</Text>
          {node.think.map((t) => <Text key={t.id} size="sm" fs="italic">{t.chk}{showEnglish ? ` — ${t.en}` : ''}</Text>)}
        </Paper>
      )}

      {node.say.length > 0 && (
        <>
          <Text fw={700} size="sm">You say · pick one</Text>
          <Stack gap="xs">
            {node.say.map((p) => <Line key={p.id} phrase={p} selected={step?.line?.id === p.id} showEnglish={showEnglish} onSelect={() => onChoose(p)} onCorrected={onCorrected} />)}
          </Stack>
        </>
      )}

      {node.lesson_phrases.length > 0 && (
        <Box>
          <Button size="compact-sm" variant="light" color="violet" onClick={() => setMoreOpen((o) => !o)} rightSection={moreOpen ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}>
            {node.lesson_phrases.length} lines from Love People—Make Disciples
          </Button>
          <Collapse in={moreOpen}>
            <Stack gap="xs" mt="xs">
              {node.lesson_phrases.map((p) => <Line key={p.id} phrase={p} selected={step?.line?.id === p.id} showEnglish={showEnglish} onSelect={() => onChoose(p)} onCorrected={onCorrected} />)}
            </Stack>
          </Collapse>
        </Box>
      )}

      {node.responses.length > 0 && (
        <Box>
          <Text fw={700} size="sm" mb={4}>Or write your own line</Text>
          <Group gap="xs" align="flex-start">
            <TextInput placeholder="English or Chuukese" value={custom} onChange={(e) => setCustom(e.currentTarget.value)} style={{ flex: 1 }} onKeyDown={(e) => e.key === 'Enter' && translate()} />
            <Button variant="light" leftSection={<IconLanguage size={16} />} onClick={translate} loading={translating}>Translate</Button>
          </Group>
          {customOut && (
            <Paper withBorder p="sm" mt="xs" radius="md" className={`${styles.line} ${step?.custom?.chk === customOut.chk ? styles.lineSelected : ''}`} onClick={() => onCustom(customOut)}>
              <Text className={styles.chk}>{customOut.chk || <Text span c="dimmed" fs="italic">No translation</Text>}</Text>
              {showEnglish && <Text size="sm" c="dimmed">{customOut.en}</Text>}
              <Badge size="xs" variant="outline" color="orange" mt={6}>machine translated</Badge>
            </Paper>
          )}
        </Box>
      )}

      {node.responses.length > 0 && (
        <Box>
          <Text fw={700} size="sm" mb={6}>They answer… {isCurrent ? '' : '(only from your current step)'}</Text>
          <Stack gap="xs">
            {node.responses.map((r) => {
              const active = step?.response === r.kind
              const color = KIND_COLOR[r.kind] || '#868e96'
              return (
                <Paper key={r.kind} withBorder p="sm" radius="md" className={`${styles.response} ${active ? styles.responseActive : ''}`} style={{ borderLeftColor: color }}>
                  <Group justify="space-between" wrap="nowrap" align="flex-start">
                    <Box style={{ flex: 1 }}>
                      <Text fw={700} size="sm" style={{ color }}>{r.label.chk || r.label.en}{r.label.chk && showEnglish ? <Text span c="dimmed" fw={400}> · {r.label.en}</Text> : null}</Text>
                      {r.they.map((t) => <Text key={t.id} size="sm" mt={2} className={styles.they}>“{t.chk || t.en}”{t.chk && showEnglish ? <Text span c="dimmed"> — {t.en}</Text> : null}</Text>)}
                    </Box>
                    <Button size="xs" variant={active ? 'filled' : 'light'} style={active ? { background: color } : { color }} onClick={() => onRespond(r.kind)} disabled={!isCurrent && !active}>
                      {active ? 'Taken' : 'Go'}
                    </Button>
                  </Group>
                </Paper>
              )
            })}
          </Stack>
        </Box>
      )}
    </Stack>
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
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showEnglish, setShowEnglish] = useState(true)
  const [saved, setSaved] = useState<SavedMeta[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [saving, setSaving] = useState(false)
  const pendingPath = useRef<Step[] | null>(null)

  const subject = useMemo(() => sources?.subjects.find((s) => s.id === subjectId) || null, [sources, subjectId])

  const loadSaved = useCallback(async () => {
    try { setSaved((await axios.get('/api/conversations')).data) } catch { /* list only */ }
  }, [])

  useEffect(() => {
    (async () => {
      try {
        const res = await axios.get<Sources>('/api/conversation/sources')
        setSources(res.data)
        if (res.data.subjects[0]) { setSubjectId(res.data.subjects[0].id); setStatementN(res.data.subjects[0].statements[0]?.n ?? null) }
      } catch (e) {
        setError(errorMessage(e, 'Could not load the conversation sources'))
      }
      loadSaved()
    })()
  }, [loadSaved])

  useEffect(() => {
    if (!subjectId) return
    let cancelled = false
    setLoading(true)
    axios.get<Flow>('/api/conversation/flow', { params: { subject: subjectId, statement: statementN ?? undefined, lesson: lessonN ?? undefined } })
      .then((res) => {
        if (cancelled) return
        setFlow(res.data)
        const p = pendingPath.current ?? [{ node: res.data.start }]
        setPath(p); setSelectedId(p[p.length - 1].node)
        pendingPath.current = null
      })
      .catch((e) => !cancelled && setError(errorMessage(e, 'Could not load the flow')))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [subjectId, statementN, lessonN])

  const chooseSubject = (id: string | null) => {
    setSubjectId(id)
    setStatementN(sources?.subjects.find((x) => x.id === id)?.statements[0]?.n ?? null)
    setActiveId(null)
  }

  // ── Path ──
  const current = path[path.length - 1]
  const stepIndexOf = (id: string) => { const i = path.findIndex((s) => s.node === id); return i >= 0 ? i : null }
  const updateStep = (i: number, patch: Partial<Step>) => setPath((p) => p.map((s, k) => (k === i ? { ...s, ...patch } : s)))
  const walk = (from: string, kind: string) => {
    if (!flow) return
    const i = path.findIndex((s) => s.node === from)
    if (i < 0) return
    const r = flow.nodes[from].responses.find((x) => x.kind === kind)
    if (!r) return
    setPath((p) => [...p.slice(0, i), { ...p[i], response: kind }, { node: r.next }])
    setSelectedId(r.next)
  }
  const restart = () => { if (flow) { setPath([{ node: flow.start }]); setSelectedId(flow.start) } }
  const correctPhrase = (u: Phrase) => {
    setFlow((f) => f && ({ ...f, nodes: Object.fromEntries(Object.entries(f.nodes).map(([k, n]) => [k, {
      ...n, say: n.say.map((p) => (p.id === u.id ? u : p)), think: n.think.map((p) => (p.id === u.id ? u : p)),
      responses: n.responses.map((r) => ({ ...r, they: r.they.map((p) => (p.id === u.id ? u : p)) })),
    }])) }))
    setPath((p) => p.map((s) => (s.line?.id === u.id ? { ...s, line: u } : s)))
  }

  // ── Save / load ──
  const defaultTitle = () => (subject && flow?.statement ? `${subject.title.chk}: ${flow.statement.chk}` : subject?.title.chk || 'Conversation')
  const save = async () => {
    setSaving(true)
    try {
      const res = await axios.post('/api/conversations', { id: activeId || undefined, title: title.trim() || defaultTitle(), subject: subjectId, statement: statementN, lesson: lessonN, week: weekPart ? { part: weekPart.n, setting: weekPart.setting } : null, path })
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
      setActiveId(id); setTitle(doc.title || ''); setLessonN(doc.lesson ?? null)
      if (doc.subject === subjectId && doc.statement === statementN) { setPath(doc.path); setSelectedId(doc.path[doc.path.length - 1].node) }
      else { pendingPath.current = doc.path; setSubjectId(doc.subject); setStatementN(doc.statement) }
    } catch (e) {
      setError(errorMessage(e, 'Could not open the conversation'))
    }
  }
  const remove = async (id: string) => { await axios.delete(`/api/conversations/${id}`); if (activeId === id) setActiveId(null); loadSaved() }

  const transcript = useMemo(() => path.filter((s) => s.line || s.custom), [path])
  const selectedNode = flow && selectedId ? flow.nodes[selectedId] : null
  const selectedStepIndex = selectedId ? stepIndexOf(selectedId) : null

  if (!sources) return <Group justify="center" p="xl">{error ? <Alert color="red">{error}</Alert> : <Loader />}</Group>
  if (!sources.has_sources) {
    return <Alert color="yellow" title="Sources not harvested yet">Run <code>scripts/harvest_conversation_sources.py</code> once to pull Love People—Make Disciples and the meeting workbook from wol.jw.org.</Alert>
  }

  return (
    <div className={styles.page}>
      {/* ── Top bar ── */}
      <Group justify="space-between" mb="xs" wrap="wrap">
        <div>
          <Title order={2}><IconMessages size={26} style={{ verticalAlign: 'middle' }} /> Conversation Builder</Title>
          <Text c="dimmed" size="sm">Click a step to see what to say. Click an answer to follow it. Your path lights up.</Text>
        </div>
        <Group gap="xs">
          <Switch label="English" checked={showEnglish} onChange={(e) => setShowEnglish(e.currentTarget.checked)} />
          <Menu shadow="md" width={320}>
            <Menu.Target><Button variant="default" leftSection={<IconFolderOpen size={16} />}>My conversations{saved.length ? ` (${saved.length})` : ''}</Button></Menu.Target>
            <Menu.Dropdown>
              {saved.length === 0 && <Menu.Label>Nothing saved yet</Menu.Label>}
              {saved.map((s) => (
                <Menu.Item key={s.id} onClick={() => open(s.id)} rightSection={<ActionIcon size="sm" variant="subtle" color="red" onClick={(e) => { e.stopPropagation(); remove(s.id) }}><IconTrash size={14} /></ActionIcon>}>
                  <Text size="sm" lineClamp={2}>{s.title}</Text><Text size="xs" c="dimmed">{s.step_count} steps</Text>
                </Menu.Item>
              ))}
            </Menu.Dropdown>
          </Menu>
          <Button variant="default" leftSection={<IconPlus size={16} />} onClick={() => { restart(); setActiveId(null); setTitle('') }}>Start over</Button>
          <Button variant="light" leftSection={<IconPrinter size={16} />} onClick={() => window.print()}>Print</Button>
          <Button leftSection={<IconDeviceFloppy size={16} />} onClick={save} loading={saving}>{activeId ? 'Save changes' : 'Save'}</Button>
        </Group>
      </Group>

      <Card withBorder radius="md" p="xs" mb="xs">
        <Group gap="xs" wrap="wrap" align="flex-end">
          <Select label="Subject" data={sources.subjects.map((s) => ({ value: s.id, label: `${s.title.chk} · ${s.title.en}` }))} value={subjectId} onChange={chooseSubject} allowDeselect={false} w={260} />
          <Select label="Truth to share" data={(subject?.statements || []).map((st) => ({ value: String(st.n), label: `${st.n}. ${st.chk}` }))} value={statementN ? String(statementN) : null} onChange={(v) => { setStatementN(v ? Number(v) : null); setActiveId(null) }} allowDeselect={false} style={{ flex: 1, minWidth: 260 }} />
          {sources.current_week && (
            <Select label={`This week · ${sources.current_week.title.en}`} placeholder="Workbook part" clearable w={300}
              data={sources.current_week.parts.map((p) => ({ value: String(p.n), label: `${p.n}. ${p.title.chk}${p.refs.lmd ? ` (lesson ${p.refs.lmd.lesson})` : ''}` }))}
              value={weekPart ? String(weekPart.n) : null}
              onChange={(v) => { const p = sources.current_week!.parts.find((x) => String(x.n) === v) || null; setWeekPart(p); if (p?.refs.lmd) setLessonN(p.refs.lmd.lesson) }} />
          )}
          <Select label="Love People lesson" placeholder="Optional" clearable w={260} value={lessonN ? String(lessonN) : null} onChange={(v) => setLessonN(v ? Number(v) : null)}
            data={sources.lessons.map((l) => ({ value: String(l.number), label: `${l.number}. ${l.title.chk}` }))} />
          <TextInput label="Name" placeholder={defaultTitle()} value={title} onChange={(e) => setTitle(e.currentTarget.value)} w={240} />
        </Group>
        {flow?.statement && (
          <Group gap="md" mt="xs" wrap="wrap">
            <Text size="sm"><b>Truth:</b> {flow.statement.chk}{showEnglish ? <Text span c="dimmed"> — {flow.statement.en}</Text> : null}</Text>
            <Text size="sm" c="violet" fw={600}>{flow.statement.scriptures.chk}{showEnglish ? ` · ${flow.statement.scriptures.en}` : ''}</Text>
            {weekPart?.setting.chk && <Text size="sm"><b>Setting:</b> {weekPart.setting.chk}{showEnglish && weekPart.setting.en ? <Text span c="dimmed"> — {weekPart.setting.en}</Text> : null}</Text>}
          </Group>
        )}
      </Card>

      {error && <Alert color="red" mb="xs" withCloseButton onClose={() => setError('')}>{error}</Alert>}

      {/* ── Canvas + panel ── */}
      <div className={styles.work}>
        <div className={styles.canvas}>
          {loading && <Group justify="center" p="md" className={styles.canvasLoading}><Loader size="sm" /></Group>}
          {flow && (
            <ReactFlowProvider>
              <Canvas flow={flow} path={path} selectedId={selectedId} showEnglish={showEnglish} onSelect={setSelectedId} onEdge={walk} />
            </ReactFlowProvider>
          )}
          <Group gap="md" className={styles.legend}>
            {Object.entries(KIND_COLOR).slice(0, 5).map(([k, c]) => <Group key={k} gap={4}><span className={styles.swatch} style={{ background: c }} />{k}</Group>)}
            <Divider orientation="vertical" />
            {Object.entries(STAGE_COLOR).map(([k, c]) => <Group key={k} gap={4}><span className={styles.swatchSq} style={{ background: c }} />{k}</Group>)}
          </Group>
        </div>
        <ScrollArea className={styles.panel} type="auto">
          {selectedNode ? (
            <StepPanel node={selectedNode} step={selectedStepIndex !== null ? path[selectedStepIndex] : null} stepIndex={selectedStepIndex}
              isCurrent={!!current && current.node === selectedNode.id} showEnglish={showEnglish}
              onChoose={(p) => selectedStepIndex !== null && updateStep(selectedStepIndex, { line: p, custom: undefined })}
              onCustom={(line) => selectedStepIndex !== null && updateStep(selectedStepIndex, { custom: line, line: undefined })}
              onRespond={(kind) => walk(selectedNode.id, kind)} onCorrected={correctPhrase} />
          ) : <Text c="dimmed" size="sm">Click a step on the diagram.</Text>}
        </ScrollArea>
      </div>

      {/* ── Transcript ── */}
      {transcript.length > 0 && flow && (
        <Card withBorder radius="md" p="md" mt="xs" className={styles.transcript}>
          <Text fw={700} size="sm" mb={6}>Your conversation</Text>
          <Stack gap={6}>
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
        </Card>
      )}
    </div>
  )
}
