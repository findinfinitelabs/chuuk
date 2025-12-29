import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, Title, Text, TextInput, Button, Group, Stack, Loader, Alert, List, Badge, Accordion } from '@mantine/core'
import { IconSearch, IconAlertCircle } from '@tabler/icons-react'
import axios from 'axios'
import type { ReactElement } from 'react'

interface DictionaryEntry {
  chuukese_word: string
  english_translation: string
  definition?: string
  examples?: string[]
  word_type?: string
  inflection_type?: string
  search_direction?: string
  primary_language?: string
  secondary_language?: string
}

function Lookup() {
  const [searchParams] = useSearchParams()
  const [word, setWord] = useState('')
  const [loading, setLoading] = useState(false)
  const [localResults, setLocalResults] = useState<DictionaryEntry[]>([])
  const [error, setError] = useState('')

  // Check for query parameter and auto-search
  useEffect(() => {
    const queryParam = searchParams.get('q')
    if (queryParam) {
      setWord(queryParam)
      performSearch(queryParam)
    }
  }, [searchParams])

  const performSearch = async (searchWord: string) => {
    if (!searchWord.trim()) return

    setLoading(true)
    setError('')
    setLocalResults([])

    try {
      const localResponse = await axios.get(`/api/lookup?word=${encodeURIComponent(searchWord)}`)
      setLocalResults(localResponse.data.results || [])
    } catch (err) {
      setError('Error performing search')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const highlightText = (text: string, searchTerm: string): ReactElement => {
    if (!searchTerm.trim()) return <>{text}</>
    
    const regex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
    const parts = text.split(regex)
    
    return (
      <>
        {parts.map((part, i) => 
          regex.test(part) ? (
            <span key={i} className="search-highlight">{part}</span>
          ) : (
            <span key={i}>{part}</span>
          )
        )}
      </>
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    performSearch(word)
  }

  return (
    <Stack gap="lg">
      <Card withBorder>
        <Title order={2} mb="md">
          <IconSearch size={24} className="title-icon" />
          Chuukese Dictionary Lookup
        </Title>
        <Text color="dimmed" mb="lg">
          Search for Chuukese words and phrases in your uploaded dictionary database. Results include translations, definitions, examples, and related words.
        </Text>

        <form onSubmit={handleSubmit}>
          <TextInput
            label="Search Dictionary"
            placeholder="Enter Chuukese word or English translation..."
            value={word}
            onChange={(e) => setWord(e.target.value)}
            required
            description="Searches both Chuukese and English - results shown in table below"
            mb="md"
          />

          <Button type="submit" loading={loading} leftSection={<IconSearch size={16} />}>
            Search
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
          <Stack gap="md" align="flex-start">
            {localResults.map((entry, index) => (
              <Card key={index} withBorder style={{ width: '100%' }}>
                <Group mb="xs" wrap="nowrap" align="flex-start">
                  <Badge color="blue">Chuukese</Badge>
                  <Text fw={500}>{highlightText(entry.chuukese_word, word)}</Text>
                </Group>
                <Group mb="xs" wrap="nowrap" align="flex-start">
                  <Badge color="green">English</Badge>
                  <Text>{highlightText(entry.english_translation, word)}</Text>
                </Group>
                {entry.word_type && (
                  <Group mb="xs" wrap="nowrap" align="flex-start">
                    <Badge color="orange">{entry.word_type}</Badge>
                  </Group>
                )}
                {entry.definition && (
                  <>
                    <Group mb="xs" wrap="nowrap" align="flex-start">
                      <Badge color="gray" variant="light">Word Breakdown</Badge>
                      <Text size="sm" color="dimmed">{highlightText(entry.definition, word)}</Text>
                    </Group>
                  </>
                )}
                <Group gap="xs">
                  {entry.search_direction && (
                    <Badge color="violet" variant="light">
                      {entry.search_direction === 'chk_to_eng' ? 'Chk→Eng' : 'Eng→Chk'}
                    </Badge>
                  )}
                  {entry.primary_language && (
                    <Badge color="gray" variant="outline" size="sm">
                      {entry.primary_language} → {entry.secondary_language}
                    </Badge>
                  )}
                </Group>
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