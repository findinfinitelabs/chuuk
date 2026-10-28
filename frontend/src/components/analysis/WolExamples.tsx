/**
 * WolExamples — real sentences from wol.jw.org containing a word, each with
 * its English equivalent, in a drawer. Used by the analysis pages so a word's
 * usage can be checked without leaving the page.
 *
 * The fetching lives in useWolExamples; this file only renders.
 */
import { Drawer, Stack, Card, Text, Group, Badge, Anchor, Loader, Alert, Box } from '@mantine/core'
import { IconAlertCircle, IconExternalLink } from '@tabler/icons-react'
import { useWolExamples } from './useWolExamples'
import type { WolExample } from './useWolExamples'
import styles from './analysis.module.css'

export function ExampleCard({ item }: { item: WolExample }) {
  return (
    <Card withBorder padding="sm" className={styles.result}>
      {item.title && <Text fw={600} size="sm" mb={4} className={styles.title}>{item.title}</Text>}
      <Text className={styles.sentence}>
        {item.segments.map((seg, i) => seg.match
          ? <mark key={i} className={styles.hit}>{seg.text}</mark>
          : <span key={i}>{seg.text}</span>)}
      </Text>
      <Box className={styles.english}>
        {item.english === undefined ? (
          <Group gap={6}><Loader size={12} /><Text size="xs" c="dimmed">Finding the English…</Text></Group>
        ) : item.english === null ? (
          <Text size="xs" c="dimmed">No English equivalent found on WOL.</Text>
        ) : (
          <>
            <Text className={styles.englishText}>{item.english.text}</Text>
            <Group gap="xs" mt={4} wrap="wrap">
              <Badge variant="light" color="cyan" size="xs">English</Badge>
              {item.english.scope === 'paragraph' && (
                <Text size="xs" c="dimmed" fs="italic">whole paragraph — sentence could not be lined up</Text>
              )}
              {item.english.citation && <Text size="xs" c="dimmed" className={styles.citation}>{item.english.citation}</Text>}
              <Anchor href={item.english.link} target="_blank" rel="noopener noreferrer" size="xs">
                <Group gap={4} wrap="nowrap"><IconExternalLink size={12} />Open English</Group>
              </Anchor>
            </Group>
          </>
        )}
      </Box>
      <Group gap="xs" mt={6} wrap="wrap">
        {item.reference?.year && <Badge variant="light" size="xs">{item.reference.year}</Badge>}
        {item.reference?.pub && <Badge variant="outline" size="xs">{item.reference.pub}</Badge>}
        {item.citation && <Text size="xs" c="dimmed" className={styles.citation}>{item.citation}</Text>}
        {item.link && (
          <Anchor href={item.link} target="_blank" rel="noopener noreferrer" size="xs">
            <Group gap={4} wrap="nowrap"><IconExternalLink size={12} />Open on WOL</Group>
          </Anchor>
        )}
      </Group>
    </Card>
  )
}

/** Drawer listing examples of `word`; closed when `word` is null. */
export function WolExamplesDrawer({ word, onClose }: { word: string | null; onClose: () => void }) {
  const { items, total, loading, error } = useWolExamples(word)
  return (
    <Drawer
      opened={!!word}
      onClose={onClose}
      position="right"
      size="lg"
      title={
        <Group gap="xs">
          <Text fw={700}>Examples of</Text>
          <Text fw={700} c="blue.7" style={{ fontFamily: 'Georgia, serif' }}>{word}</Text>
          <Text size="sm" c="dimmed">on wol.jw.org</Text>
        </Group>
      }
    >
      {loading && <Group justify="center" py="xl"><Loader /><Text c="dimmed">Searching wol.jw.org…</Text></Group>}
      {error && <Alert icon={<IconAlertCircle size={16} />} color="red">{error}</Alert>}
      {!loading && !error && word && items.length === 0 && (
        <Text c="dimmed" ta="center" py="xl">No sentences on wol.jw.org contain “{word}”.</Text>
      )}
      {items.length > 0 && (
        <Stack gap="sm">
          <Text size="xs" c="dimmed">
            {total} sentence{total === 1 ? '' : 's'} found — showing the {items.length} newest.
          </Text>
          {items.map((item, i) => <ExampleCard key={i} item={item} />)}
        </Stack>
      )}
    </Drawer>
  )
}
