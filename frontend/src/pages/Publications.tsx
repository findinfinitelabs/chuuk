import { useEffect, useState } from 'react'
import { Card, Title, Text, Button, Grid, Group } from '@mantine/core'
import { IconBooks, IconPlus } from '@tabler/icons-react'
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
    </div>
  )
}

export default Publications