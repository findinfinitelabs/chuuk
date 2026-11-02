/**
 * ReferenceModal.tsx
 * Purpose: show what an outline citation ("w21.08 5 ¶9", "lff lesson 16
 * points 4-5") points at: the article on wol.jw.org, the cited paragraph(s)
 * with the outline point's key phrases marked, and the same paragraph(s) in
 * Chuukese when the publication exists in Chuukese, with the sentence that
 * carries the thought marked by content alignment. Each Chuukese sentence can
 * be sent to the talk.
 */

import { useEffect, useState } from 'react'
import { Alert, Anchor, Badge, Box, Button, Divider, Group, Loader, Modal, Paper, Stack, Switch, Text } from '@mantine/core'
import { IconExternalLink, IconRefresh } from '@tabler/icons-react'
import axios from 'axios'
import AddToTalk from './AddToTalk'
import { GlossCard, GlossLegend, GlossedWords } from './GlossedText'
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

const errorMessage = (e: unknown, fallback: string) =>
  (axios.isAxiosError(e) && (e.response?.data?.error as string)) || (e instanceof Error ? e.message : fallback)

function Marked({ row, big }: { row: SentenceRow; big?: boolean }) {
  return (
    <Text component="span" style={{ background: row.hit ? 'rgba(255, 212, 59, 0.35)' : undefined, borderRadius: 4, padding: row.hit ? '1px 2px' : 0, fontSize: big ? '1.08rem' : undefined, fontWeight: big ? 600 : undefined }}>
      {row.words.map((w, i) => (w.hit ? <mark key={i} style={{ background: '#ffd43b', padding: 0 }}>{w.text}</mark> : <span key={i}>{w.text}</span>))}
    </Text>
  )
}

export default function ReferenceModal({ reference, context, opened, onClose, pointLabel, talkId }: {
  reference: string | null; context: string; opened: boolean; onClose: () => void; pointLabel?: string; talkId?: string
}) {
  const [gloss, setGloss] = useState<Gloss | null>(null)
  const [data, setData] = useState<ResolvedReference | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showEnglish, setShowEnglish] = useState(true)

  const load = async (refresh = false) => {
    if (!reference) return
    setLoading(true); setError(''); if (refresh) setData(null)
    try {
      const res = await axios.post<ResolvedReference>('/api/talks/references/resolve', { ref: reference, context, refresh, talk_id: talkId })
      setData(res.data)
    } catch (e) {
      setError(errorMessage(e, 'Could not resolve the reference'))
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { if (opened && reference) { setData(null); load() } }, [opened, reference]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Modal opened={opened} onClose={onClose} size="xl" title={<Group gap="xs"><Badge size="lg" variant="light" color="violet">{reference}</Badge>{pointLabel && <Text size="sm" c="dimmed">for point {pointLabel}</Text>}</Group>}>
      {loading && <Group justify="center" p="lg"><Loader /><Text size="sm" c="dimmed">Reading the article on wol.jw.org… the first time takes a few seconds, after that it is instant.</Text></Group>}
      {error && <Alert color="red">{error}</Alert>}
      {data && (
        <Stack gap="sm">
          <Group justify="space-between" wrap="wrap">
            <Box>
              <Text fw={700}>{data.title.chk || data.title.en}</Text>
              {data.title.chk && data.title.en && <Text size="sm" c="dimmed">{data.title.en}</Text>}
            </Box>
            <Group gap="xs">
              <Switch size="sm" label="English" checked={showEnglish} onChange={(e) => setShowEnglish(e.currentTarget.checked)} />
              {data.links.chk && <Anchor href={data.links.chk} target="_blank" rel="noopener noreferrer"><Group gap={4}><IconExternalLink size={14} />Open Chuukese</Group></Anchor>}
              {data.links.en && <Anchor href={data.links.en} target="_blank" rel="noopener noreferrer"><Group gap={4}><IconExternalLink size={14} />Open English</Group></Anchor>}
              {data.links.search && data.links.search !== data.links.en && <Anchor href={data.links.search} target="_blank" rel="noopener noreferrer" c="dimmed"><Group gap={4}><IconExternalLink size={14} />Search citation on WOL</Group></Anchor>}
              <Button size="compact-xs" variant="subtle" leftSection={<IconRefresh size={12} />} onClick={() => load(true)}>Refresh</Button>
            </Group>
          </Group>
          {data.note && <Alert color={data.chuukese_available ? 'yellow' : 'orange'} py={6}><Text size="sm">{data.note}</Text></Alert>}
          {data.maps && <Group justify="space-between" wrap="wrap"><GlossLegend /><Text size="xs" c="dimmed">Hover a Chuukese word for its dictionary gloss.{data.stored ? ' Stored with this talk.' : ''}</Text></Group>}
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
                                <GlossedWords text={row.text} dictionary={data.maps.dictionary} similar={data.maps.similar} phrases={data.maps.phrases} onGloss={setGloss} keyPrefix={`${p.pid}-${i}-`}
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
      )}
      {gloss && <GlossCard gloss={gloss} />}
    </Modal>
  )
}
