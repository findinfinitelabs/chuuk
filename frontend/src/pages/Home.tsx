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
      .then(response => {
        // Ensure response.data is an array
        const data = Array.isArray(response.data) ? response.data : response.data.publications || []
        setPublications(data)
      })
      .catch(error => console.error('Error fetching publications:', error))
  }, [])

  return (
    <Container size="lg">
      <Stack gap="xl">
        {/* Hero Section */}
        <Card withBorder radius="lg" p="xl" className="dictionary-card">
          <Group align="center" mb="lg">
            <ThemeIcon size={60} radius="lg" color="#3B1898">
              <IconLanguage size={32} />
            </ThemeIcon>
            <div>
              <Title order={1} size="h1">
                Chuuk AI Language Dictionary
              </Title>
              <Text size="xl" c="gray.7" mt="sm">
                Advanced AI tools for digitizing Chuukese language resources
              </Text>
            </div>
          </Group>

          <Group gap="md" mt="xl">
            <Button 
              size="md" 
              component={Link} 
              to="/translate"
              leftSection={<IconLanguage size={18} />}
            >
              AI Translator
            </Button>
            <Button 
              size="md" 
              component={Link} 
              to="/lookup"
              leftSection={<IconSearch size={18} />}
              variant="outline"
            >
              Lookup Word or Phrase
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
                <ThemeIcon color="#4A6DA7" size={40} radius="md">
                  <IconWorld size={20} />
                </ThemeIcon>
                <Title order={3}>JW.org Integration</Title>
              </Group>
              <Text c="gray.7" mb="md">
                Cross-reference with JW.org Chuukese publications for 
                cultural context and usage examples.
              </Text>
              <Badge color="#4A6DA7" variant="light">Cultural Context</Badge>
            </Card>
          </Grid.Col>
        </Grid>
      </Stack>
    </Container>
  )
}

export default Home