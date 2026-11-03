/**
 * Talk.tsx
 * Purpose: Talk Builder — assemble a talk in Chuukese on an outline, then deliver it.
 *
 * Paste or upload an outline (English or Chuukese). It is parsed into points
 * and sub-points with their scriptures and time marks. Under each point you
 * collect lines: typed here (translated either way), or sent from other
 * pages with "Add to talk". Scriptures are shown in both languages. Delivery
 * view shows one main point per screen in large type with a timer against
 * the outline's minutes. Talks are saved per user.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Accordion, ActionIcon, Alert, Anchor, Badge, Box, Button, Card, Divider, FileButton, Group, Loader, Modal, Paper, Progress,
  SegmentedControl, Stack, Switch, Text, TextInput, Textarea, Title, Tooltip,
} from '@mantine/core'
import {
  IconArrowDown, IconArrowUp, IconCheck, IconChevronLeft, IconChevronRight, IconDeviceFloppy, IconEdit, IconLanguage,
  IconPlayerPause, IconPlayerPlay, IconPlus, IconPresentation, IconPrinter, IconRefresh, IconSearch, IconTrash, IconUpload, IconX,
} from '@tabler/icons-react'
import axios from 'axios'
import { invalidateTalks } from '../components/AddToTalk'
import { ReferenceInline } from '../components/ReferenceView'
import { searchLink } from '../components/wolLinks'
import type { StoredReference } from '../components/ReferenceView'
import { GlossCard, GlossLegend, GlossedWords } from '../components/GlossedText'
import type { Dictionary, Gloss, SimilarMap } from '../components/GlossedText'
import type { PhraseMap } from '../components/glossUtils'
import styles from './Talk.module.css'

// ── Types ────────────────────────────────────────────────────────────────────

interface Reference { raw: string; kind: string }
interface Point { id: string; label: string; text: string; scriptures: string[]; references?: Reference[]; minutes: number | null; children?: Point[] }
interface Outline { title: string; number?: string; note?: string; theme_scripture: string; language: 'en' | 'chk'; points: Point[]; total_minutes: number | null }
interface Line { id: string; chk: string; en: string; source: string; ref: string; confirmed: boolean; note: string }
interface Talk { id: string; title: string; language: string; outline: Outline; outline_text?: string; lines: Record<string, Line[]>; line_count: number; updated_at?: string; scriptures?: (Verse & { ref: string })[]; references?: StoredReference[] }
interface TalkMeta { id: string; title: string; line_count: number; updated_at?: string; outline?: { title?: string; total_minutes?: number | null } }
interface Maps { dictionary: Dictionary; similar: SimilarMap; phrases: PhraseMap }
interface Verse { ref?: string; chuukese: string; english: string; error: string | null; maps?: Maps; source?: 'nwt' | 'liebenzell' | 'mixed' }
/** Hebrew Scriptures come from a different Chuukese translation; say so wherever they show. */
const LIEBENZELL = 'Liebenzell Paipel, not the New World Translation'
const SourceTag = ({ verse, size = 'xs' }: { verse: Verse; size?: string }) =>
  verse.source && verse.source !== 'nwt' ? <Badge size={size} color="orange" variant="light" ml={6}>{LIEBENZELL}</Badge> : null

const errorMessage = (e: unknown, fallback: string) =>
  (axios.isAxiosError(e) && (e.response?.data?.error as string)) || (e instanceof Error ? e.message : fallback)
const looksEnglish = (s: string) => [...s].every((c) => c.charCodeAt(0) < 128 || !/\p{L}/u.test(c))

async function machineTranslate(text: string, direction: 'en_to_chk' | 'chk_to_en'): Promise<string> {
  const res = await axios.post('/api/translate', { text, direction })
  const t = res.data?.translations || {}
  const pick = ['helsinki', 'madlad', 'model', 'google'].map((k) => (typeof t[k] === 'string' ? t[k] : t[k]?.text)).find((v) => typeof v === 'string' && v.trim() && !/error|not available|not configured/i.test(v))
  return pick ? String(pick).trim() : ''
}

const allPoints = (o: Outline | null): Point[] => (o?.points || []).flatMap((p) => [p, ...(p.children || [])])
/** A point's text with each citation rendered as a link to wol.jw.org. */
function TextWithCitations({ text, references, links }: { text: string; references?: Reference[]; links: Record<string, string> }) {
  const raws = (references || []).map((r) => r.raw).filter(Boolean)
  if (!raws.length) return <>{text}</>
  const parts: (string | Reference)[] = []
  let rest = text
  while (rest) {
    let best: { i: number; raw: string } | null = null
    for (const raw of raws) {
      const i = rest.indexOf(raw)
      if (i >= 0 && (!best || i < best.i)) best = { i, raw }
    }
    if (!best) { parts.push(rest); break }
    if (best.i > 0) parts.push(rest.slice(0, best.i))
    parts.push({ raw: best.raw, kind: '' })
    rest = rest.slice(best.i + best.raw.length)
  }
  return (
    <>
      {parts.map((part, i) => (typeof part === 'string' ? <span key={i}>{part}</span> : (
        <Anchor key={i} href={links[part.raw] || searchLink(part.raw)} target="_blank" rel="noopener noreferrer" c="violet" fw={700} inherit>{part.raw}</Anchor>
      )))}
    </>
  )
}

const allRefs = (o: Outline | null): string[] => Array.from(new Set([o?.theme_scripture || '', ...allPoints(o).flatMap((p) => p.scriptures)].filter(Boolean)))

// ── Alternatives for a line ──────────────────────────────────────────────────

interface Alternative { chk: string; en: string; source: 'wol' | 'library' | 'article' | 'conversation'; reference: string; link: string | null; score: number }
interface Alternatives { terms: string[]; items: Alternative[]; wol_reachable: boolean; wol_count: number; maps?: Maps; cached?: boolean }
const SOURCE_LABEL: Record<Alternative['source'], string> = { wol: 'wol.jw.org', library: 'library', article: 'analysed article', conversation: 'conversation' }

/** Published sentences close to the line, behind an accordion; searched when opened. */
function LineAlternatives({ line, showEnglish, onGloss, onUse, onAdd }: {
  line: Line; showEnglish: boolean; onGloss?: (g: Gloss | null) => void; onUse: (a: Alternative) => void; onAdd?: (a: Alternative) => void
}) {
  const [open, setOpen] = useState<string | null>(null)
  const [data, setData] = useState<Alternatives | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const load = async (refresh = false) => {
    if (!line.chk.trim()) return
    setLoading(true); setError('')
    try { const res = await axios.post<Alternatives>('/api/talks/alternatives', { chk: line.chk, refresh }); setData(res.data) } catch (e) { setError(errorMessage(e, 'Could not search')) } finally { setLoading(false) }
  }
  useEffect(() => { setData(null) }, [line.chk])
  useEffect(() => { if (open && !data && !loading) load() }, [open]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!line.chk.trim()) return null
  return (
    <Accordion value={open} onChange={setOpen} variant="separated" radius="md" mt={6} styles={{ control: { padding: '4px 8px' }, content: { padding: '4px 8px 8px' }, item: { background: 'var(--mantine-color-gray-0)' } }}>
      <Accordion.Item value="alt">
        <Accordion.Control icon={<IconSearch size={14} />}>
          <Group gap={6}><Text size="xs" fw={600}>Similar on wol.jw.org and in the library</Text>{data && <Badge size="xs" variant="light" color={data.items.length ? 'violet' : 'gray'}>{data.items.length}</Badge>}{loading && <Loader size={12} />}</Group>
        </Accordion.Control>
        <Accordion.Panel>
          {error && <Alert color="red" py={4}><Text size="xs">{error}</Text></Alert>}
          {data && (
            <Stack gap={6}>
              <Group gap={6} justify="space-between">
                <Text size="xs" c="dimmed">Searched for {data.terms.map((t) => <Badge key={t} size="xs" variant="outline" mr={4}>{t}</Badge>)}{!data.wol_reachable && <Text span c="orange"> · wol.jw.org did not answer; showing the library only</Text>}</Text>
                <Button size="compact-xs" variant="subtle" leftSection={<IconRefresh size={12} />} onClick={() => load(true)}>Search again</Button>
              </Group>
              {data.items.length === 0 && <Text size="xs" c="dimmed">Nothing close was found.</Text>}
              {data.items.map((a, i) => (
                <Paper key={i} withBorder p="xs" radius="sm">
                  <Group align="flex-start" wrap="nowrap" justify="space-between">
                    <Box style={{ flex: 1 }}>
                      <Text className={styles.chk}>{data.maps && onGloss ? <GlossedWords text={a.chk} dictionary={data.maps.dictionary} similar={data.maps.similar} phrases={data.maps.phrases} onGloss={onGloss} keyPrefix={`${line.id}-alt${i}-`} /> : a.chk}</Text>
                      {showEnglish && a.en && <Text size="sm" c="dimmed">{a.en}</Text>}
                      <Group gap={6} mt={2}>
                        <Badge size="xs" variant="light" color={a.source === 'wol' ? 'violet' : 'teal'}>{SOURCE_LABEL[a.source]}</Badge>
                        {a.reference && (a.link ? <Anchor size="xs" href={a.link} target="_blank" rel="noopener noreferrer">{a.reference}</Anchor> : <Text size="xs" c="dimmed">{a.reference}</Text>)}
                        <Text size="xs" c="dimmed">{Math.round(a.score * 100)}% of the words</Text>
                      </Group>
                    </Box>
                    <Group gap={4} wrap="nowrap">
                      <Tooltip label="Replace this line with it"><Button size="compact-xs" variant="light" onClick={() => onUse(a)}>Use</Button></Tooltip>
                      {onAdd && <Tooltip label="Add it as another line"><Button size="compact-xs" variant="default" onClick={() => onAdd(a)}>Add</Button></Tooltip>}
                    </Group>
                  </Group>
                </Paper>
              ))}
            </Stack>
          )}
        </Accordion.Panel>
      </Accordion.Item>
    </Accordion>
  )
}

// ── A collected line ────────────────────────────────────────────────────────

function LineCard({ line, showEnglish, onChange, onRemove, onMove, maps, onGloss, onAdd }: {
  line: Line; showEnglish: boolean; onChange: (l: Line) => void; onRemove: () => void; onMove: (d: -1 | 1) => void
  maps?: Maps | null; onGloss?: (g: Gloss | null) => void; onAdd?: (l: Omit<Line, 'id'>) => void
}) {
  const [editing, setEditing] = useState(false)
  const [chk, setChk] = useState(line.chk)
  const [en, setEn] = useState(line.en)
  const [suggesting, setSuggesting] = useState<'chk' | 'en' | null>(null)
  const timer = useRef<number | null>(null)

  const suggest = (side: 'chk' | 'en', text: string) => {
    if (timer.current) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(async () => {
      if (!text.trim()) return
      setSuggesting(side)
      try { const out = await machineTranslate(text.trim(), side === 'chk' ? 'en_to_chk' : 'chk_to_en'); if (out) (side === 'chk' ? setChk : setEn)(out) } finally { setSuggesting(null) }
    }, 900)
  }

  return (
    <Paper withBorder p="sm" radius="md" className={`${styles.line} ${line.confirmed ? styles.lineConfirmed : ''}`}>
      {editing ? (
        <Stack gap={6}>
          <Textarea autosize minRows={1} label="Chuukese" value={chk} onChange={(e) => { setChk(e.currentTarget.value); suggest('en', e.currentTarget.value) }} rightSection={suggesting === 'chk' ? <Loader size={14} /> : null} />
          <Textarea autosize minRows={1} label="English" value={en} onChange={(e) => { setEn(e.currentTarget.value); suggest('chk', e.currentTarget.value) }} rightSection={suggesting === 'en' ? <Loader size={14} /> : null} />
          <Group justify="flex-end" gap="xs">
            <Button size="xs" variant="default" leftSection={<IconX size={14} />} onClick={() => { setEditing(false); setChk(line.chk); setEn(line.en) }}>Cancel</Button>
            <Button size="xs" color="green" leftSection={<IconCheck size={14} />} onClick={() => { onChange({ ...line, chk: chk.trim(), en: en.trim(), confirmed: true }); setEditing(false) }}>Save</Button>
          </Group>
        </Stack>
      ) : (
        <Group align="flex-start" wrap="nowrap" justify="space-between">
          <Box style={{ flex: 1 }}>
            <Text className={styles.chk}>
              {line.chk ? (maps && onGloss ? <GlossedWords text={line.chk} dictionary={maps.dictionary} similar={maps.similar} phrases={maps.phrases} onGloss={onGloss} keyPrefix={`${line.id}-`} /> : line.chk) : <Text span c="dimmed" fs="italic">No Chuukese yet</Text>}
            </Text>
            {showEnglish && line.en && <Text size="sm" c="dimmed">{line.en}</Text>}
            <Group gap={6} mt={4}>
              <Badge size="xs" variant="light" color="violet">{line.source}</Badge>
              {line.ref && <Text size="xs" c="dimmed" lineClamp={1}>{line.ref}</Text>}
              {line.confirmed ? <Badge size="xs" variant="outline" color="green">checked</Badge> : <Badge size="xs" variant="outline" color="orange">unchecked</Badge>}
            </Group>
          </Box>
          <Group gap={2} wrap="nowrap">
            <Tooltip label={line.confirmed ? 'Mark unchecked' : 'Mark as checked'}><ActionIcon variant="subtle" color={line.confirmed ? 'green' : 'gray'} onClick={() => onChange({ ...line, confirmed: !line.confirmed })}><IconCheck size={16} /></ActionIcon></Tooltip>
            <ActionIcon variant="subtle" color="gray" onClick={() => { setChk(line.chk); setEn(line.en); setEditing(true) }}><IconEdit size={16} /></ActionIcon>
            <ActionIcon variant="subtle" color="gray" onClick={() => onMove(-1)}><IconArrowUp size={16} /></ActionIcon>
            <ActionIcon variant="subtle" color="gray" onClick={() => onMove(1)}><IconArrowDown size={16} /></ActionIcon>
            <ActionIcon variant="subtle" color="red" onClick={onRemove}><IconTrash size={16} /></ActionIcon>
          </Group>
        </Group>
      )}
      {!editing && (
        <LineAlternatives line={line} showEnglish={showEnglish} onGloss={onGloss}
          onUse={(a) => onChange({ ...line, chk: a.chk, en: a.en || line.en, source: a.source, ref: a.reference, confirmed: false })}
          onAdd={onAdd ? (a) => onAdd({ chk: a.chk, en: a.en, source: a.source, ref: a.reference, confirmed: false, note: '' }) : undefined} />
      )}
    </Paper>
  )
}

function AddLine({ onAdd, onGloss }: { onAdd: (l: Omit<Line, 'id'>) => void; onGloss?: (g: Gloss | null) => void }) {
  const [previewMaps, setPreviewMaps] = useState<Maps | null>(null)
  const [text, setText] = useState('')
  const [out, setOut] = useState<{ chk: string; en: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const translate = async () => {
    if (!text.trim()) return
    setBusy(true)
    try {
      const en = looksEnglish(text)
      const t = await machineTranslate(text.trim(), en ? 'en_to_chk' : 'chk_to_en')
      const next = en ? { en: text.trim(), chk: t } : { chk: text.trim(), en: t }
      setOut(next)
      if (next.chk) axios.post<Maps>('/api/talks/gloss', { texts: [next.chk] }).then((r) => setPreviewMaps(r.data)).catch(() => setPreviewMaps(null))
    } finally { setBusy(false) }
  }
  return (
    <Box mt="xs">
      <Group gap="xs" align="flex-start">
        <TextInput placeholder="Type a line in English or Chuukese" value={text} onChange={(e) => setText(e.currentTarget.value)} style={{ flex: 1 }} onKeyDown={(e) => e.key === 'Enter' && translate()} />
        <Button variant="light" leftSection={<IconLanguage size={16} />} onClick={translate} loading={busy}>Translate</Button>
      </Group>
      {out && (
        <Paper withBorder p="sm" mt="xs" radius="md">
          <Text className={styles.chk}>{out.chk ? (previewMaps && onGloss ? <GlossedWords text={out.chk} dictionary={previewMaps.dictionary} similar={previewMaps.similar} phrases={previewMaps.phrases} onGloss={onGloss} keyPrefix="preview-" /> : out.chk) : <Text span c="dimmed" fs="italic">No translation</Text>}</Text>
          <Text size="sm" c="dimmed">{out.en}</Text>
          <Group justify="flex-end" mt={4} gap="xs">
            <Button size="xs" variant="default" onClick={() => setOut(null)}>Discard</Button>
            <Button size="xs" leftSection={<IconPlus size={14} />} onClick={() => { onAdd({ ...out, source: 'typed', ref: '', confirmed: false, note: '' }); setOut(null); setText('') }}>Add under this point</Button>
          </Group>
        </Paper>
      )}
    </Box>
  )
}

// ── Verse box ───────────────────────────────────────────────────────────────

function VerseBox({ cite, verse, showEnglish, onGloss }: { cite: string; verse?: Verse; showEnglish: boolean; onGloss?: (g: Gloss | null) => void }) {
  return (
    <Box className={styles.verse} mt={6}>
      <Group gap={4}><Text size="xs" fw={700} c="violet">{cite}</Text>{verse && <SourceTag verse={verse} />}</Group>
      {!verse ? <Text size="xs" c="dimmed">Loading…</Text> : (
        <>
          {verse.chuukese && (
            <Text className={styles.verseChk}>
              {verse.maps && onGloss ? <GlossedWords text={verse.chuukese} dictionary={verse.maps.dictionary} similar={verse.maps.similar} phrases={verse.maps.phrases} onGloss={onGloss} keyPrefix={`${cite}-`} /> : verse.chuukese}
            </Text>
          )}
          {showEnglish && verse.english && <Text size="sm" c="dimmed">{verse.english}</Text>}
          {!verse.chuukese && !verse.english && <Text size="xs" c="orange">{verse.error || 'Verse not available'}</Text>}
        </>
      )}
    </Box>
  )
}

// ── Delivery view ───────────────────────────────────────────────────────────

function Deliver({ talk, verses, showEnglish: initialEnglish, onClose }: { talk: Talk; verses: Record<string, Verse>; showEnglish: boolean; onClose: () => void }) {
  const [i, setI] = useState(0)
  const [showEnglish, setShowEnglish] = useState(initialEnglish)
  const [running, setRunning] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const points = talk.outline.points
  const point = points[i]
  useEffect(() => { if (!running) return; const t = window.setInterval(() => setElapsed((e) => e + 1), 1000); return () => window.clearInterval(t) }, [running])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'ArrowRight' || e.key === ' ') setI((x) => Math.min(points.length - 1, x + 1)); if (e.key === 'ArrowLeft') setI((x) => Math.max(0, x - 1)); if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey)
  }, [points.length, onClose])
  const plannedUntil = points.slice(0, i + 1).reduce((n, p) => n + (p.minutes || 0), 0) * 60
  const total = (talk.outline.total_minutes || 0) * 60
  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  if (!point) return null
  const block = (p: Point) => (
    <Box key={p.id}>
      {p.scriptures.map((c) => verses[c] && (
        <Box key={c} className={styles.deliverVerse}>
          <Group gap={4}><Text size="sm" fw={700} c="violet">{c}</Text><SourceTag verse={verses[c]} size="sm" /></Group>
          <div>{verses[c].chuukese || verses[c].english}</div>
          {showEnglish && verses[c].chuukese && <Text c="dimmed" size="md">{verses[c].english}</Text>}
        </Box>
      ))}
      {(talk.lines[p.id] || []).map((l) => (
        <Box key={l.id}>
          <div className={styles.deliverLine}>{l.chk || l.en}</div>
          {showEnglish && l.chk && <div className={styles.deliverEn}>{l.en}</div>}
        </Box>
      ))}
    </Box>
  )
  return (
    <div className={styles.deliver}>
      <div className={styles.deliverHead}>
        <Group gap="sm">
          <Button variant="default" leftSection={<IconChevronLeft size={16} />} onClick={() => setI((x) => Math.max(0, x - 1))} disabled={i === 0}>Back</Button>
          <Text fw={700}>{i + 1} / {points.length}</Text>
          <Button variant="default" rightSection={<IconChevronRight size={16} />} onClick={() => setI((x) => Math.min(points.length - 1, x + 1))} disabled={i === points.length - 1}>Next</Button>
        </Group>
        <Group gap="sm">
          <Text className={`${styles.timer} ${total && elapsed > plannedUntil ? styles.timerOver : ''}`}>{fmt(elapsed)}{point.minutes ? ` / ${fmt(plannedUntil)}` : ''}{total ? ` · ${fmt(total)} total` : ''}</Text>
          <ActionIcon variant="light" onClick={() => setRunning((r) => !r)}>{running ? <IconPlayerPause size={18} /> : <IconPlayerPlay size={18} />}</ActionIcon>
          <ActionIcon variant="subtle" onClick={() => { setElapsed(0); setRunning(false) }}><IconRefresh size={18} /></ActionIcon>
          <Switch label="English" checked={showEnglish} onChange={(e) => setShowEnglish(e.currentTarget.checked)} />
          <Button variant="default" leftSection={<IconX size={16} />} onClick={onClose}>Exit</Button>
        </Group>
      </div>
      <div className={styles.deliverTitle}>{point.label ? `${point.label}. ` : ''}{point.text}{point.minutes ? <Text span c="dimmed" fw={400} size="lg"> ({point.minutes} min.)</Text> : null}</div>
      {block(point)}
      {(point.children || []).map((c) => (
        <Box key={c.id}>
          <div className={styles.deliverSub}>{c.label ? `${c.label}. ` : '· '}{c.text}</div>
          {block(c)}
        </Box>
      ))}
      {i === 0 && talk.outline.theme_scripture && verses[talk.outline.theme_scripture] && (
        <Box className={styles.deliverVerse}><Group gap={4}><Text size="sm" fw={700} c="violet">Theme · {talk.outline.theme_scripture}</Text><SourceTag verse={verses[talk.outline.theme_scripture]} size="sm" /></Group><div>{verses[talk.outline.theme_scripture].chuukese}</div></Box>
      )}
    </div>
  )
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function TalkBuilder() {
  const [talks, setTalks] = useState<TalkMeta[]>([])
  const [talk, setTalk] = useState<Talk | null>(null)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [showEnglish, setShowEnglish] = useState(true)
  const [verses, setVerses] = useState<Record<string, Verse>>({})
  const [delivering, setDelivering] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [importText, setImportText] = useState('')
  const [importLang, setImportLang] = useState<'auto' | 'en' | 'chk'>('auto')
  const [preview, setPreview] = useState<Outline | null>(null)
  const [parsing, setParsing] = useState(false)
  const [editOutline, setEditOutline] = useState(false)
  const [gloss, setGloss] = useState<Gloss | null>(null)
  // Citation → article URL (with WOL's highlight anchor) once a reference has resolved.
  const [refLinks, setRefLinks] = useState<Record<string, string>>({})
  const [lineMaps, setLineMaps] = useState<Maps | null>(null)
  const lineTexts = useMemo(() => Array.from(new Set(Object.values(talk?.lines || {}).flat().map((l) => l.chk).filter(Boolean))).sort().join('\n'), [talk?.lines])
  useEffect(() => {
    if (!lineTexts) { setLineMaps(null); return }
    let cancelled = false
    const t = window.setTimeout(() => {
      axios.post<Maps>('/api/talks/gloss', { texts: lineTexts.split('\n') }).then((r) => !cancelled && setLineMaps(r.data)).catch(() => undefined)
    }, 400)
    return () => { cancelled = true; window.clearTimeout(t) }
  }, [lineTexts])

  const loadTalks = useCallback(async () => { try { setTalks((await axios.get('/api/talks')).data) } catch { /* list only */ } }, [])
  useEffect(() => { loadTalks() }, [loadTalks])

  // Scriptures for the open talk, in both languages, fetched once per set of citations.
  const refs = useMemo(() => allRefs(talk?.outline || null), [talk?.outline])
  useEffect(() => {
    const missing = refs.filter((r) => !verses[r])
    if (!missing.length || !talk) return
    axios.post('/api/talks/scriptures', { refs: missing, talk_id: talk.id }).then((r) => setVerses((v) => ({ ...v, ...r.data }))).catch(() => undefined)
  }, [refs, verses, talk])

  const open = async (id: string) => {
    try {
      const doc: Talk = (await axios.get(`/api/talks/${id}`)).data
      // Verses stored with the talk show at once; nothing is fetched again.
      setVerses((v) => ({ ...v, ...Object.fromEntries((doc.scriptures || []).filter((s) => s.chuukese).map((s) => [s.ref, s])) }))
      setTalk(doc); setDirty(false); setEditOutline(false)
    } catch (e) { setError(errorMessage(e, 'Could not open the talk')) }
  }
  const save = async () => {
    if (!talk) return
    setSaving(true)
    try {
      await axios.put(`/api/talks/${talk.id}`, { title: talk.title, language: talk.language, outline: talk.outline, outline_text: talk.outline_text, lines: talk.lines })
      setDirty(false); await loadTalks()
    } catch (e) { setError(errorMessage(e, 'Could not save')) } finally { setSaving(false) }
  }
  const remove = async (id: string) => {
    await axios.delete(`/api/talks/${id}`); invalidateTalks()
    if (talk?.id === id) setTalk(null)
    loadTalks()
  }

  // ── Import ──
  const parse = async (file?: File | null) => {
    setParsing(true)
    try {
      let res
      if (file) {
        const fd = new FormData(); fd.append('file', file); if (importLang !== 'auto') fd.append('language', importLang)
        res = await axios.post('/api/talks/parse-outline', fd)
        setImportText(res.data.text || '')
      } else {
        res = await axios.post('/api/talks/parse-outline', { text: importText, language: importLang === 'auto' ? undefined : importLang })
      }
      setPreview(res.data.outline)
    } catch (e) { setError(errorMessage(e, 'Could not read the outline')) } finally { setParsing(false) }
  }
  const createFromPreview = async () => {
    if (!preview) return
    try {
      const res = await axios.post('/api/talks', { title: preview.title || 'Talk', language: preview.language, outline: preview, outline_text: importText, lines: {} })
      invalidateTalks(); setImportOpen(false); setPreview(null); setImportText('')
      await loadTalks(); await open(res.data.id)
    } catch (e) { setError(errorMessage(e, 'Could not create the talk')) }
  }

  // ── Line edits ──
  const mutate = (fn: (t: Talk) => Talk) => { setTalk((t) => (t ? fn(t) : t)); setDirty(true) }
  const setLines = (pid: string, rows: Line[]) => mutate((t) => ({ ...t, lines: { ...t.lines, [pid]: rows } }))
  const addLine = (pid: string, l: Omit<Line, 'id'>) => setLines(pid, [...(talk?.lines[pid] || []), { ...l, id: Math.random().toString(36).slice(2, 12) }])
  const moveLine = (pid: string, idx: number, d: -1 | 1) => {
    const rows = [...(talk?.lines[pid] || [])]; const j = idx + d
    if (j < 0 || j >= rows.length) return
    ;[rows[idx], rows[j]] = [rows[j], rows[idx]]; setLines(pid, rows)
  }
  const moveLineTo = (fromPid: string, idx: number, toPid: string) => {
    if (!talk) return
    const from = [...(talk.lines[fromPid] || [])]; const [l] = from.splice(idx, 1)
    mutate((t) => ({ ...t, lines: { ...t.lines, [fromPid]: from, [toPid]: [...(t.lines[toPid] || []), l] } }))
  }
  const updatePoint = (pid: string, patch: Partial<Point>) => mutate((t) => ({
    ...t, outline: { ...t.outline, points: t.outline.points.map((p) => (p.id === pid ? { ...p, ...patch } : { ...p, children: (p.children || []).map((c) => (c.id === pid ? { ...c, ...patch } : c)) })) },
  }))

  const points = allPoints(talk?.outline || null)
  const covered = points.filter((p) => (talk?.lines[p.id] || []).length > 0).length
  const unsorted = talk?.lines['unsorted'] || []

  const sections = talk?.outline.points || []
  const renderPoint = (p: Point, child = false) => {
    const rows = talk?.lines[p.id] || []
    const childLines = (p.children || []).reduce((n, c) => n + (talk?.lines[c.id] || []).length, 0)
    const sectionIndex = sections.findIndex((s) => s.id === p.id)
    const head = child ? (
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Group gap="sm" align="flex-start" wrap="nowrap" style={{ flex: 1 }}>
            {p.label && <Text className={styles.pointLabel}>{p.label}.</Text>}
            {editOutline ? (
              <TextInput value={p.text} onChange={(e) => updatePoint(p.id, { text: e.currentTarget.value })} style={{ flex: 1 }} />
            ) : <Text className={styles.pointTitle}><TextWithCitations text={p.text} references={p.references} links={refLinks} /></Text>}
          </Group>
          <Group gap="xs">
            {editOutline ? <TextInput w={80} type="number" placeholder="min" value={p.minutes ?? ''} onChange={(e) => updatePoint(p.id, { minutes: e.currentTarget.value ? Number(e.currentTarget.value) : null })} /> : p.minutes ? <Badge size="lg" variant="filled" color="violet">{p.minutes} min</Badge> : null}
            <Badge variant={rows.length ? 'light' : 'outline'} color={rows.length ? 'green' : 'orange'}>{rows.length} line{rows.length === 1 ? '' : 's'}</Badge>
          </Group>
        </Group>
    ) : (
        <div className={styles.sectionHead}>
          <Group gap="sm" align="center" wrap="nowrap" style={{ flex: 1, minWidth: 0 }}>
            <Text className={styles.sectionNum}>{p.label ? `${p.label}.` : sectionIndex + 1}</Text>
            <Box style={{ flex: 1, minWidth: 0 }}>
              <Text className={styles.sectionCount}>Section {sectionIndex + 1} of {sections.length}</Text>
              {editOutline ? (
                <TextInput value={p.text} onChange={(e) => updatePoint(p.id, { text: e.currentTarget.value })} />
              ) : <Text className={styles.sectionTitle}><TextWithCitations text={p.text} references={p.references} links={refLinks} /></Text>}
            </Box>
          </Group>
          <div className={styles.sectionMeta}>
            <Text className={styles.sectionLines}>{rows.length + childLines} line{rows.length + childLines === 1 ? '' : 's'}</Text>
            {editOutline ? <TextInput w={80} type="number" placeholder="min" value={p.minutes ?? ''} onChange={(e) => updatePoint(p.id, { minutes: e.currentTarget.value ? Number(e.currentTarget.value) : null })} /> : <span className={styles.sectionTime}>{p.minutes ? `${p.minutes} min` : 'no time'}</span>}
          </div>
        </div>
    )
    const body = (
      <>
        {(p.references || []).map((r) => (
          <ReferenceInline key={`${talk?.id}-${p.id}-${r.raw}`} reference={r.raw} context={p.text} talkId={talk?.id} showEnglish={showEnglish} onGloss={setGloss}
            onResolved={(raw, d) => { const link = d.links.en || d.links.search; if (link) setRefLinks((m) => (m[raw] === link ? m : { ...m, [raw]: link })) }}
            stored={(talk?.references || []).find((s) => s.key.ref === r.raw.toLowerCase() && s.key.context === p.text.toLowerCase().slice(0, 300) && s.result.paragraphs.length > 0)?.result} />
        ))}
        {p.scriptures.map((c) => <VerseBox key={c} cite={c} verse={verses[c]} showEnglish={showEnglish} onGloss={setGloss} />)}
        <Stack gap="xs" mt="sm">
          {rows.map((l, i) => (
            <Group key={l.id} align="stretch" gap={4} wrap="nowrap">
              <Box style={{ flex: 1 }}>
                <LineCard line={l} showEnglish={showEnglish} maps={lineMaps} onGloss={setGloss} onChange={(nl) => setLines(p.id, rows.map((x) => (x.id === nl.id ? nl : x)))} onRemove={() => setLines(p.id, rows.filter((x) => x.id !== l.id))} onMove={(d) => moveLine(p.id, i, d)} onAdd={(nl) => addLine(p.id, nl)} />
              </Box>
            </Group>
          ))}
        </Stack>
        <AddLine onAdd={(l) => addLine(p.id, l)} onGloss={setGloss} />
        {(p.children || []).length > 0 && <Stack gap="sm" mt="sm">{p.children!.map((c) => renderPoint(c, true))}</Stack>}
      </>
    )
    if (child) {
      return (
        <Card key={p.id} withBorder radius="md" p="md" className={`${styles.child} ${styles.point} ${rows.length === 0 ? styles.pointEmpty : ''}`}>
          {head}
          {body}
        </Card>
      )
    }
    return (
      <section key={p.id} className={`${styles.section} ${rows.length + childLines === 0 ? styles.sectionEmpty : ''}`}>
        {head}
        <div className={styles.sectionBody}>{body}</div>
      </section>
    )
  }

  return (
    <div className={styles.page}>
      <Group justify="space-between" mb="md" wrap="wrap">
        <div>
          <Title order={2}><IconPresentation size={26} style={{ verticalAlign: 'middle' }} /> Talk Builder</Title>
          <Text c="dimmed" size="sm">Bring in an outline, collect Chuukese lines under each point as you find them, then deliver from the large-type view.</Text>
        </div>
        <Group gap="xs">
          {talk && <GlossLegend />}
          <Switch label="English" checked={showEnglish} onChange={(e) => setShowEnglish(e.currentTarget.checked)} />
          <Button variant="default" leftSection={<IconUpload size={16} />} onClick={() => setImportOpen(true)}>New talk from outline</Button>
          {talk && <Button variant="light" leftSection={<IconPrinter size={16} />} onClick={() => window.print()}>Print</Button>}
          {talk && <Button color="violet" leftSection={<IconPresentation size={16} />} onClick={() => setDelivering(true)}>Deliver</Button>}
          {talk && <Button leftSection={<IconDeviceFloppy size={16} />} onClick={save} loading={saving} disabled={!dirty}>{dirty ? 'Save' : 'Saved'}</Button>}
        </Group>
      </Group>
      {error && <Alert color="red" mb="md" withCloseButton onClose={() => setError('')}>{error}</Alert>}

      <div className={styles.layout}>
        <Card withBorder radius="md" p="sm" className={styles.side}>
          <Text fw={700} size="sm" mb={6}>My talks</Text>
          {talks.length === 0 && <Text size="xs" c="dimmed">No talks yet. Start with an outline.</Text>}
          <Stack gap={2}>
            {talks.map((t) => (
              <Group key={t.id} justify="space-between" wrap="nowrap" className={`${styles.talkRow} ${talk?.id === t.id ? styles.talkRowActive : ''}`} onClick={() => open(t.id)}>
                <Box style={{ flex: 1, minWidth: 0 }}>
                  <Text size="sm" fw={600} lineClamp={2}>{t.title}</Text>
                  <Text size="xs" c="dimmed">{t.line_count} lines{t.outline?.total_minutes ? ` · ${t.outline.total_minutes} min` : ''}</Text>
                </Box>
                <ActionIcon size="sm" variant="subtle" color="red" onClick={(e) => { e.stopPropagation(); remove(t.id) }}><IconTrash size={14} /></ActionIcon>
              </Group>
            ))}
          </Stack>
        </Card>

        <Box>
          {!talk ? (
            <Alert color="violet" title="Pick a talk or bring in an outline">
              Paste an outline or upload a .txt, .docx or .pdf. Then, on any page where you meet a good sentence, use <b>Add to talk</b> to file it under a point.
            </Alert>
          ) : (
            <>
              <Card withBorder radius="md" p="md" mb="sm">
                <Group justify="space-between" wrap="wrap" align="flex-start">
                  <Box style={{ flex: 1, minWidth: 260 }}>
                    {editOutline ? <TextInput label="Title" value={talk.title} onChange={(e) => mutate((t) => ({ ...t, title: e.currentTarget.value }))} /> : <Group gap="sm" align="baseline">{talk.outline.number && <Badge variant="outline" color="gray">{talk.outline.number}</Badge>}<Title order={3}>{talk.title}</Title></Group>}
                    {talk.outline.note && <Text className={styles.note}>{talk.outline.note}</Text>}
                    {talk.outline.theme_scripture && <Text c="violet" fw={600} mt={4}>Theme: {talk.outline.theme_scripture}</Text>}
                    {talk.outline.theme_scripture && verses[talk.outline.theme_scripture] && <VerseBox cite={talk.outline.theme_scripture} verse={verses[talk.outline.theme_scripture]} showEnglish={showEnglish} onGloss={setGloss} />}
                  </Box>
                  <Stack gap={4} align="flex-end">
                    <Group gap="xs">
                      <Badge variant="light">{talk.outline.language === 'chk' ? 'Chuukese outline' : 'English outline'}</Badge>
                      {talk.outline.total_minutes && <Badge size="lg" variant="filled" color="violet">{talk.outline.total_minutes} min</Badge>}
                      <Button size="xs" variant={editOutline ? 'filled' : 'default'} leftSection={<IconEdit size={14} />} onClick={() => setEditOutline((e) => !e)}>{editOutline ? 'Done editing outline' : 'Edit outline'}</Button>
                    </Group>
                    <Box w={260}>
                      <Text size="xs" c="dimmed">{covered} of {points.length} points have lines</Text>
                      <Progress value={points.length ? (covered / points.length) * 100 : 0} color={covered === points.length ? 'green' : 'violet'} />
                    </Box>
                  </Stack>
                </Group>
              </Card>

              {unsorted.length > 0 && (
                <Card withBorder radius="md" p="md" mb="sm" style={{ borderColor: 'var(--mantine-color-orange-4)' }}>
                  <Text fw={700} mb={4}>Unsorted lines · drag-free: pick a point for each</Text>
                  <Stack gap="xs">
                    {unsorted.map((l, i) => (
                      <Group key={l.id} align="flex-start" wrap="nowrap">
                        <Box style={{ flex: 1 }}><LineCard line={l} showEnglish={showEnglish} maps={lineMaps} onGloss={setGloss} onChange={(nl) => setLines('unsorted', unsorted.map((x) => (x.id === nl.id ? nl : x)))} onRemove={() => setLines('unsorted', unsorted.filter((x) => x.id !== l.id))} onMove={(d) => moveLine('unsorted', i, d)} /></Box>
                        <select className="mantine-Input-input" style={{ maxWidth: 220 }} defaultValue="" onChange={(e) => e.target.value && moveLineTo('unsorted', i, e.target.value)}>
                          <option value="">Move under…</option>
                          {points.map((p) => <option key={p.id} value={p.id}>{p.label ? `${p.label}. ` : ''}{p.text.slice(0, 50)}</option>)}
                        </select>
                      </Group>
                    ))}
                  </Stack>
                </Card>
              )}

              {talk.outline.points.map((p) => renderPoint(p))}
              {talk.outline.points.length === 0 && <Alert color="yellow">This talk has no outline points yet. Use Edit outline, or create a new talk from an outline.</Alert>}
            </>
          )}
        </Box>
      </div>

      {gloss && <GlossCard gloss={gloss} />}
      {delivering && talk && <Deliver talk={talk} verses={verses} showEnglish={showEnglish} onClose={() => setDelivering(false)} />}

      <Modal opened={importOpen} onClose={() => { setImportOpen(false); setPreview(null) }} title="New talk from an outline" size="xl">
        <Stack gap="sm">
          <Group gap="sm">
            <SegmentedControl value={importLang} onChange={(v) => setImportLang(v as 'auto' | 'en' | 'chk')} data={[{ label: 'Detect language', value: 'auto' }, { label: 'English', value: 'en' }, { label: 'Chuukese', value: 'chk' }]} />
            <FileButton onChange={(f) => parse(f)} accept=".txt,.docx,.pdf,.md">{(props) => <Button {...props} variant="default" leftSection={<IconUpload size={16} />} loading={parsing}>Upload .txt / .docx / .pdf</Button>}</FileButton>
          </Group>
          <Textarea autosize minRows={8} maxRows={18} placeholder={'Paste the outline. Example:\nWhy Trust the Bible? (Ps. 119:105)\n1. The Bible claims to be from God (5 min.)\n   a. 2 Tim. 3:16, 17\n2. The Bible is accurate (8 min.)'} value={importText} onChange={(e) => setImportText(e.currentTarget.value)} />
          <Group justify="flex-end"><Button variant="light" onClick={() => parse()} loading={parsing} disabled={!importText.trim()}>Parse outline</Button></Group>
          {preview && (
            <Paper withBorder p="sm" radius="md">
              <Text fw={700}>{preview.title || '(no title)'} <Badge ml="xs" variant="light">{preview.language === 'chk' ? 'Chuukese' : 'English'}</Badge>{preview.total_minutes ? <Badge ml="xs" variant="light" color="gray">{preview.total_minutes} min</Badge> : null}</Text>
              {preview.theme_scripture && <Text size="sm" c="violet">Theme: {preview.theme_scripture}</Text>}
              <Divider my="xs" />
              {preview.points.map((p) => (
                <Box key={p.id} mb={4}>
                  <Text size="sm"><b>{p.label ? `${p.label}. ` : ''}</b>{p.text}{p.minutes ? <Text span c="dimmed"> ({p.minutes} min)</Text> : null}{p.scriptures.length ? <Text span c="violet"> · {p.scriptures.join('; ')}</Text> : null}{(p.references || []).length ? <Text span c="grape"> · {p.references!.map((r) => r.raw).join('; ')}</Text> : null}</Text>
                  {(p.children || []).map((c) => <Text key={c.id} size="sm" pl="lg" c="dimmed">{c.label ? `${c.label}. ` : '· '}{c.text}{c.scriptures.length ? <Text span c="violet"> · {c.scriptures.join('; ')}</Text> : null}</Text>)}
                </Box>
              ))}
              <Group justify="flex-end" mt="sm"><Button onClick={createFromPreview} leftSection={<IconPlus size={16} />}>Create talk</Button></Group>
            </Paper>
          )}
        </Stack>
      </Modal>
    </div>
  )
}
