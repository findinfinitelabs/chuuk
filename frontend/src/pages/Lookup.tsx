import { useState } from 'react'
import { Card, Title, Text, TextInput, Select, Button, Group, Checkbox, Stack, Loader, Alert, List, Badge, Accordion } from '@mantine/core'
import { IconSearch, IconAlertCircle } from '@tabler/icons-react'
import axios from 'axios'

interface DictionaryEntry {
  chuukese_word: string
  english_translation: string
  definition?: string
  examples?: string[]
  word_type?: string
  inflection_type?: string
}

interface JWResult {
  source: string
  status: string
  url?: string
  error?: string
}

function Lookup() {
  const [word, setWord] = useState('')
  const [lang, setLang] = useState('chk')
  const [searchLocal, setSearchLocal] = useState(true)
  const [searchJW, setSearchJW] = useState(true)
  const [loading, setLoading] = useState(false)
  const [localResults, setLocalResults] = useState<DictionaryEntry[]>([])
  const [jwResults, setJwResults] = useState<JWResult[]>([])
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!word.trim()) return

    setLoading(true)
    setError('')
    setLocalResults([])
    setJwResults([])

    try {
      if (searchLocal) {
        const localResponse = await axios.get(`/api/lookup?word=${encodeURIComponent(word)}&lang=${lang}`)
        setLocalResults(localResponse.data.results || [])
      }

      if (searchJW) {
        const jwResponse = await axios.post('/api/lookup/jworg', { word, lang })
        setJwResults(jwResponse.data.results || [])
      }
    } catch (err) {
      setError('Error performing search')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const languageOptions = [
    { value: 'chk', label: 'Chuukese → English' },
    { value: 'en', label: 'English → Chuukese' },
    { value: 'es', label: 'Spanish' },
    { value: 'pt', label: 'Portuguese' },
    { value: 'fr', label: 'French' },
    { value: 'de', label: 'German' },
    { value: 'it', label: 'Italian' },
    { value: 'ja', label: 'Japanese' },
    { value: 'ko', label: 'Korean' },
    { value: 'zh', label: 'Chinese' },
  ]

  return (
    <Stack gap="lg">
      <Card withBorder>
        <Title order={2} mb="md">
          <IconSearch size={24} style={{ marginRight: 8 }} />
          Chuukese Dictionary Lookup
        </Title>
        <Text color="dimmed" mb="lg">
          Search for Chuukese words and phrases in your uploaded dictionary database. Results include translations, definitions, examples, and related words.
        </Text>

        <form onSubmit={handleSubmit}>
          <Group grow mb="md">
            <TextInput
              label="Chuukese Word or English Translation"
              placeholder="Enter Chuukese word (e.g., 'mwochen') or English translation..."
              value={word}
              onChange={(e) => setWord(e.target.value)}
              required
              description="Search works in both Chuukese and English"
            />
            <Select
              label="Search Language"
              data={languageOptions}
              value={lang}
              onChange={(value) => setLang(value || 'chk')}
            />
          </Group>

          <Group mb="md">
            <Checkbox
              label="Search Local Dictionary Database"
              checked={searchLocal}
              onChange={(e) => setSearchLocal(e.currentTarget.checked)}
            />
            <Checkbox
              label="Search JW.org Resources"
              checked={searchJW}
              onChange={(e) => setSearchJW(e.currentTarget.checked)}
            />
          </Group>

          <Button type="submit" loading={loading} leftSection={<IconSearch size={16} />}>
            Lookup
          </Button>
        </form>
      </Card>

      {error && (
        <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
          {error}
        </Alert>
      )}

      {localResults.length > 0 && (
        <Card withBorder>
          <Title order={3} mb="md">Dictionary Database Results</Title>
          <Stack gap="md">
            {localResults.map((entry, index) => (
              <Card key={index} withBorder>
                <Group mb="xs">
                  <Badge color="blue">CHK</Badge>
                  <Text fw={500}>{entry.chuukese_word}</Text>
                </Group>
                <Group mb="xs">
                  <Badge color="green">ENG</Badge>
                  <Text>{entry.english_translation}</Text>
                </Group>
                {entry.word_type && <Badge color="orange">{entry.word_type}</Badge>}
                {entry.definition && (
                  <Text size="sm" color="dimmed">{entry.definition}</Text>
                )}
                {entry.examples && entry.examples.length > 0 && (
                  <Accordion>
                    <Accordion.Item value="examples">
                      <Accordion.Control>Usage Examples</Accordion.Control>
                      <Accordion.Panel>
                        <List>
                          {entry.examples.map((example, i) => (
                            <List.Item key={i}>{example}</List.Item>
                          ))}
                        </List>
                      </Accordion.Panel>
                    </Accordion.Item>
                  </Accordion>
                )}
              </Card>
            ))}
          </Stack>
        </Card>
      )}

      {jwResults.length > 0 && (
        <Card withBorder>
          <Title order={3} mb="md">JW.org Search Results</Title>
          <Stack gap="md">
            {jwResults.map((result, index) => (
              <Card key={index} withBorder>
                <Title order={4}>{result.source}</Title>
                {result.status === 'success' ? (
                  <Button component="a" href={result.url} target="_blank" rel="noopener noreferrer" variant="light">
                    View Results
                  </Button>
                ) : (
                  <Alert color="red" title="Error">
                    {result.error || 'Unable to access resource'}
                  </Alert>
                )}
              </Card>
            ))}
          </Stack>
        </Card>
      )}

      {loading && (
        <Card withBorder>
          <Group justify="center">
            <Loader />
            <Text>Searching...</Text>
          </Group>
        </Card>
      )}
    </Stack>
  )
}

export default Lookup