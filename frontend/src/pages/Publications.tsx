import { useEffect, useState } from 'react'
import { Card, Title, Text, Button, Grid, Group, List, ThemeIcon, Divider } from '@mantine/core'
import { IconBooks, IconPlus, IconEye, IconWorld, IconDatabase } from '@tabler/icons-react'
import { Link } from 'react-router-dom'
import axios from 'axios'

interface Publication {
  id: string
  title: string
  description?: string
  created_date: string
  page_count?: number
}

function Publications() {
  const [publications, setPublications] = useState<Publication[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    axios.get('/api/publications')
      .then(response => {
        setPublications(response.data)
        setLoading(false)
      })
      .catch(error => {
        console.error('Error fetching publications:', error)
        setLoading(false)
      })
  }, [])

  if (loading) {
    return <Text>Loading publications...</Text>
  }

  return (
    <div>
      <Group justify="space-between" mb="lg">
        <Title order={2}>
          <IconBooks size={24} style={{ marginRight: 8 }} />
          Publications
        </Title>
        <Button component={Link} to="/publications/new" leftSection={<IconPlus size={16} />}>
          New Publication
        </Button>
      </Group>

      {publications.length === 0 ? (
        <Card withBorder>
          <Text ta="center" color="dimmed">
            No publications yet. <Button component={Link} to="/publications/new" variant="link">Create your first publication</Button>
          </Text>
        </Card>
      ) : (
        <Grid>
          {publications.map((pub) => (
            <Grid.Col key={pub.id} span={4}>
              <Card withBorder shadow="sm" component={Link} to={`/publications/${pub.id}`} className="link-no-decoration">
                <Title order={4}>{pub.title}</Title>
                {pub.description && <Text size="sm" color="dimmed">{pub.description}</Text>}
                <Text size="xs" mt="sm">Created: {new Date(pub.created_date).toLocaleDateString()}</Text>
                {pub.page_count && <Text size="xs">Pages: {pub.page_count}</Text>}
              </Card>
            </Grid.Col>
          ))}
        </Grid>
      )}

      <Divider my="xl" />

      {/* Getting Started */}
      <Card withBorder radius="md" p="lg">
        <Title order={2} mb="md">Getting Started</Title>
        <List spacing="md">
          <List.Item icon={<ThemeIcon color="#4A6DA7" size={24} radius="xl"><IconPlus size={16} /></ThemeIcon>}>
            <Text><strong>Upload Publication:</strong> Start by uploading a dictionary publication</Text>
          </List.Item>
          <List.Item icon={<ThemeIcon color="#4A6DA7" size={24} radius="xl"><IconEye size={16} /></ThemeIcon>}>
            <Text><strong>AI Text Processing:</strong> Extract text with high accuracy for Chuukese characters</Text>
          </List.Item>
          <List.Item icon={<ThemeIcon color="#4A6DA7" size={24} radius="xl"><IconWorld size={16} /></ThemeIcon>}>
            <Text><strong>Cross-Reference:</strong> Match words with JW.org resources</Text>
          </List.Item>
          <List.Item icon={<ThemeIcon color="#4A6DA7" size={24} radius="xl"><IconDatabase size={16} /></ThemeIcon>}>
            <Text><strong>Organize:</strong> Store and search your digitized dictionary entries</Text>
          </List.Item>
        </List>
      </Card>
    </div>
  )
}

export default Publications