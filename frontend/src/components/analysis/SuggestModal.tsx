/**
 * SuggestModal — a proposed dictionary entry for a word we do not hold (or
 * hold without a translation), with the evidence behind it.
 *
 * The backend gathers: the same word under other accents, related entries,
 * the translation model's gloss, and how wol.jw.org renders the word across
 * real sentence pairs. The user can edit the wording, then either add the
 * entry straight away (handed back through `onUse`) or send it to the
 * Translation Review queue for an admin to accept.
 */
import { useEffect, useState } from 'react'
import {
  Modal, Stack, Group, Text, TextInput, Autocomplete, Button, Alert, Badge, Loader, Paper, Divider, Box, Tooltip,
} from '@mantine/core'
import { IconAlertCircle, IconPlus, IconSend, IconSparkles, IconCheck } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import axios from 'axios'
import { GRAMMAR_OPTIONS } from './grammar'
import type { EntryPrefill } from './EntryEditor'
import styles from './analysis.module.css'

interface Variant { headword: string; english: string; grammar: string; definition: string; entry_id?: string | null }
interface Similar { word: string; english: string; grammar?: string }
interface Rendering { stem: string; word: string; count: number; share: number; lift: number; examples: number[] }
interface Pair { chk: string; en: string; scope?: string; link?: string | null; english_link?: string | null; citation?: string | null; title?: string | null }

export interface Suggestion {
  word: string
  variants: Variant[]
  similar: Similar[]
  model: { word: string; sentence: string | null; engine_name: string }
  wol: { pairs: Pair[]; renderings: Rendering[]; total: number; error: string | null }
  proposal: {
    english: string
    grammar: string
    definition: string
    source: 'accent_variant' | 'wol' | 'model' | ''
    model_gloss: string
    confirmed_in_context: boolean
  }
}

const SOURCE_LABEL: Record<string, { label: string; color: string }> = {
  accent_variant: { label: 'same word, other accents', color: 'blue' },
  wol: { label: 'from WOL usage', color: 'teal' },
  model: { label: 'translation model', color: 'grape' },
}

function errorMessage(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) return e.response?.data?.error || fallback
  return fallback
}

export function SuggestModal({
  word, sentence, english, englishSource = 'article', canAdd = true, onClose, onUse,
}: {
  /** The word to propose an entry for; null closes the modal. */
  word: string | null
  /** The sentence it was seen in. */
  sentence: string
  /** That sentence's English, when known. */
  english?: string | null
  /** Where that English came from: a real parallel text, or the model. */
  englishSource?: 'article' | 'model'
  /** Whether this user may add the entry directly (otherwise: review only). */
  canAdd?: boolean
  onClose: () => void
  /** Hand the wording to the add-entry form. */
  onUse: (prefill: EntryPrefill) => void
}) {
  const [data, setData] = useState<Suggestion | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [englishText, setEnglishText] = useState('')
  const [grammar, setGrammar] = useState('')
  const [queueing, setQueueing] = useState(false)

  useEffect(() => {
    if (!word) { setData(null); setError(''); return }
    let cancelled = false
    setLoading(true); setError(''); setData(null)
    axios.post('/api/sentences/suggest', { word, sentence, english: english || undefined, english_source: englishSource })
      .then((res) => {
        if (cancelled) return
        const s: Suggestion = res.data
        setData(s)
        setEnglishText(s.proposal.english || '')
        setGrammar(s.proposal.grammar || '')
      })
      .catch((e) => { if (!cancelled) setError(errorMessage(e, 'Could not build a suggestion')) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [word, sentence, english, englishSource])

  const queue = async () => {
    if (!data || !word) return
    if (!englishText.trim()) { setError('Give the proposal an English translation first'); return }
    setQueueing(true)
    setError('')
    try {
      await axios.post('/api/sentences/suggest/queue', {
        word,
        english: englishText.trim(),
        grammar: grammar.trim(),
        definition: data.proposal.definition || '',
        sentence,
        english_sentence: (englishSource === 'article' ? english : null) || data.model.sentence || '',
        evidence: {
          source: data.proposal.source,
          variants: data.variants,
          similar: data.similar,
          renderings: data.wol.renderings,
          pairs: data.wol.pairs,
          model: data.model,
        },
      })
      notifications.show({ title: 'Sent to review', message: `“${word}” is waiting in the Translation Review queue.`, color: 'teal' })
      onClose()
    } catch (e) {
      setError(errorMessage(e, 'Could not send to the review queue'))
    } finally {
      setQueueing(false)
    }
  }

  const source = data ? SOURCE_LABEL[data.proposal.source] : undefined

  return (
    <Modal
      opened={!!word}
      onClose={onClose}
      size="xl"
      title={
        <Group gap="xs">
          <IconSparkles size={18} color="#7048e8" />
          <Text fw={700}>Suggest an entry for</Text>
          <Text fw={700} c="blue.7" style={{ fontFamily: 'Georgia, serif' }}>{word}</Text>
        </Group>
      }
    >
      {loading && (
        <Group justify="center" py="xl">
          <Loader />
          <Text c="dimmed">Checking accents, related entries, the model and wol.jw.org…</Text>
        </Group>
      )}
      {error && <Alert icon={<IconAlertCircle size={16} />} color="red" mb="sm">{error}</Alert>}

      {data && (
        <Stack gap="md">
          {/* The proposal, editable */}
          <Paper withBorder p="md" radius="md">
            <Group gap="xs" mb="xs">
              <Text size="xs" c="dimmed" tt="uppercase" fw={700}>Proposed entry</Text>
              {source && <Badge size="xs" variant="light" color={source.color}>{source.label}</Badge>}
              {!data.proposal.english && <Badge size="xs" variant="light" color="gray">no confident proposal — fill it in</Badge>}
              {data.proposal.confirmed_in_context && (
                <Tooltip label="This wording also appears in the English of the sentence being analyzed">
                  <Badge size="xs" variant="light" color="green" leftSection={<IconCheck size={10} />}>matches the sentence's English</Badge>
                </Tooltip>
              )}
            </Group>
            <Group align="flex-end" gap="sm" wrap="wrap">
              <TextInput
                label="English"
                value={englishText}
                onChange={(e) => setEnglishText(e.currentTarget.value)}
                style={{ flex: 2, minWidth: 220 }}
              />
              <Autocomplete
                label="Grammar"
                value={grammar}
                onChange={setGrammar}
                data={GRAMMAR_OPTIONS}
                style={{ flex: 1, minWidth: 150 }}
              />
            </Group>
            {data.proposal.definition && <Text size="xs" c="dimmed" mt={6}>Definition carried over: {data.proposal.definition}</Text>}
          </Paper>

          {/* Evidence */}
          {data.variants.length > 0 && (
            <Box>
              <Text size="xs" c="dimmed" tt="uppercase" fw={700} mb={4}>Same word, spelled with other accents</Text>
              <Stack gap={4}>
                {data.variants.map((v) => (
                  <Group key={v.headword} gap="xs" wrap="wrap">
                    <Text fw={700} className={styles.headword}>{v.headword}</Text>
                    <Text size="sm">{v.english || <Text component="span" c="dimmed" fs="italic">no translation yet</Text>}</Text>
                    {v.grammar && <Badge size="xs" variant="outline">{v.grammar}</Badge>}
                    {v.english && (
                      <Button size="compact-xs" variant="subtle" onClick={() => { setEnglishText(v.english); if (v.grammar) setGrammar(v.grammar) }}>use</Button>
                    )}
                  </Group>
                ))}
              </Stack>
            </Box>
          )}

          <Box>
            <Group gap="xs" mb={4}>
              <Text size="xs" c="dimmed" tt="uppercase" fw={700}>How wol.jw.org renders it</Text>
              {data.wol.total > 0 && <Badge size="xs" variant="light">{data.wol.total} sentence{data.wol.total === 1 ? '' : 's'} on WOL</Badge>}
            </Group>
            {data.wol.error && <Text size="xs" c="red">{data.wol.error}</Text>}
            {!data.wol.error && data.wol.renderings.length === 0 && (
              <Text size="xs" c="dimmed">
                {data.wol.pairs.length < 2
                  ? 'Too few sentence pairs with English to tell.'
                  : 'No single English word recurs across the pairs — read them below and decide.'}
              </Text>
            )}
            {data.wol.renderings.length > 0 && (
              <Group gap={6} wrap="wrap">
                {data.wol.renderings.map((r) => (
                  <Tooltip key={r.stem} label={`in ${r.count} of ${data.wol.pairs.length} sentence pairs · ${r.lift}× more than usual · click to use`}>
                    <Badge
                      variant={englishText.trim().toLowerCase() === r.word ? 'filled' : 'light'}
                      color="teal"
                      style={{ cursor: 'pointer' }}
                      onClick={() => setEnglishText(r.word)}
                    >
                      {r.word} · {r.count}
                    </Badge>
                  </Tooltip>
                ))}
              </Group>
            )}
            {data.wol.pairs.length > 0 && (
              <Stack gap={6} mt="xs">
                {data.wol.pairs.slice(0, 5).map((p, i) => (
                  <Paper key={i} withBorder p="xs" radius="sm">
                    <Text size="sm" className={styles.sentence} style={{ fontSize: '0.95rem', lineHeight: 1.5 }}>{p.chk}</Text>
                    <Box className={styles.english} style={{ marginTop: 4 }}>
                      <Text size="sm" className={styles.englishText} style={{ fontSize: '0.9rem' }}>{p.en}</Text>
                      {p.citation && <Text size="xs" c="dimmed" className={styles.citation}>{p.citation}</Text>}
                    </Box>
                  </Paper>
                ))}
              </Stack>
            )}
          </Box>

          <Box>
            <Text size="xs" c="dimmed" tt="uppercase" fw={700} mb={4}>{data.model.engine_name} translation model</Text>
            <Group gap="xs" wrap="wrap">
              <Text size="sm">
                word: {data.model.word
                  ? <Text component="span" fw={600}>{data.model.word}</Text>
                  : <Text component="span" c="dimmed" fs="italic">no gloss</Text>}
              </Text>
              {data.proposal.model_gloss && (
                <Button size="compact-xs" variant="subtle" onClick={() => setEnglishText(data.proposal.model_gloss)}>use</Button>
              )}
            </Group>
            {data.model.sentence && (
              <Text size="xs" c="dimmed" mt={2}>sentence: {data.model.sentence}</Text>
            )}
            {english && englishSource === 'article' && (
              <Text size="xs" c="dimmed" mt={2}>English from the article: {english}</Text>
            )}
          </Box>

          {data.similar.length > 0 && (
            <Box>
              <Text size="xs" c="dimmed" tt="uppercase" fw={700} mb={4}>Related entries we hold</Text>
              <Group gap={6} wrap="wrap">
                {data.similar.map((s) => (
                  <Tooltip key={s.word} label={s.english ? `${s.english}${s.grammar ? ` · ${s.grammar}` : ''}` : 'no translation yet'}>
                    <Badge
                      variant="light"
                      color="yellow"
                      style={{ cursor: s.english ? 'pointer' : 'default' }}
                      onClick={() => { if (s.english) { setEnglishText(s.english); if (s.grammar) setGrammar(s.grammar) } }}
                    >
                      {s.word}{s.english ? ` — ${s.english}` : ''}
                    </Badge>
                  </Tooltip>
                ))}
              </Group>
            </Box>
          )}

          <Divider />
          <Group justify="flex-end" gap="sm">
            <Button variant="subtle" onClick={onClose}>Close</Button>
            <Tooltip label="File it for an admin to accept on the Translation Review page">
              <Button variant="light" color="violet" leftSection={<IconSend size={16} />} loading={queueing} onClick={queue} disabled={!englishText.trim()}>
                Send to review
              </Button>
            </Tooltip>
            {canAdd && (
              <Button
                leftSection={<IconPlus size={16} />}
                disabled={!englishText.trim()}
                onClick={() => onUse({ english: englishText.trim(), grammar: grammar.trim(), definition: data.proposal.definition || '' })}
              >
                Add now
              </Button>
            )}
          </Group>
        </Stack>
      )}
    </Modal>
  )
}
