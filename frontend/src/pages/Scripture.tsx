/**
 * Scripture.tsx — Scripture Lookup.
 * Purpose: look up any passage the way jw.org's Bible does: type a citation
 * (John 3:16, 17 · Ps 23 · 1 Pe 3:1, 2, 15 · Kölf. 37:29) or pick a book and
 * a chapter. Every verse is shown in Chuukese and English from the uploaded
 * Bibles (New World Translation; Liebenzell Paipel for Chuukese Genesis to
 * Malachi). The Chuukese carries the dictionary gloss overlay (hover, click),
 * the English can be shown or hidden, and any verse can be added to a talk.
 * Nothing is fetched from wol.jw.org and nothing is translated.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  ActionIcon, Alert, Badge, Box, Button, Card, Collapse, Container, Divider, Group, Loader, Paper, SegmentedControl, SimpleGrid, Stack, Switch, Text, TextInput, Title, Tooltip, UnstyledButton,
} from '@mantine/core'
import { IconArrowLeft, IconArrowRight, IconBook, IconChevronLeft, IconChevronRight, IconCopy, IconSearch, IconX } from '@tabler/icons-react'
import axios from 'axios'
import { GlossCard, GlossLegend, GlossedWords } from '../components/GlossedText'
import type { Dictionary, Gloss, SimilarMap } from '../components/GlossedText'
import type { PhraseMap } from '../components/glossUtils'
import type { BaseWord } from '../components/GlossedText'
import AddToTalk from '../components/AddToTalk'
import { alignWords, pairColor, WORD_TOKENS } from '../components/wordAlign'
import styles from './Scripture.module.css'

interface Book { number: number; name: string; chk_name: string; chapters: number }
interface WordLinks { chk: (number | null)[]; en: (number | null)[]; pairs: number; semantic: boolean; bases?: (BaseWord | null)[] }
interface Verse { n: number; en: string; chk: string; links?: WordLinks }
interface Maps { dictionary: Dictionary; similar: SimilarMap; phrases: PhraseMap }
interface Passage extends Book {
  chapter: number
  label: string
  whole: boolean
  verses: Verse[]
  highlight: number[]
  missing: number[]
  source_chk: 'nwt' | 'liebenzell'
  source_en: string
  source_chk_label: string
  prev: { book: number; chapter: number } | null
  next: { book: number; chapter: number } | null
  maps: Maps
}

type View = 'both' | 'chk' | 'en'
const VIEW_KEY = 'scripture-view'
const LINK_KEY = 'scripture-link-words'
const BASE_KEY = 'scripture-base-words'
const RECENT_KEY = 'scripture-recent'
const EXAMPLES = ['John 3:16', 'Ps 23', '1 Pe 3:1, 2, 15', 'Isa 55:8, 9', 'Mat 24:14', 'Kölf. 37:29']

function readRecent(): string[] {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]') } catch { return [] }
}
function pushRecent(q: string) {
  const list = [q, ...readRecent().filter((x) => x.toLowerCase() !== q.toLowerCase())].slice(0, 12)
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(list)) } catch { /* ignore */ }
  return list
}
function errorMessage(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) return e.response?.data?.error || fallback
  return fallback
}

/** The English of a verse with its paired words tinted like their Chuukese counterparts. */
function PairedEnglish({ text, pairs, activePair, onPairHover }: { text: string; pairs: (number | undefined)[]; activePair: number | null; onPairHover: (p: number | null) => void }) {
  // Tokens with their word ordinal, computed up front so render stays pure.
  const tokens = useMemo(() => {
    let wi = -1
    return text.split(WORD_TOKENS).filter(Boolean).map((tok) => ({ tok, wi: /^[\p{L}\p{N}]+$/u.test(tok) ? ++wi : -1 }))
  }, [text])
  return <>{tokens.map(({ tok, wi }, i) => {
    const pair = wi >= 0 ? pairs[wi] : undefined
    if (pair === undefined) return <span key={i}>{tok}</span>
    return <span key={i} className={styles.pairEn} style={{ background: pairColor(pair), boxShadow: activePair === pair ? `0 0 0 2px ${pairColor(pair)}` : undefined }} onMouseEnter={() => onPairHover(pair)} onMouseLeave={() => onPairHover(null)}>{tok}</span>
  })}</>
}

/** One verse: number, Chuukese with the gloss behind it, English beside or below. */
function VerseRow({ v, p, view, link, showBases, onGloss }: { v: Verse; p: Passage; view: View; link: boolean; showBases: boolean; onGloss: (g: Gloss | null) => void }) {
  const cite = `${p.name} ${p.chapter}:${v.n}`
  const [activePair, setActivePair] = useState<number | null>(null)
  // The server pairs words by spelling and meaning; the local aligner is the fallback for older responses.
  const align = useMemo(() => {
    if (!link || !v.chk || !v.en) return null
    if (v.links) return { chk: v.links.chk.map((x) => x ?? undefined), en: v.links.en.map((x) => x ?? undefined), pairs: v.links.pairs }
    return alignWords(v.chk, v.en, p.maps.dictionary)
  }, [link, v.chk, v.en, v.links, p.maps.dictionary])
  // Base words: the dictionary word a longer word was read through, when the verse's English supports it.
  const bases = useMemo(() => (showBases && v.links?.bases ? v.links.bases.map((b) => b ?? undefined) : undefined), [showBases, v.links])
  const chk = v.chk
    ? <Text className={styles.chk}><span className={styles.num}>{v.n}</span><GlossedWords text={v.chk} dictionary={p.maps.dictionary} similar={p.maps.similar} phrases={p.maps.phrases} onGloss={onGloss} keyPrefix={`${p.number}-${p.chapter}-${v.n}-`} pairs={align?.chk} activePair={activePair} onPairHover={setActivePair} bases={bases} /></Text>
    : <Text className={styles.chk}><span className={styles.num}>{v.n}</span><span className={styles.missing}>No Chuukese text for this verse in the uploaded Bibles</span></Text>
  const en = v.en
    ? <Text className={styles.en}>{view === 'en' && <span className={styles.num}>{v.n}</span>}{align ? <PairedEnglish text={v.en} pairs={align.en} activePair={activePair} onPairHover={setActivePair} /> : v.en}</Text>
    : <Text className={`${styles.en} ${styles.missing}`}>{view === 'en' && <span className={styles.num}>{v.n}</span>}No English text for this verse in the uploaded Bible</Text>
  return (
    <Box className={`${styles.verse}${p.highlight.includes(v.n) ? ` ${styles.highlight}` : ''}`} id={`v${p.number}-${p.chapter}-${v.n}`}>
      <Group align="flex-start" wrap="nowrap" gap="xs">
        <Box style={{ flex: 1, minWidth: 0 }}>
          {view === 'both' ? (
            <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md" verticalSpacing={4}>{chk}{en}</SimpleGrid>
          ) : view === 'chk' ? chk : en}
        </Box>
        <AddToTalk chk={v.chk} en={v.en} source="bible" reference={cite} size="xs" />
      </Group>
    </Box>
  )
}

export default function Scripture() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''
  const [input, setInput] = useState(q)
  const [books, setBooks] = useState<Book[] | null>(null)
  const [passages, setPassages] = useState<Passage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [gloss, setGloss] = useState<Gloss | null>(null)
  const [picker, setPicker] = useState(false)
  const [pickBook, setPickBook] = useState<Book | null>(null)
  const [recent, setRecent] = useState<string[]>(readRecent)
  const [view, setView] = useState<View>(() => { try { return (localStorage.getItem(VIEW_KEY) as View) || 'both' } catch { return 'both' } })
  // Link words: tint each Chuukese word and the English word its dictionary gloss matches alike.
  const [link, setLink] = useState<boolean>(() => { try { return localStorage.getItem(LINK_KEY) !== 'off' } catch { return true } })
  const [showBases, setShowBases] = useState<boolean>(() => { try { return localStorage.getItem(BASE_KEY) !== 'off' } catch { return true } })
  const [copied, setCopied] = useState<string | null>(null)
  const inFlight = useRef<string | null>(null)

  useEffect(() => { axios.get<Book[]>('/api/bible/books').then((r) => setBooks(r.data)).catch(() => setBooks([])) }, [])
  useEffect(() => { try { localStorage.setItem(VIEW_KEY, view) } catch { /* ignore */ } }, [view])
  useEffect(() => { try { localStorage.setItem(LINK_KEY, link ? 'on' : 'off') } catch { /* ignore */ } }, [link])
  useEffect(() => { try { localStorage.setItem(BASE_KEY, showBases ? 'on' : 'off') } catch { /* ignore */ } }, [showBases])

  // The address bar is the source of truth: a citation in it is looked up,
  // so a link or the browser's Back button shows the same passage.
  const [seenQ, setSeenQ] = useState(q)
  if (q !== seenQ) { setSeenQ(q); setInput(q) }
  useEffect(() => {
    if (inFlight.current === q) return
    inFlight.current = q
    const run = async () => {
      if (!q.trim()) { setPassages([]); setError(null); inFlight.current = null; return }
      setLoading(true); setError(null); setGloss(null); setPicker(false)
      try {
        const r = await axios.get<{ passages: Passage[] }>('/api/bible/lookup', { params: { q } })
        setPassages(r.data.passages); setRecent(pushRecent(q))
      } catch (e) {
        setPassages([]); setError(errorMessage(e, 'Could not look this up'))
      } finally {
        setLoading(false); inFlight.current = null
      }
    }
    void run()
  }, [q])

  const go = useCallback((citation: string) => {
    const c = citation.trim()
    if (!c) return
    setParams(c === q ? { q: c, t: String(Date.now()) } : { q: c })
  }, [q, setParams])

  const openChapter = (book: number, chapter: number, bookName?: string) => {
    const name = bookName || books?.find((b) => b.number === book)?.name
    if (name) go(`${name} ${chapter}`)
  }

  const copyPassage = async (p: Passage) => {
    const lines = [p.label, '', p.verses.map((v) => `${v.n} ${v.chk}`).join(' '), '', p.verses.map((v) => `${v.n} ${v.en}`).join(' ')]
    try { await navigator.clipboard.writeText(lines.join('\n')); setCopied(p.label); setTimeout(() => setCopied(null), 1500) } catch { /* clipboard blocked */ }
  }

  const hebrew = useMemo(() => (books || []).filter((b) => b.number < 40), [books])
  const greek = useMemo(() => (books || []).filter((b) => b.number >= 40), [books])

  return (
    <Container size="xl" className={styles.page} py="md">
      <Paper p="md" withBorder radius="md" mb="md" className={styles.head}>
        <Group gap="xs" mb={4}><IconBook size={26} /><Title order={2}>Scripture Lookup</Title></Group>
        <Text size="sm" c="dimmed">
          Type a citation the way jw.org takes it, or pick a book and chapter. Verses come from the uploaded Bibles: the New World Translation in English, and in Chuukese for Matthew to Revelation, with the Liebenzell Paipel for Chuukese Genesis to Malachi. Nothing is fetched from wol.jw.org and nothing is translated.
        </Text>
        <Group align="flex-end" gap="sm" mt="sm" wrap="wrap">
          <TextInput
            label="Citation"
            placeholder="e.g. John 3:16, 17 · Ps 23 · 1 Pe 3:1, 2, 15 · Kölf. 37:29"
            value={input}
            onChange={(e) => setInput(e.currentTarget.value)}
            onKeyDown={(e) => e.key === 'Enter' && go(input)}
            style={{ flex: 1, minWidth: 260 }}
            rightSection={input ? <ActionIcon variant="subtle" color="gray" aria-label="Clear" onClick={() => { setInput(''); setParams({}) }}><IconX size={14} /></ActionIcon> : undefined}
          />
          <Button onClick={() => go(input)} loading={loading} leftSection={<IconSearch size={16} />} disabled={!input.trim()}>Look up</Button>
          <Button variant={picker ? 'filled' : 'light'} color="orange" leftSection={<IconBook size={16} />} onClick={() => { setPicker((o) => !o); setPickBook(null) }}>Books</Button>
        </Group>
        {!q && (
          <Group gap={6} mt="sm" wrap="wrap">
            <Text size="xs" c="dimmed">{recent.length ? 'Recent:' : 'Try:'}</Text>
            {(recent.length ? recent : EXAMPLES).map((c) => (
              <Badge key={c} variant="light" color="gray" style={{ cursor: 'pointer', textTransform: 'none' }} onClick={() => go(c)}>{c}</Badge>
            ))}
          </Group>
        )}
      </Paper>

      {/* ── Book → chapter picker, as on jw.org ────────────────────────── */}
      <Collapse in={picker}>
        <Paper p="md" withBorder radius="md" mb="md">
          {!books ? <Loader size="sm" /> : pickBook ? (
            <>
              <Group justify="space-between" mb="sm">
                <Group gap="xs">
                  <ActionIcon variant="subtle" aria-label="Back to the books" onClick={() => setPickBook(null)}><IconArrowLeft size={18} /></ActionIcon>
                  <Text fw={700} size="lg">{pickBook.name}</Text>
                  <Text c="dimmed">{pickBook.chk_name}</Text>
                </Group>
                <Text size="xs" c="dimmed">{pickBook.chapters} chapter{pickBook.chapters === 1 ? '' : 's'} · pick one</Text>
              </Group>
              <div className={styles.chapterGrid}>
                {Array.from({ length: pickBook.chapters }, (_, i) => i + 1).map((c) => (
                  <Button key={c} variant="light" color="orange" className={styles.chapter} onClick={() => openChapter(pickBook.number, c, pickBook.name)}>{c}</Button>
                ))}
              </div>
            </>
          ) : (
            <Stack gap="md">
              {[['Hebrew-Aramaic Scriptures', hebrew], ['Christian Greek Scriptures', greek]].map(([title, list]) => (
                <Box key={title as string}>
                  <Text fw={700} size="sm" mb={6} c="dimmed" tt="uppercase">{title as string}</Text>
                  <div className={styles.bookGrid}>
                    {(list as Book[]).map((b) => (
                      <UnstyledButton key={b.number} className={styles.book} onClick={() => setPickBook(b)} style={{ border: '1px solid var(--mantine-color-gray-3)', borderRadius: 8 }}>
                        <span className={styles.en}>{b.name}</span>
                        <span className={styles.chkName}>{b.chk_name}</span>
                      </UnstyledButton>
                    ))}
                  </div>
                </Box>
              ))}
            </Stack>
          )}
        </Paper>
      </Collapse>

      {error && <Alert color="red" variant="light" mb="md" withCloseButton onClose={() => setError(null)}>{error}</Alert>}

      {loading && passages.length === 0 && <Group gap="xs"><Loader size="sm" /><Text c="dimmed">Reading the Bibles…</Text></Group>}

      {passages.length > 0 && (
        <>
          <Group className={styles.toolbar} justify="space-between" wrap="wrap" gap="sm">
            <SegmentedControl
              size="xs"
              value={view}
              onChange={(v) => setView(v as View)}
              data={[{ value: 'both', label: 'Chuukese + English' }, { value: 'chk', label: 'Chuukese' }, { value: 'en', label: 'English' }]}
            />
            <Tooltip label="Each Chuukese word the dictionary holds is tinted with the English word its gloss matches; hover one to see its partner"><Switch size="xs" label="Link words" checked={link} onChange={(e) => setLink(e.currentTarget.checked)} /></Tooltip>
            <Tooltip label="Under a longer word, the dictionary word it was read through (ápilúkú under ápilúkúni) when the English of the verse supports it"><Switch size="xs" label="Base words" checked={showBases} onChange={(e) => setShowBases(e.currentTarget.checked)} /></Tooltip>
            <GlossLegend />
          </Group>

          <Stack gap="md">
            {passages.map((p) => (
              <Card key={`${p.number}-${p.chapter}-${p.label}`} withBorder radius="md" padding="md">
                <Group justify="space-between" align="flex-start" wrap="wrap" mb="xs">
                  <Box>
                    <Text className={styles.label}>{p.label}</Text>
                    <Text size="sm" className={styles.chkLabel}>{p.chk_name} {p.chapter}{!p.whole && p.highlight.length ? `:${p.label.split(':').slice(1).join(':')}` : ''}</Text>
                  </Box>
                  <Group gap="xs" wrap="wrap">
                    <Tooltip label={`Chuukese: ${p.source_chk_label}`}><Badge variant="light" color={p.source_chk === 'nwt' ? 'blue' : 'teal'} style={{ textTransform: 'none' }}>{p.source_chk === 'nwt' ? 'NWT Chuukese' : 'Liebenzell Paipel'}</Badge></Tooltip>
                    <Tooltip label={`English: ${p.source_en}`}><Badge variant="light" color="gray" style={{ textTransform: 'none' }}>NWT English</Badge></Tooltip>
                    <Tooltip label="Copy the citation with both languages"><ActionIcon variant="subtle" aria-label="Copy passage" onClick={() => copyPassage(p)} color={copied === p.label ? 'green' : 'gray'}><IconCopy size={16} /></ActionIcon></Tooltip>
                  </Group>
                </Group>
                {p.missing.length > 0 && (
                  <Text size="xs" c="dimmed" mb={4}>Verse{p.missing.length === 1 ? '' : 's'} {p.missing.join(', ')} {p.missing.length === 1 ? 'is' : 'are'} not in this chapter of the uploaded Bibles.</Text>
                )}
                <Divider mb={4} />
                {p.verses.map((v) => <VerseRow key={v.n} v={v} p={p} view={view} link={link && view === 'both'} showBases={showBases && view !== 'en'} onGloss={setGloss} />)}
                <Divider mt="xs" mb="xs" />
                <Group justify="space-between" wrap="wrap">
                  {p.whole ? (
                    <>
                      <Button variant="subtle" size="xs" leftSection={<IconChevronLeft size={14} />} disabled={!p.prev} onClick={() => p.prev && openChapter(p.prev.book, p.prev.chapter)}>Previous chapter</Button>
                      <Button variant="subtle" size="xs" rightSection={<IconChevronRight size={14} />} disabled={!p.next} onClick={() => p.next && openChapter(p.next.book, p.next.chapter)}>Next chapter</Button>
                    </>
                  ) : (
                    <Button variant="light" size="xs" rightSection={<IconArrowRight size={14} />} onClick={() => go(`${p.name} ${p.chapter}`)}>Read the whole chapter</Button>
                  )}
                </Group>
              </Card>
            ))}
          </Stack>
        </>
      )}

      {gloss && <GlossCard gloss={gloss} />}
    </Container>
  )
}
