/**
 * EntryEditor — the add / edit dictionary modal shared by the Sentence and
 * Article Analysis pages.
 *
 * Edits in place when the word resolved to a `dictionary_entries` row;
 * otherwise adds a new entry (the add endpoint updates an existing headword
 * with the same spelling rather than duplicating it). A word matched under a
 * different accent spelling can be saved either as an edit of that headword
 * or as a new entry under the spelling seen in the text.
 */
import { useEffect, useState } from 'react'
import {
  Modal, Stack, Group, Text, TextInput, Textarea, Autocomplete, Button, Alert, Badge, SegmentedControl,
} from '@mantine/core'
import { IconAlertCircle, IconPencil, IconPlus } from '@tabler/icons-react'
import axios from 'axios'
import type { DictEntry } from '../GlossedText'
import { GRAMMAR_OPTIONS } from './grammar'

export interface EntryPrefill {
  english?: string
  grammar?: string
  definition?: string
}

export interface EntrySaved {
  mode: 'add' | 'edit'
  /** The headword written: the text's spelling, or the accent variant edited. */
  word: string
  entry_id?: string
  english: string
  grammar: string
  definition: string
  notes?: string
}

function errorMessage(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) return e.response?.data?.error || fallback
  return fallback
}

export function EntryEditor({
  opened, onClose, word, entry, example, prefill, onSaved,
}: {
  opened: boolean
  onClose: () => void
  /** The word as it appears in the text. */
  word: string
  /** Its dictionary entry, if any. */
  entry?: DictEntry | null
  /** Sentence saved as the example when adding. */
  example?: string
  /** Values to start from when adding (from the suggestion modal). */
  prefill?: EntryPrefill | null
  onSaved: (saved: EntrySaved) => void
}) {
  const editable = !!entry?.entry_id && (entry.source ?? 'dictionary') === 'dictionary'
  const isVariant = !!entry?.variant_of
  // For an accent variant: edit the headword we matched, or add the text's spelling.
  const [target, setTarget] = useState<'edit' | 'add'>('edit')
  const [english, setEnglish] = useState('')
  const [grammar, setGrammar] = useState('')
  const [definition, setDefinition] = useState('')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!opened) return
    setTarget(editable ? 'edit' : 'add')
    setEnglish(prefill?.english ?? entry?.english ?? '')
    setGrammar(prefill?.grammar ?? entry?.grammar ?? '')
    setDefinition(prefill?.definition ?? entry?.definition ?? '')
    setNotes('')
    setError('')
  }, [opened, word, entry, prefill, editable])

  const mode: 'add' | 'edit' = editable && target === 'edit' ? 'edit' : 'add'
  const headword = mode === 'edit' && entry?.variant_of ? entry.variant_of : word

  const save = async () => {
    if (!english.trim()) { setError('An English translation is required'); return }
    if (!grammar.trim()) { setError('A grammar type is required'); return }
    setBusy(true)
    setError('')
    try {
      if (mode === 'edit' && entry?.entry_id) {
        await axios.put('/api/dictionary/update', {
          entry_id: entry.entry_id,
          english_translation: english.trim(),
          grammar: grammar.trim(),
          definition: definition.trim(),
          ...(notes.trim() ? { notes: notes.trim() } : {}),
        })
        onSaved({ mode: 'edit', word: headword, entry_id: entry.entry_id, english: english.trim(), grammar: grammar.trim(), definition: definition.trim(), notes: notes.trim() })
      } else {
        const res = await axios.post('/api/dictionary/add', {
          chuukese_word: word,
          english_translation: english.trim(),
          grammar: grammar.trim(),
          definition: definition.trim(),
          confidence: 100,
          verified: true,
          chuukese_example: example || '',
          type: 'sentence',
        })
        onSaved({ mode: 'add', word, entry_id: res.data?.entry_id, english: english.trim(), grammar: grammar.trim(), definition: definition.trim() })
      }
      onClose()
    } catch (e) {
      setError(errorMessage(e, 'Could not save the entry'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      size="lg"
      title={
        <Group gap="xs">
          {mode === 'edit' ? <IconPencil size={18} /> : <IconPlus size={18} />}
          <Text fw={700} size="lg">
            {mode === 'edit' ? 'Edit' : 'Add'} <Text component="span" c="blue.7" style={{ fontFamily: 'Georgia, serif' }}>{headword}</Text>
          </Text>
          {entry && !isVariant && <Badge variant="light" color={entry.status === 'translated' ? 'green' : 'pink'}>{entry.status === 'translated' ? 'in dictionary' : 'no translation yet'}</Badge>}
        </Group>
      }
    >
      <Stack gap="md">
        {isVariant && editable && (
          <Alert color="blue" variant="light" py="xs">
            <Text size="sm" mb={6}>
              “{word}” is in the dictionary as <strong>{entry!.variant_of}</strong>.
            </Text>
            <SegmentedControl
              size="xs"
              value={target}
              onChange={(v) => setTarget(v as 'edit' | 'add')}
              data={[
                { value: 'edit', label: `Edit “${entry!.variant_of}”` },
                { value: 'add', label: `Add “${word}” as its own entry` },
              ]}
            />
          </Alert>
        )}
        {entry && !editable && entry.entry_id && (
          <Text size="xs" c="dimmed">
            This word lives in the {entry.source} collection, which this page cannot edit. Saving adds a dictionary entry for it.
          </Text>
        )}
        <TextInput
          label="English translation"
          required
          value={english}
          onChange={(e) => setEnglish(e.currentTarget.value)}
          placeholder="e.g. to love, to care for"
          data-autofocus
        />
        <Autocomplete
          label="Grammar type"
          required
          value={grammar}
          onChange={setGrammar}
          data={GRAMMAR_OPTIONS}
          placeholder="verb, noun, adjective…"
        />
        <Textarea
          label="Definition"
          value={definition}
          onChange={(e) => setDefinition(e.currentTarget.value)}
          placeholder="Extended definition, usage notes"
          minRows={2}
          autosize
        />
        {mode === 'edit' && (
          <Textarea
            label="Add a note"
            value={notes}
            onChange={(e) => setNotes(e.currentTarget.value)}
            placeholder="Replaces the entry's notes field if filled"
            minRows={1}
            autosize
          />
        )}
        {mode === 'add' && example && (
          <Text size="xs" c="dimmed">
            Saved as verified, with this sentence as its example: “{example}”
          </Text>
        )}
        {error && <Alert icon={<IconAlertCircle size={16} />} color="red" py="xs">{error}</Alert>}
        <Group justify="flex-end" gap="sm">
          <Button variant="subtle" onClick={onClose}>Cancel</Button>
          <Button onClick={save} loading={busy} leftSection={mode === 'edit' ? <IconPencil size={16} /> : <IconPlus size={16} />}>
            {mode === 'edit' ? 'Save changes' : 'Add to dictionary'}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
