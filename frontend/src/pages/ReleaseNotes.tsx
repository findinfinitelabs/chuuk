import { Container, Stack, Title, Text, Card, Group, Badge, List, Anchor } from '@mantine/core'
import { IconArrowLeft } from '@tabler/icons-react'
import { Link } from 'react-router-dom'
import releases from '../data/releases.json'

/** Shape of one entry in src/data/releases.json. */
export interface Release {
  version: string
  date: string
  title?: string
  notes: string[]
}

export const RELEASES: Release[] = releases.releases
export const CURRENT_VERSION = RELEASES[0]?.version ?? '0.0.0.0'

function formatDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`)
  return isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })
}

/** Release notes, one card per deployed version, newest first. */
export default function ReleaseNotes() {
  return (
    <Container size="md">
      <Stack gap="lg">
        <div>
          <Anchor component={Link} to="/" size="sm">
            <Group gap={4}>
              <IconArrowLeft size={14} /> Home
            </Group>
          </Anchor>
          <Title order={1} mt="xs">Release Notes</Title>
          <Text c="gray.7">
            Current version <Badge variant="light" size="lg">{CURRENT_VERSION}</Badge>
          </Text>
        </div>

        {RELEASES.map((r) => (
          <Card key={r.version} withBorder radius="md" p="lg" className="dictionary-card">
            <Group justify="space-between" align="baseline" mb="sm">
              <Group gap="sm" align="baseline">
                <Title order={3}>v{r.version}</Title>
                {r.title && <Text c="gray.7">{r.title}</Text>}
              </Group>
              <Text size="sm" c="gray.6">Deployed {formatDate(r.date)}</Text>
            </Group>
            <List spacing="xs" size="sm">
              {r.notes.map((n, i) => (
                <List.Item key={i}>{n}</List.Item>
              ))}
            </List>
          </Card>
        ))}
      </Stack>
    </Container>
  )
}
