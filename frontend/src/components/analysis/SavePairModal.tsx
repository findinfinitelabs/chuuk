/**
 * SavePairModal — record the confirmed English for a Chuukese sentence as a
 * training pair. Prefilled with the exact text found on wol.jw.org when there
 * is one, otherwise typed in. Saved pairs go where the Translation Game's
 * confirmed matches go, so the retraining scripts use them.
 */
import { useEffect, useState } from 'react'
import { Modal, Stack, Group, Text, Textarea, Button, Alert, Badge, Anchor } from '@mantine/core'
import { IconAlertCircle, IconDeviceFloppy, IconExternalLink } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import axios from 'axios'
import styles from './analysis.module.css'

export interface PairSource {
  source: 'wol.jw.org' | 'user'
  citation?: string | null
  link?: string | null
  title?: string | null
}

function errorMessage(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) return e.response?.data?.error || fallback
  return fallback
}

export function SavePairModal({
  opened, onClose, chuukese, english, origin, onSaved,
}: {
  opened: boolean
  onClose: () => void
  chuukese: string
  /** Starting English: the WOL text, or empty to type one. */
  english: string
  origin: PairSource
  onSaved?: (english: string) => void
}) {
  const [text, setText] = useState(english)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (opened) { setText(english); setError('') }
  }, [opened, english])

  const edited = text.trim() !== english.trim()
  const source: PairSource['source'] = origin.source === 'wol.jw.org' && !edited ? 'wol.jw.org' : 'user'

  const save = async () => {
    if (!text.trim()) { setError('Enter the English translation'); return }
    setBusy(true)
    setError('')
    try {
      await axios.post('/api/sentences/pairs', {
        chuukese,
        english: text.trim(),
        source,
        citation: origin.citation || undefined,
        link: origin.link || undefined,
        title: origin.title || undefined,
      })
      notifications.show({ title: 'Translation saved', message: 'Stored as a confirmed sentence pair for training.', color: 'teal' })
      onSaved?.(text.trim())
      onClose()
    } catch (e) {
      setError(errorMessage(e, 'Could not save the pair'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} size="lg" title={<Text fw={700}>Save the translation of this sentence</Text>}>
      <Stack gap="md">
        <Text className={styles.sentence}>{chuukese}</Text>
        <Textarea
          label="English"
          value={text}
          onChange={(e) => setText(e.currentTarget.value)}
          minRows={2}
          autosize
          data-autofocus
        />
        <Group gap="xs" wrap="wrap">
          <Badge variant="light" color={source === 'wol.jw.org' ? 'teal' : 'gray'} size="sm">
            {source === 'wol.jw.org' ? 'exact text from wol.jw.org' : edited && origin.source === 'wol.jw.org' ? 'edited from the WOL text' : 'typed in'}
          </Badge>
          {origin.citation && <Text size="xs" c="dimmed" className={styles.citation}>{origin.citation}</Text>}
          {origin.link && (
            <Anchor href={origin.link} target="_blank" rel="noopener noreferrer" size="xs">
              <Group gap={4} wrap="nowrap"><IconExternalLink size={12} />Open source</Group>
            </Anchor>
          )}
        </Group>
        {error && <Alert icon={<IconAlertCircle size={16} />} color="red" py="xs">{error}</Alert>}
        <Group justify="flex-end" gap="sm">
          <Button variant="subtle" onClick={onClose}>Cancel</Button>
          <Button onClick={save} loading={busy} leftSection={<IconDeviceFloppy size={16} />} disabled={!text.trim()}>
            Save as confirmed pair
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
