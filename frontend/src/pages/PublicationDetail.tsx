import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Title, Text, Button, Group, Stack, Grid, Badge, Loader, Alert } from '@mantine/core'
import { IconUpload, IconFileText, IconAlertCircle } from '@tabler/icons-react'
import axios from 'axios'

interface Page {
  id: string
  filename: string
  ocr_text?: string
  processed: boolean
}

interface Publication {
  id: string
  title: string
  description?: string
  created_date: string
  pages: Page[]
}

function PublicationDetail() {
  const { id } = useParams<{ id: string }>()
  const [publication, setPublication] = useState<Publication | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (id) {
      axios.get(`/api/publications/${id}`)
        .then(response => {
          setPublication(response.data)
          setLoading(false)
        })
        .catch(() => {
          setError('Failed to load publication')
          setLoading(false)
        })
    }
  }, [id])

  if (loading) {
    return <Loader />
  }

  if (error || !publication) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
        {error || 'Publication not found'}
      </Alert>
    )
  }

  return (
    <Stack gap="lg">
      <Card withBorder>
        <Title order={2} mb="sm">{publication.title}</Title>
        {publication.description && <Text color="dimmed">{publication.description}</Text>}
        <Text size="sm" mt="sm">Created: {new Date(publication.created_date).toLocaleDateString()}</Text>
      </Card>

      <Card withBorder>
        <Group justify="space-between" mb="md">
          <Title order={3}>Pages ({publication.pages.length})</Title>
          <Button leftSection={<IconUpload size={16} />}>
            Upload Pages
          </Button>
        </Group>

        {publication.pages.length === 0 ? (
          <Text color="dimmed" ta="center">
            No pages uploaded yet. Click "Upload Pages" to add dictionary pages.
          </Text>
        ) : (
          <Grid>
            {publication.pages.map((page) => (
              <Grid.Col key={page.id} span={6}>
                <Card withBorder>
                  <Group justify="space-between">
                    <div>
                      <Text fw={500}>{page.filename}</Text>
                      <Badge color={page.processed ? 'green' : 'yellow'}>
                        {page.processed ? 'Processed' : 'Pending'}
                      </Badge>
                    </div>
                    <IconFileText size={20} />
                  </Group>
                  {page.ocr_text && (
                    <Text size="sm" color="dimmed" mt="xs" lineClamp={2}>
                      {page.ocr_text}
                    </Text>
                  )}
                </Card>
              </Grid.Col>
            ))}
          </Grid>
        )}
      </Card>
    </Stack>
  )
}

export default PublicationDetail