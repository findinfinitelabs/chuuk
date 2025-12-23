import { useEffect, useState } from 'react'
import { Card, Title, Text, Button, Group, Grid, List, ThemeIcon, Stack } from '@mantine/core'
import { IconHome, IconBook, IconEye, IconWorld, IconDatabase, IconPlus, IconSearch } from '@tabler/icons-react'
import { Link } from 'react-router-dom'
import axios from 'axios'

interface Publication {
  id: string
  title: string
  description?: string
  created_date: string
  page_count?: number
}

function Home() {
  const [publications, setPublications] = useState<Publication[]>([])

  useEffect(() => {
    axios.get('/api/publications')
      .then(response => {
        // Ensure response.data is an array
        const data = Array.isArray(response.data) ? response.data : response.data.publications || []
        setPublications(data)
      })
      .catch(error => console.error('Error fetching publications:', error))
  }, [])

  return (
    <Stack gap="lg">
      <Card withBorder>
        <Title order={2} mb="md">
          <IconHome size={24} style={{ marginRight: 8 }} />
          Welcome to the Chuuk Dictionary AI Copilot
        </Title>
        <Text size="lg" mb="md">
          This tool helps you digitize and cross-reference Chuukese dictionary pages using advanced AI technology and online resources.
        </Text>

        <Title order={3} mb="sm">Features:</Title>
        <List spacing="sm" mb="lg">
          <List.Item icon={<ThemeIcon color="blue" size={24} radius="xl"><IconBook size={16} /></ThemeIcon>}>
            Upload and manage dictionary publications (400+ pages)
          </List.Item>
          <List.Item icon={<ThemeIcon color="green" size={24} radius="xl"><IconEye size={16} /></ThemeIcon>}>
            OCR processing using Tesseract and Google Vision API
          </List.Item>
          <List.Item icon={<ThemeIcon color="teal" size={24} radius="xl"><IconWorld size={16} /></ThemeIcon>}>
            Cross-reference words with JW.org Chuukese resources
          </List.Item>
          <List.Item icon={<ThemeIcon color="orange" size={24} radius="xl"><IconDatabase size={16} /></ThemeIcon>}>
            Store and organize your digitized content
          </List.Item>
        </List>

        <Group>
          <Button component={Link} to="/publications/new" leftSection={<IconPlus size={16} />} color="green">
            Create New Publication
          </Button>
          <Button component={Link} to="/lookup" leftSection={<IconSearch size={16} />} variant="outline">
            Lookup Words
          </Button>
        </Group>
      </Card>

      {publications.length > 0 && (
        <Card withBorder>
          <Title order={2} mb="md">Your Publications</Title>
          <Grid>
            {publications.map((pub) => (
              <Grid.Col key={pub.id} span={4}>
                <Card withBorder shadow="sm" component={Link} to={`/publications/${pub.id}`} style={{ textDecoration: 'none' }}>
                  <Title order={5}>{pub.title}</Title>
                  {pub.description && <Text size="sm" color="dimmed">{pub.description}</Text>}
                  <Text size="xs" mt="sm">Created: {new Date(pub.created_date).toLocaleDateString()}</Text>
                  {pub.page_count && <Text size="xs">Pages: {pub.page_count}</Text>}
                </Card>
              </Grid.Col>
            ))}
          </Grid>
        </Card>
      )}
    </Stack>
  )
}

export default Home