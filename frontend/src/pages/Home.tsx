import { useEffect, useState } from 'react'
import { Card, Title, Text, Button, Group, Grid, List, ThemeIcon, Stack, Badge, Container } from '@mantine/core'
import { IconEye, IconWorld, IconDatabase, IconPlus, IconSearch, IconLanguage } from '@tabler/icons-react'
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
      .then(response => setPublications(response.data))
      .catch(error => console.error('Error fetching publications:', error))
  }, [])

  return (
    <Container size="lg">
      <Stack gap="xl">
        {/* Hero Section */}
        <Card withBorder radius="lg" p="xl" className="dictionary-card">
          <Group align="center" mb="lg">
            <ThemeIcon size={60} radius="lg">
              <IconLanguage size={32} />
            </ThemeIcon>
            <div>
              <Title order={1} size="h1">
                🏝️ Chuuk AI Language Dictionary
              </Title>
              <Text size="xl" c="gray.7" mt="sm">
                Advanced AI tools for digitizing Chuukese language resources
              </Text>
            </div>
          </Group>

          <Text size="lg" c="gray.7" mb="md">
            This tool helps linguists and community members digitize 
            Chuukese dictionary pages using AI technology.
          </Text>

          <Group gap="md" mt="xl">
            <Button 
              size="md" 
              component={Link} 
              to="/publications/new"
              leftSection={<IconPlus size={18} />}
            >
              Start New Project
            </Button>
            <Button 
              size="md" 
              component={Link} 
              to="/lookup"
              leftSection={<IconSearch size={18} />}
              variant="outline"
            >
              Search Dictionary
            </Button>
          </Group>
        </Card>

        {/* Features Grid */}
        <Grid>
          <Grid.Col span={{ base: 12, md: 6 }}>
            <Card withBorder radius="md" p="lg" h="100%" className="dictionary-card">
              <Group align="center" mb="md">
                <ThemeIcon color="blue" size={40} radius="md">
                  <IconEye size={20} />
                </ThemeIcon>
                <Title order={3}>AI Text Processing</Title>
              </Group>
              <Text c="gray.7" mb="md">
                Advanced AI text recognition with Google Vision API 
                for Chuukese texts and handwritten content.
              </Text>
              <Badge color="blue" variant="light">AI-Powered</Badge>
            </Card>
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 6 }}>
            <Card withBorder radius="md" p="lg" h="100%" className="dictionary-card">
              <Group align="center" mb="md">
                <ThemeIcon color="teal" size={40} radius="md">
                  <IconWorld size={20} />
                </ThemeIcon>
                <Title order={3}>JW.org Integration</Title>
              </Group>
              <Text c="gray.7" mb="md">
                Cross-reference with JW.org Chuukese publications for 
                cultural context and usage examples.
              </Text>
              <Badge color="teal" variant="light">Cultural Context</Badge>
            </Card>
          </Grid.Col>
        </Grid>

        {/* Recent Publications */}
        {publications.length > 0 && (
          <Card withBorder radius="md" p="lg">
            <Group justify="space-between" align="center" mb="md">
              <Title order={2}>Recent Publications</Title>
              <Button 
                variant="outline" 
                size="sm" 
                component={Link} 
                to="/publications"
              >
                View All
              </Button>
            </Group>
            <Grid>
              {publications.slice(0, 3).map((publication) => (
                <Grid.Col key={publication.id} span={{ base: 12, sm: 6, md: 4 }}>
                  <Card withBorder p="md" radius="md" className="dictionary-card">
                    <Title order={4} mb="sm">
                      {publication.title}
                    </Title>
                    <Text c="gray.6" size="sm" mb="md">
                      {publication.description || 'Dictionary publication'}
                    </Text>
                    <Group justify="space-between">
                      <Text size="xs" c="gray.5">
                        {new Date(publication.created_date).toLocaleDateString()}
                      </Text>
                      {publication.page_count && (
                        <Badge size="sm" color="gray" variant="light">
                          {publication.page_count} pages
                        </Badge>
                      )}
                    </Group>
                  </Card>
                </Grid.Col>
              ))}
            </Grid>
          </Card>
        )}

        {/* Getting Started */}
        <Card withBorder radius="md" p="lg">
          <Title order={2} mb="md">Getting Started</Title>
          <List spacing="md">
            <List.Item icon={<ThemeIcon color="blue" size={24} radius="xl"><IconPlus size={16} /></ThemeIcon>}>
              <Text><strong>Upload Publication:</strong> Start by uploading a dictionary publication</Text>
            </List.Item>
            <List.Item icon={<ThemeIcon color="green" size={24} radius="xl"><IconEye size={16} /></ThemeIcon>}>
              <Text><strong>AI Text Processing:</strong> Extract text with high accuracy for Chuukese characters</Text>
            </List.Item>
            <List.Item icon={<ThemeIcon color="teal" size={24} radius="xl"><IconWorld size={16} /></ThemeIcon>}>
              <Text><strong>Cross-Reference:</strong> Match words with JW.org resources</Text>
            </List.Item>
            <List.Item icon={<ThemeIcon color="orange" size={24} radius="xl"><IconDatabase size={16} /></ThemeIcon>}>
              <Text><strong>Organize:</strong> Store and search your digitized dictionary entries</Text>
            </List.Item>
          </List>
        </Card>
      </Stack>
    </Container>
  )
}

export default Home