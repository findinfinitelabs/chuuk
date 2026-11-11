/**
 * VerbLookup.tsx
 * Purpose: look up any Chuukese verb and see it with every subject pronoun
 * (seven persons × seven tense markers), every object suffix (me, you, him,
 * us, you all, them), the other forms built on it, and real examples in
 * which a subject marker stands before the verb.
 *
 * Stored data only on load. wol.jw.org is searched only from the button.
 */

import { useEffect, useMemo, useState } from 'react'
import { ActionIcon, Alert, Anchor, Badge, Button, Card, Chip, Group, Loader, Modal, SegmentedControl, Stack, Table, Text, TextInput, Textarea, Title, Tooltip } from '@mantine/core'
import { IconAbc, IconCheck, IconSearch, IconSparkles, IconWorld } from '@tabler/icons-react'
import axios from 'axios'
import { useSearchParams } from 'react-router-dom'
import AddToTalk from '../components/AddToTalk'
import styles from './VerbLookup.module.css'

interface Cell { tense: string; marker: string; chuukese: string }
interface SubjectRow { person: string; english: string; pronoun: string; cells: Cell[] }
interface ObjectForm { object: string; english: string; suffix: string; form: string; attested: boolean; gloss: string; alternatives: string[] }
interface OtherForm { form: string; english: string; modifier: string; grammar: string }
interface Example { chk: string; en: string; source: string; reference: string; marker: string; aspect: string; form: string; person: string; tense: string; start: number; end: number }
interface Lookup {
  matches: { chuukese: string; english: string; grammar: string }[]
  query: string; found: boolean; verb: string; english: string; grammar: string; modifier: string; definition: string
  persons: { id: string; english: string; pronoun: string }[]
  tenses: { id: string; label: string; gloss: string }[]
  aspects: { word: string; english: string }[]
  subjects: SubjectRow[]; objects: ObjectForm[]; other_forms: OtherForm[]; examples: Example[]
}
interface WolHit { text: string; title?: string; link?: string; citation?: string; segments: { text: string; match: boolean }[]; subject?: { subject: string; marker: string; tense?: string } | null }

const errorMessage = (e: unknown, fallback: string) => (axios.isAxiosError(e) && e.response?.data?.error) || fallback

/** The English for one cell: the tense gloss with the subject and the verb's
 *  base meaning filled in, e.g. "I will help you". */
function gloss(tenseGloss: string, subject: string, verb: string) {
  return tenseGloss.replace('{s}', subject).replace('{v}', verb)
}

const baseVerb = (english: string) => (english || '').replace(/^to\s+/i, '').split(/[;,(]/)[0].trim()

const STOP = new Set(['to', 'be', 'a', 'an', 'the', 'of', 'in', 'on', 'for', 'with', 'about', 'at', 'or', 'and', 'up', 'out', 'sg', 'pl', 'incl', 'excl', 'me', 'you', 'him', 'her', 'it', 'us', 'them', 'one', 'someone', 'something'])

/** A regex that finds the verb's English in a sentence in any common form:
 *  "help" matches helped, helps, helping; "love" matches loved, loving;
 *  "carry" matches carries, carried. Built from every meaning the
 *  dictionary gives for the verb and its object forms. */
function englishPattern(meanings: string[]): RegExp | null {
  const stems = new Set<string>()
  for (const m of meanings) {
    for (const part of (m || '').toLowerCase().split(/[;,/()]/)) {
      for (const w of part.replace(/^to\s+/, '').split(/[^a-z']+/)) {
        if (w.length >= 3 && !STOP.has(w)) stems.add(w)
      }
    }
  }
  if (!stems.size) return null
  const alts = [...stems].map((w) => {
    const e = w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    if (w.endsWith('y')) return `${e.slice(0, -1)}(?:y|ies|ied|ying)`
    if (w.endsWith('e')) return `${e.slice(0, -1)}(?:e|es|ed|ing)`
    return `${e}(?:s|es|ed|ing|${w.slice(-1)}ed|${w.slice(-1)}ing)?`
  })
  return new RegExp(`\\b(?:${alts.join('|')})\\b`, 'i')
}

/** Translate one way with the site's engines (Google first on the hosted site). */
async function machineTranslate(text: string, direction: 'en_to_chk' | 'chk_to_en'): Promise<string> {
  const res = await axios.post('/api/translate', { text, direction })
  const t = res.data?.translations || {}
  const order = [res.data?.preferred === 'google' ? 'google' : 'helsinki', 'helsinki', 'madlad', 'model', 'google']
  const pick = order.map((k) => (typeof t[k] === 'string' ? t[k] : t[k]?.text)).find((v) => typeof v === 'string' && v.trim() && !/error|not available|not configured/i.test(v))
  return pick ? String(pick).trim() : ''
}

const normChk = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()

interface Seed { clause: string; marker: string; form: string; en: string; person: string; tense: string }

/** Make a sentence from a table cell: an English sentence is written from the
 *  cell's gloss, translated by the site's engines, and shown with the
 *  Chuukese editable so the clause can be put right before it is saved as a
 *  verified pair or added to a talk. Stored examples with the same pronoun,
 *  tense and form are listed first, since a real sentence beats a generated one. */
function SentenceModal({ seed, examples, onClose }: { seed: Seed | null; examples: Example[]; onClose: () => void }) {
  const [en, setEn] = useState('')
  const [chk, setChk] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  useEffect(() => {
    if (!seed) return
    const first = seed.en.charAt(0).toUpperCase() + seed.en.slice(1)
    setEn(`${first}.`); setChk(''); setError(null); setSaved(false)
  }, [seed])
  if (!seed) return null
  const same = examples.filter((e) => e.person === seed.person && e.tense === seed.tense && normChk(e.form) === normChk(seed.form))
  const usesClause = chk && normChk(chk).includes(normChk(seed.clause))
  const generate = async () => {
    setBusy(true); setError(null); setSaved(false)
    try {
      const out = await machineTranslate(en.trim(), 'en_to_chk')
      if (!out) setError('No translation came back')
      setChk(out)
    } catch (e) { setError(errorMessage(e, 'Translation failed')) } finally { setBusy(false) }
  }
  const save = async () => {
    try { await axios.post('/api/pairs/verified', { chk: chk.trim(), en: en.trim(), source: 'verb_lookup', reference: seed.clause }); setSaved(true) } catch (e) { setError(errorMessage(e, 'Could not save')) }
  }
  return (
    <Modal opened onClose={onClose} title={<Text fw={700}>Sentence with <span className={styles.chk}>{seed.clause}</span></Text>} size="lg">
      <Stack gap="sm">
        {same.length > 0 && (
          <div>
            <Text size="sm" fw={700} mb={4}>Stored sentences with this pronoun and form</Text>
            <Stack gap={4}>
              {same.slice(0, 5).map((e, i) => (
                <div key={i} className={styles.example}>
                  <div className={styles.chk}>{e.chk.slice(0, e.start)}<mark className={styles.hit}>{e.chk.slice(e.start, e.end)}</mark>{e.chk.slice(e.end)}</div>
                  {e.en && <Text size="sm" c="dimmed">{e.en}</Text>}
                  <Group gap={4} mt={2}><Text span size="xs" c="dimmed">{e.source}</Text><AddToTalk chk={e.chk} en={e.en} source={e.source} reference={e.reference} size="xs" /></Group>
                </div>
              ))}
            </Stack>
          </div>
        )}
        <Textarea label="English sentence" description="Edit it to say what you want, then generate the Chuukese." autosize minRows={2} value={en} onChange={(e) => setEn(e.currentTarget.value)} />
        <Group>
          <Button leftSection={<IconSparkles size={16} />} onClick={generate} loading={busy} disabled={!en.trim()}>Generate Chuukese</Button>
          <Text size="xs" c="dimmed">Uses the site's translation engine; check it before saving.</Text>
        </Group>
        {error && <Alert color="red">{error}</Alert>}
        {(chk || busy) && (
          <>
            <Textarea label="Chuukese" autosize minRows={2} value={chk} onChange={(e) => { setChk(e.currentTarget.value); setSaved(false) }} className={styles.chkArea} />
            {chk && (usesClause
              ? <Text size="xs" c="green">Uses “{seed.clause}”.</Text>
              : <Text size="xs" c="orange">Does not contain “{seed.clause}”. The engine chose another wording; edit the Chuukese so it uses the pronoun and form you picked, or try a different English sentence.</Text>)}
            <Group>
              <Button size="xs" color="green" leftSection={<IconCheck size={14} />} onClick={save} disabled={!chk.trim() || saved}>{saved ? 'Saved as verified' : 'Save as verified pair'}</Button>
              {chk.trim() && <AddToTalk chk={chk.trim()} en={en.trim()} source="verb lookup" reference={seed.clause} size="xs" variant="button" />}
            </Group>
          </>
        )}
      </Stack>
    </Modal>
  )
}

/** The English sentence with the verb's translation marked. */
function HighlightEnglish({ text, pattern }: { text: string; pattern: RegExp | null }) {
  const m = pattern ? pattern.exec(text) : null
  if (!m) return <>{text}</>
  return <>{text.slice(0, m.index)}<mark className={styles.hitEn}>{m[0]}</mark>{text.slice(m.index + m[0].length)}</>
}

export default function VerbLookup() {
  const [params, setParams] = useSearchParams()
  const [q, setQ] = useState(params.get('q') || '')
  const [data, setData] = useState<Lookup | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [object, setObject] = useState('him')
  const [aspect, setAspect] = useState('')
  const [wol, setWol] = useState<WolHit[] | null>(null)
  const [wolLoading, setWolLoading] = useState(false)
  const [wolError, setWolError] = useState<string | null>(null)
  const [seed, setSeed] = useState<Seed | null>(null)

  const lookup = async (verb: string) => {
    const v = verb.trim()
    if (!v) return
    setLoading(true); setError(null); setWol(null); setWolError(null)
    try {
      const r = await axios.get<Lookup>('/api/verbs/lookup', { params: { q: v } })
      setData(r.data); setObject('him'); setAspect('')
      setParams({ q: v }, { replace: true })
    } catch (e) { setError(errorMessage(e, 'Could not look up the verb')) } finally { setLoading(false) }
  }
  // A verb in the address bar (a link from another page) is looked up on open; this is the dictionary, not wol.jw.org.
  useEffect(() => { const v = params.get('q'); if (v && !data) void lookup(v) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const searchWol = async () => {
    if (!data) return
    setWolLoading(true); setWolError(null)
    try {
      const r = await axios.post('/api/wol/verb-examples', { verb: data.verb, pages: 1, limit: 30, dictionary: false })
      setWol(r.data.results || [])
    } catch (e) { setWolError(errorMessage(e, 'Could not reach wol.jw.org')) } finally { setWolLoading(false) }
  }

  const chosen = data?.objects.find((o) => o.object === object)
  const enPattern = useMemo(() => (data ? englishPattern([data.english, ...data.objects.map((o) => o.gloss), ...data.other_forms.slice(0, 10).map((o) => o.english)]) : null), [data])
  const form = chosen?.form || data?.verb || ''
  const objectEnglish = (o: ObjectForm) => (o.object === 'him' ? '' : ` ${o.english.replace(/ \(.*\)/, '')}`)
  const verbEnglish = data ? baseVerb(data.english) + (chosen ? objectEnglish(chosen) : '') : ''
  const between = aspect ? `${aspect} ` : ''
  const aspectEnglish = data?.aspects.find((a) => a.word === aspect)?.english

  return (
    <Stack gap="md" className={styles.page}>
      <SentenceModal seed={seed} examples={data?.examples || []} onClose={() => setSeed(null)} />
      <div>
        <Title order={2}><IconAbc size={26} style={{ verticalAlign: 'middle' }} /> Verb Lookup</Title>
        <Text c="dimmed" size="sm">Type a verb in Chuukese or English to see it with every subject pronoun and tense marker, every object suffix, and examples from the stored library.</Text>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); void lookup(q) }}>
        <Group align="flex-end" gap="xs">
          <TextInput label="Verb" placeholder="Chuukese or English, e.g. álisi, tongei, need, help" value={q} onChange={(e) => setQ(e.currentTarget.value)} style={{ flex: 1, maxWidth: 420 }} />
          <Button type="submit" leftSection={<IconSearch size={16} />} loading={loading}>Look up</Button>
        </Group>
      </form>
      {error && <Alert color="red">{error}</Alert>}
      {loading && !data && <Loader size="sm" />}

      {data && (
        <>
          {data.matches.length > 0 && (
            // An English query: the dictionary words that carry that meaning; the first is shown, the others are a click away.
            <Card withBorder radius="md" p="sm">
              <Text size="sm" fw={700} mb={4}>Words that mean “{data.query}”</Text>
              <Group gap={6}>
                {data.matches.map((m) => (
                  <Button key={m.chuukese} size="xs" variant={m.chuukese === data.verb ? 'filled' : 'light'} color="violet" onClick={() => { setQ(m.chuukese); void lookup(m.chuukese) }}>
                    {m.chuukese}<Text span size="xs" ml={6} opacity={0.85}>{m.english}{m.grammar ? ` (${m.grammar})` : ''}</Text>
                  </Button>
                ))}
              </Group>
            </Card>
          )}
          <Card withBorder radius="md" p="md" className={styles.head}>
            <Group gap="sm" align="baseline">
              <Text className={styles.verb}>{data.verb}</Text>
              <Text size="lg" fw={600}>{data.english ? `= ${data.english}` : <Text span c="dimmed">not in the dictionary; forms are by rule</Text>}</Text>
              {data.grammar && <Badge variant="light" color="violet">{data.grammar}{data.modifier ? ` · ${data.modifier}` : ''}</Badge>}
            </Group>
            {data.definition && <Text size="sm" c="dimmed" mt={4}>{data.definition}</Text>}
          </Card>

          {/* ── Object and aspect pickers: they change the verb form shown in the subject table ── */}
          <Card withBorder radius="md" p="md">
            <Group justify="space-between" align="flex-start" wrap="wrap" gap="md">
              <div>
                <Text fw={700} size="sm" mb={6}>Object (suffix on the verb)</Text>
                <Chip.Group value={object} onChange={(v) => setObject(typeof v === 'string' ? v : 'him')}>
                  <Group gap={6}>
                    {data.objects.map((o) => (
                      <Tooltip key={o.object} label={o.attested ? `${o.form} = ${o.gloss || o.english} (in the dictionary)` : `${o.form}: formed by rule, not yet in the dictionary${o.alternatives.length ? `; could also be ${o.alternatives.join(', ')}` : ''}`}>
                        <Chip value={o.object} size="sm" variant={o.attested ? 'filled' : 'outline'} color={o.attested ? 'violet' : 'gray'}>{o.english} <span className={styles.suffix}>{o.suffix}</span></Chip>
                      </Tooltip>
                    ))}
                  </Group>
                </Chip.Group>
              </div>
              <div>
                <Text fw={700} size="sm" mb={6}>Between marker and verb</Text>
                <SegmentedControl size="xs" value={aspect} onChange={setAspect} data={[{ value: '', label: 'nothing' }, ...data.aspects.map((a) => ({ value: a.word, label: `${a.word} (${a.english})` }))]} />
              </div>
            </Group>
            <Text size="sm" mt="sm">
              Showing <b className={styles.chk}>{between}{form}</b>
              {chosen && !chosen.attested && <Badge ml={6} size="xs" variant="outline" color="gray">formed by rule</Badge>}
              {chosen?.attested && chosen.gloss && <Text span c="dimmed"> · {chosen.gloss}</Text>}
            </Text>
          </Card>

          {/* ── Subject pronoun × tense table ── */}
          <Card withBorder radius="md" p="md">
            <Text fw={700} mb="xs">Subject pronoun and tense marker + verb</Text>
            <Table.ScrollContainer minWidth={760}>
              <Table striped highlightOnHover withColumnBorders className={styles.table}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Subject</Table.Th>
                    {data.tenses.map((t) => <Table.Th key={t.id}>{t.label}</Table.Th>)}
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {data.subjects.map((row) => (
                    <Table.Tr key={row.person}>
                      <Table.Td><b>{row.english}</b><br /><Text span size="xs" c="dimmed">{row.pronoun}</Text></Table.Td>
                      {row.cells.map((c) => {
                        const t = data.tenses.find((x) => x.id === c.tense)!
                        const chk = `${c.marker} ${between}${form}`
                        const en = gloss(t.gloss, row.english.split(' ')[0] === 'he' ? 'he / she / it' : row.english, verbEnglish) + (aspectEnglish ? ` (${aspectEnglish})` : '')
                        return (
                          <Table.Td key={c.tense} className={styles.cell}>
                            <Group gap={4} wrap="nowrap" align="flex-start">
                              <div style={{ flex: 1 }}>
                                <span className={styles.chk}><span className={styles.marker}>{c.marker}</span> {between}{form}</span>
                                <Text size="xs" c="dimmed">{en}</Text>
                              </div>
                              <Tooltip label={`Make a sentence with “${chk}”`}><ActionIcon size="sm" variant="subtle" color="violet" aria-label="Make a sentence" onClick={() => setSeed({ clause: chk, marker: c.marker, form, en, person: row.person, tense: c.tense })}><IconSparkles size={14} /></ActionIcon></Tooltip>
                            </Group>
                          </Table.Td>
                        )
                      })}
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
            <Text size="xs" c="dimmed" mt={6}>Markers come from the dictionary's pronoun entries. The English is assembled from the tense and the verb's base meaning, so treat it as a guide.</Text>
          </Card>

          {/* ── Object forms ── */}
          <Card withBorder radius="md" p="md">
            <Text fw={700} mb="xs">Object forms</Text>
            <Table className={styles.table}>
              <Table.Thead><Table.Tr><Table.Th>Object</Table.Th><Table.Th>Suffix</Table.Th><Table.Th>Form</Table.Th><Table.Th>Meaning</Table.Th><Table.Th>Status</Table.Th></Table.Tr></Table.Thead>
              <Table.Tbody>
                {data.objects.map((o) => (
                  <Table.Tr key={o.object}>
                    <Table.Td>{o.english}</Table.Td>
                    <Table.Td><span className={styles.suffix}>{o.suffix}</span></Table.Td>
                    <Table.Td><span className={styles.chk}>{o.form}</span>{o.alternatives.length > 0 && !o.attested && <Text span size="xs" c="dimmed"> or {o.alternatives.join(', ')}</Text>}</Table.Td>
                    <Table.Td>{o.gloss || <Text span c="dimmed">{baseVerb(data.english)}{objectEnglish(o)}</Text>}</Table.Td>
                    <Table.Td>{o.attested ? <Badge size="xs" color="violet" variant="light">in dictionary</Badge> : <Badge size="xs" color="gray" variant="outline">formed by rule</Badge>}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            {data.other_forms.length > 0 && (
              <>
                <Text fw={700} mt="md" mb={4} size="sm">Other forms built on {data.verb}</Text>
                <Group gap={6}>
                  {data.other_forms.map((o) => (
                    <Tooltip key={o.form} label={`${o.english || '—'}${o.modifier ? ` · ${o.modifier}` : ''}`}>
                      <Badge variant="outline" color="gray" size="lg" className={styles.other} onClick={() => { setQ(o.form); void lookup(o.form) }}>{o.form}<Text span size="xs" c="dimmed"> {o.english ? `· ${o.english}` : ''}</Text></Badge>
                    </Tooltip>
                  ))}
                </Group>
              </>
            )}
          </Card>

          {/* ── Examples ── */}
          <Card withBorder radius="md" p="md">
            <Group justify="space-between" mb="xs">
              <Text fw={700}>Examples with a subject pronoun ({data.examples.length} stored)</Text>
              <Button size="xs" variant="light" leftSection={<IconWorld size={14} />} onClick={searchWol} loading={wolLoading} disabled={wol !== null}>Search wol.jw.org</Button>
            </Group>
            {data.examples.length === 0 && <Text c="dimmed" size="sm">No stored sentence has a subject marker directly before this verb yet.</Text>}
            <Stack gap={6}>
              {data.examples.map((e, i) => {
                const person = data.persons.find((p) => p.id === e.person)
                const tense = data.tenses.find((t) => t.id === e.tense)
                return (
                  <div key={i} className={styles.example}>
                    <Group gap={6} wrap="nowrap" align="flex-start">
                      <div style={{ flex: 1 }}>
                        <div className={styles.chk}>{e.chk.slice(0, e.start)}<mark className={styles.hit}>{e.chk.slice(e.start, e.end)}</mark>{e.chk.slice(e.end)}</div>
                        {e.en && <Text size="sm" c="dimmed"><HighlightEnglish text={e.en} pattern={enPattern} /></Text>}
                        <Group gap={4} mt={2}>
                          {person && <Badge size="xs" variant="light" color="violet">{person.english}</Badge>}
                          {tense && <Badge size="xs" variant="light" color="blue">{tense.label}</Badge>}
                          {e.aspect && <Badge size="xs" variant="light" color="teal">{e.aspect}</Badge>}
                          <Text span size="xs" c="dimmed">{e.source}{e.reference ? ` · ${e.reference}` : ''}</Text>
                        </Group>
                      </div>
                      <AddToTalk chk={e.chk} en={e.en} source={e.source} reference={e.reference} size="xs" />
                    </Group>
                  </div>
                )
              })}
            </Stack>
            {wolError && <Alert color="orange" mt="sm">{wolError}</Alert>}
            {wol && (
              <>
                <Text fw={700} mt="md" mb={4} size="sm">From wol.jw.org ({wol.length})</Text>
                {wol.length === 0 && <Text c="dimmed" size="sm">wol.jw.org returned nothing for this verb.</Text>}
                <Stack gap={6}>
                  {wol.map((h, i) => (
                    <div key={i} className={styles.example}>
                      <div className={styles.chk}>{h.segments.map((s, k) => (s.match ? <mark key={k} className={styles.hit}>{s.text}</mark> : <span key={k}>{s.text}</span>))}</div>
                      <Group gap={4} mt={2}>
                        {h.subject && <Badge size="xs" variant="light" color="violet">{h.subject.subject}{h.subject.tense ? ` · ${h.subject.tense}` : ''}</Badge>}
                        {h.link ? <Anchor href={h.link} target="_blank" rel="noopener noreferrer" size="xs">{h.title || h.citation || 'wol.jw.org'}</Anchor> : <Text span size="xs" c="dimmed">{h.title}</Text>}
                      </Group>
                    </div>
                  ))}
                </Stack>
              </>
            )}
          </Card>
        </>
      )}
    </Stack>
  )
}
