/**
 * ReferenceView.tsx
 * Purpose: show, under a talk point, what an outline citation ("w12 11/1 23",
 * "w21.08 5 ¶9", "lff lesson 16 points 4-5") points at: a link to the article
 * on wol.jw.org, the cited paragraph(s) with their numbers and the outline
 * point's key phrases marked, and the same paragraph(s) in Chuukese when the
 * publication exists in Chuukese, with the sentence that carries the thought
 * marked by content alignment and every Chuukese word glossed from the
 * dictionary. Each Chuukese sentence can be sent to the talk.
 *
 * `ReferenceInline` loads the reference itself: the copy stored with the talk
 * first (no request to WOL), then the shared cache, then wol.jw.org.
 */

import { useEffect, useState } from 'react'
import { ActionIcon, Alert, Anchor, Badge, Box, Collapse, Divider, Group, Loader, Paper, Stack, Text, Tooltip } from '@mantine/core'
import { IconChevronDown, IconChevronRight, IconExternalLink, IconRefresh } from '@tabler/icons-react'
import axios from 'axios'
import AddToTalk from './AddToTalk'
import { GlossedWords } from './GlossedText'
import type { Dictionary, Gloss, SimilarMap } from './GlossedText'
import type { PhraseMap } from './glossUtils'

interface Word { text: string; hit: boolean }
interface SentenceRow { text: string; hit: boolean; words: Word[]; english_indices?: number[] }
interface Paragraph { number: number; pid: string; en: string | null; chk: string | null; en_sentences: SentenceRow[]; chk_sentences: SentenceRow[] | null }
export interface ResolvedReference {
  ref: string; kind: string; key_words: string[]; title: { en: string; chk: string }
  links: { en: string | null; chk: string | null; search?: string | null }; chuukese_available: boolean; paragraphs: Paragraph[]; note: string; cached?: boolean; stored?: boolean
  maps?: { dictionary: Dictionary; similar: SimilarMap; phrases: PhraseMap }
}
/** A reference stored with a talk by the resolve route. */
export interface StoredReference { key: { ref: string; context: string }; result: ResolvedReference }

import { searchLink } from './wolLinks'

const errorMessage = (e: unknown, fallback: string) =>
  (axios.isAxiosError(e) && (e.response?.data?.error as string)) || (e instanceof Error ? e.message : fallback)

function Marked({ row, big }: { row: SentenceRow; big?: boolean }) {
  return (
    <Text component="span" style={{ background: row.hit ? 'rgba(255, 212, 59, 0.35)' : undefined, borderRadius: 4, padding: row.hit ? '1px 2px' : 0, fontSize: big ? '1.08rem' : undefined, fontWeight: big ? 600 : undefined }}>
      {row.words.map((w, i) => (w.hit ? <mark key={i} style={{ background: '#ffd43b', padding: 0 }}>{w.text}</mark> : <span key={i}>{w.text}</span>))}
    </Text>
  )
}

/** The paragraphs of a resolved reference, Chuukese glossed, English marked. */
export function ReferenceBody({ data, showEnglish, onGloss }: { data: ResolvedReference; showEnglish: boolean; onGloss: (g: Gloss | null) => void }) {
  return (
    <Stack gap="sm">
      {data.note && <Alert color={data.chuukese_available ? 'yellow' : 'orange'} py={6}><Text size="sm">{data.note}</Text></Alert>}
      {data.key_words.length > 0 && (
        <Text size="xs" c="dimmed">Key phrases from your outline: {data.key_words.map((k) => <Badge key={k} size="xs" variant="outline" color="yellow" mr={4}>{k}</Badge>)}</Text>
      )}
      {data.paragraphs.map((p) => (
        <Paper key={p.pid} withBorder radius="md" p="md" style={{ borderLeft: '5px solid var(--mantine-color-violet-5)' }}>
          <Group gap="sm" align="flex-start" wrap="nowrap">
            <Text style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--mantine-color-violet-6)', lineHeight: 1, minWidth: '2.4rem', textAlign: 'center' }}>¶{p.number}</Text>
            <Box style={{ flex: 1 }}>
              {p.chk_sentences && (
                <Box mb="xs">
                  <Text size="xs" fw={700} tt="uppercase" c="dimmed">Chuukese</Text>
                  <Stack gap={4}>
                    {p.chk_sentences.map((row, i) => (
                      <Group key={i} gap={6} wrap="nowrap" align="flex-start">
                        <Box style={{ flex: 1, background: row.hit ? 'rgba(255, 212, 59, 0.25)' : undefined, borderRadius: 4, padding: '1px 3px', fontSize: '1.08rem', fontWeight: 600, lineHeight: 1.4 }}>
                          {data.maps ? (
                            <GlossedWords text={row.text} dictionary={data.maps.dictionary} similar={data.maps.similar} phrases={data.maps.phrases} onGloss={onGloss} keyPrefix={`${p.pid}-${i}-`}
                              marks={new Set(row.words.filter((w) => w.hit).map((w) => w.text.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '')))} />
                          ) : <Marked row={row} big />}
                        </Box>
                        <AddToTalk chk={row.text} en={(row.english_indices || []).map((k) => p.en_sentences[k]?.text).filter(Boolean).join(' ')} source="article" reference={`${data.ref} ¶${p.number}`} size="xs" />
                      </Group>
                    ))}
                  </Stack>
                </Box>
              )}
              {p.en && showEnglish && (
                <Box>
                  {p.chk_sentences && <Divider my={6} />}
                  <Text size="xs" fw={700} tt="uppercase" c="dimmed">English</Text>
                  <Text size="sm">
                    {p.en_sentences.map((row, i) => <span key={i}><Marked row={row} />{' '}</span>)}
                  </Text>
                </Box>
              )}
            </Box>
          </Group>
        </Paper>
      ))}
      {data.paragraphs.length === 0 && !data.note && <Text size="sm" c="dimmed">No paragraph text to show.</Text>}
    </Stack>
  )
}

/** One citation under a talk point: link, title, and the paragraphs. */
export function ReferenceInline({ reference, context, talkId, stored, showEnglish, onGloss }: {
  reference: string; context: string; talkId?: string; stored?: ResolvedReference; showEnglish: boolean; onGloss: (g: Gloss | null) => void
}) {
  const [data, setData] = useState<ResolvedReference | null>(stored || null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(true)

  const load = async (refresh = false) => {
    setLoading(true); setError('')
    try {
      const res = await axios.post<ResolvedReference>('/api/talks/references/resolve', { ref: reference, context, refresh, talk_id: talkId })
      setData(res.data)
    } catch (e) {
      setError(errorMessage(e, 'Could not resolve the reference'))
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { if (stored) setData(stored); else load() }, [reference, context]) // eslint-disable-line react-hooks/exhaustive-deps

  const link = data?.links.en || data?.links.search || searchLink(reference)
  return (
    <Paper withBorder radius="md" p="sm" mt={6} style={{ background: 'var(--mantine-color-violet-0)' }}>
      <Group justify="space-between" wrap="wrap" gap="xs">
        <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
          <ActionIcon variant="subtle" size="sm" onClick={() => setOpen((o) => !o)} aria-label={open ? 'Hide paragraphs' : 'Show paragraphs'}>
            {open ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
          </ActionIcon>
          <Anchor href={link} target="_blank" rel="noopener noreferrer" fw={700} c="violet"><Group gap={4} wrap="nowrap"><IconExternalLink size={14} />{reference}</Group></Anchor>
          {data && (data.title.chk || data.title.en) && (
            <Box style={{ minWidth: 0 }}>
              <Text size="sm" fw={600} truncate>{data.title.chk || data.title.en}</Text>
              {data.title.chk && data.title.en && <Text size="xs" c="dimmed" truncate>{data.title.en}</Text>}
            </Box>
          )}
          {loading && <Loader size="xs" />}
        </Group>
        <Group gap="xs">
          {data?.links.chk && <Anchor size="xs" href={data.links.chk} target="_blank" rel="noopener noreferrer">Open Chuukese</Anchor>}
          {data?.links.en && <Anchor size="xs" href={data.links.en} target="_blank" rel="noopener noreferrer">Open English</Anchor>}
          {data?.links.search && data.links.search !== data.links.en && <Anchor size="xs" c="dimmed" href={data.links.search} target="_blank" rel="noopener noreferrer">Search on WOL</Anchor>}
          <Tooltip label="Read the article again from wol.jw.org"><ActionIcon variant="subtle" size="sm" onClick={() => load(true)} loading={loading} aria-label="Refresh"><IconRefresh size={14} /></ActionIcon></Tooltip>
        </Group>
      </Group>
      <Collapse in={open}>
        <Box mt="xs">
          {loading && !data && <Text size="xs" c="dimmed">Reading the article on wol.jw.org… the first time takes a few seconds, after that it is instant.</Text>}
          {error && <Alert color="red" py={6}><Text size="sm">{error}</Text></Alert>}
          {data && <ReferenceBody data={data} showEnglish={showEnglish} onGloss={onGloss} />}
        </Box>
      </Collapse>
    </Paper>
  )
}
