import { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, Title, Text, TextInput, Button, Group, Stack, Loader, Alert, Badge, Grid, Select, ScrollArea } from '@mantine/core'
import { IconSearch, IconAlertCircle, IconBook } from '@tabler/icons-react'
import axios from 'axios'
import type { ReactElement } from 'react'

interface DictionaryEntry {
  _id?: string
  chuukese_word: string
  english_translation: string
  definition?: string
  examples?: string[]
  word_type?: string
  type?: string
  grammar?: string
  inflection_type?: string
  search_direction?: string
  primary_language?: string
  secondary_language?: string
  scripture?: string
  confidence_score?: number
}

function Lookup() {
  const [searchParams] = useSearchParams()
  const [word, setWord] = useState('')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<DictionaryEntry[]>([])
  const [error, setError] = useState('')
  const [filterType, setFilterType] = useState<string>('')
  const [filterGrammar, setFilterGrammar] = useState<string>('')
  const [filterScripture, setFilterScripture] = useState<string>('')
  const searchInputRef = useRef<HTMLInputElement>(null)

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
    setResults([])

    try {
      const response = await axios.get(`/api/lookup?word=${encodeURIComponent(searchWord)}&limit=100`)
      setResults(response.data.results || [])
    } catch (err) {
      setError('Error performing search')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const highlightText = (text: string, searchTerm: string): ReactElement => {
    if (!searchTerm.trim() || !text) return <>{text || ''}</>
    
    const regex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
    const parts = text.split(regex)
    
    return (
      <>
        {parts.map((part, i) => 
          regex.test(part) ? (
            <span key={i} style={{ backgroundColor: '#fff3cd', fontWeight: 600 }}>{part}</span>
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

  const insertAccent = (char: string) => {
    const input = searchInputRef.current
    if (!input) return

    const start = input.selectionStart || 0
    const end = input.selectionEnd || 0
    const text = word
    const newText = text.substring(0, start) + char + text.substring(end)
    
    setWord(newText)
    
    setTimeout(() => {
      input.focus()
      input.setSelectionRange(start + 1, start + 1)
    }, 0)
  }

  const handleLetterClick = (letter: string) => {
    setWord(letter)
    performSearch(letter)
  }

  // Chuukese alphabet letters
  const chuukeseLetters = [
    'A', 'Á', 'E', 'É', 'I', 'Í', 'O', 'Ó', 'U', 'Ú',
    'Ch', 'F', 'K', 'M', 'N', 'Ng', 'P', 'Pw', 'R', 'S', 'T', 'W'
  ]

  // Accent characters for insertion
  const accentChars = [
    'á', 'à', 'â', 'ä', 'ã',
    'é', 'è', 'ê', 'ë',
    'í', 'ì', 'î', 'ï',
    'ó', 'ò', 'ô', 'ö', 'õ',
    'ú', 'ù', 'û', 'ü',
    'ñ', 'ç'
  ]

  // Filter results
  const filteredResults = results.filter(entry => {
    if (filterType && entry.type !== filterType) return false
    if (filterGrammar && entry.grammar !== filterGrammar) return false
    if (filterScripture) {
      if (filterScripture === 'has_scripture' && !entry.scripture) return false
      if (filterScripture === 'no_scripture' && entry.scripture) return false
    }
    return true
  })

  // Separate words from phrases
  const isPhrase = (entry: DictionaryEntry) => {
    const text = entry.chuukese_word || ''
    return text.includes(' ') || entry.type === 'phrase' || entry.type === 'sentence'
  }

  const wordResults = filteredResults.filter(e => !isPhrase(e)).sort((a, b) => 
    (a.chuukese_word || '').toLowerCase().localeCompare((b.chuukese_word || '').toLowerCase())
  )
  
  const phraseResults = filteredResults.filter(e => isPhrase(e)).sort((a, b) => 
    (a.chuukese_word || '').toLowerCase().localeCompare((b.chuukese_word || '').toLowerCase())
  )

  // Get unique filter options from results
  const typeOptions = [...new Set(results.map(r => r.type).filter(Boolean))]
  const grammarOptions = [...new Set(results.map(r => r.grammar).filter(Boolean))]

  const renderResultCard = (entry: DictionaryEntry, index: number, darkMode = false) => (
    <Card key={entry._id || index} withBorder p="sm" style={{ width: '100%' }} bg={darkMode ? 'dark.5' : undefined}>
      {/* Header row with grammar badge on right */}
      <Group justify="space-between" align="flex-start" mb="xs">
        <Group gap="xs" wrap="nowrap" align="flex-start" style={{ flex: 1 }}>
          <Badge color="blue" size="sm" style={{ width: 70, flexShrink: 0, textAlign: 'center' }}>Chuukese</Badge>
          <Text fw={600} size="sm" c={darkMode ? 'white' : undefined} style={{ textAlign: 'left' }}>{highlightText(entry.chuukese_word, word)}</Text>
        </Group>
        {entry.grammar && (
          <Badge color="orange" size="xs">{entry.grammar}</Badge>
        )}
      </Group>
      
      {/* English translation */}
      <Group gap="xs" wrap="nowrap" align="flex-start" mb="xs">
        <Badge color="green" size="sm" style={{ width: 70, flexShrink: 0, textAlign: 'center' }}>English</Badge>
        <Text size="sm" c={darkMode ? 'white' : undefined} style={{ textAlign: 'left' }}>{highlightText(entry.english_translation, word)}</Text>
      </Group>
      
      {/* Definition */}
      {entry.definition && (
        <Group gap="xs" wrap="nowrap" align="flex-start" mb="xs">
          <Badge color="gray" size="xs" variant="light" style={{ width: 70, flexShrink: 0, textAlign: 'center' }}>Definition</Badge>
          <Text size="xs" c={darkMode ? 'gray.4' : 'dimmed'} style={{ textAlign: 'left' }}>{highlightText(entry.definition, word)}</Text>
        </Group>
      )}
      
      {/* Examples */}
      {entry.examples && entry.examples.length > 0 && (
        <Group gap="xs" wrap="nowrap" align="flex-start" mb="xs">
          <Badge color="violet" size="xs" variant="light" style={{ width: 70, flexShrink: 0, textAlign: 'center' }}>Examples</Badge>
          <Stack gap={2} style={{ textAlign: 'left' }}>
            {entry.examples.map((example, i) => (
              <Text key={i} size="xs" c={darkMode ? 'gray.3' : 'dimmed'}>• {example}</Text>
            ))}
          </Stack>
        </Group>
      )}
      
      {/* Scripture reference - always last */}
      {entry.scripture && (
        <Group gap="xs" wrap="nowrap" align="flex-start" mt="xs">
          <Badge color="blue" size="xs" variant="light" style={{ width: 70, flexShrink: 0, textAlign: 'center' }} leftSection={<IconBook size={10} />}>Scripture</Badge>
          <Text size="xs" c={darkMode ? 'blue.3' : 'blue'} style={{ textAlign: 'left' }}>{entry.scripture}</Text>
        </Group>
      )}
    </Card>
  )

  return (
    <Stack gap="lg">
      <Card withBorder>
        <Title order={2} mb="md">
          <IconSearch size={24} className="title-icon" />
          Chuukese Dictionary Lookup
        </Title>
        <Text c="dimmed" mb="lg">
          Search for Chuukese words and phrases. Results include translations, definitions, examples, and scripture references.
        </Text>

        <form onSubmit={handleSubmit}>
          <TextInput
            ref={searchInputRef}
            label="Search Dictionary"
            placeholder="Enter Chuukese word or English translation..."
            value={word}
            onChange={(e) => setWord(e.target.value)}
            description="Searches both Chuukese and English"
            mb="sm"
          />

          {/* Chuukese alphabet letters */}
          <Text size="xs" c="dimmed" mb="xs">Chuukese Letters:</Text>
          <Group gap={4} mb="sm">
            {chuukeseLetters.map((letter) => (
              <Button
                key={letter}
                size="xs"
                variant="light"
                color="blue"
                onClick={() => handleLetterClick(letter.toLowerCase())}
                style={{ minWidth: 32, padding: '0 6px' }}
              >
                {letter}
              </Button>
            ))}
          </Group>

          {/* Accent buttons */}
          <Text size="xs" c="dimmed" mb="xs">Insert Accents:</Text>
          <Group gap={4} mb="md">
            {accentChars.map((char) => (
              <Button
                key={char}
                size="xs"
                variant="outline"
                onClick={() => insertAccent(char)}
                style={{ minWidth: 28, padding: '0 4px' }}
              >
                {char}
              </Button>
            ))}
          </Group>

          <Button type="submit" loading={loading} leftSection={<IconSearch size={16} />}>
            Search
          </Button>
        </form>
      </Card>

      {/* Filters */}
      {results.length > 0 && (
        <Card withBorder>
          <Group gap="md">
            <Text size="sm" fw={500}>Filters:</Text>
            <Select
              placeholder="Type"
              value={filterType}
              onChange={(value) => setFilterType(value || '')}
              data={typeOptions.map(t => ({ value: t!, label: t! }))}
              clearable
              size="xs"
              style={{ width: 120 }}
            />
            <Select
              placeholder="Grammar"
              value={filterGrammar}
              onChange={(value) => setFilterGrammar(value || '')}
              data={grammarOptions.map(g => ({ value: g!, label: g! }))}
              clearable
              size="xs"
              style={{ width: 120 }}
            />
            <Select
              placeholder="Scripture"
              value={filterScripture}
              onChange={(value) => setFilterScripture(value || '')}
              data={[
                { value: 'has_scripture', label: 'Has Scripture' },
                { value: 'no_scripture', label: 'No Scripture' }
              ]}
              clearable
              size="xs"
              style={{ width: 140 }}
            />
            {(filterType || filterGrammar || filterScripture) && (
              <Button
                size="xs"
                variant="subtle"
                color="gray"
                onClick={() => {
                  setFilterType('')
                  setFilterGrammar('')
                  setFilterScripture('')
                }}
              >
                Clear filters
              </Button>
            )}
            <Text size="xs" c="dimmed" ml="auto">
              {filteredResults.length} results ({wordResults.length} words, {phraseResults.length} phrases)
            </Text>
          </Group>
        </Card>
      )}

      {error && (
        <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
          {error}
        </Alert>
      )}

      {loading && (
        <Card withBorder>
          <Group justify="center">
            <Loader />
            <Text>Searching...</Text>
          </Group>
        </Card>
      )}

      {/* Results - Split View */}
      {filteredResults.length > 0 && !loading && (
        <Grid gutter="md">
          {/* Words Column */}
          <Grid.Col span={{ base: 12, md: 6 }}>
            <Card withBorder h="100%">
              <Title order={4} mb="md">
                <Badge color="blue" size="lg" mr="sm">{wordResults.length}</Badge>
                Words
              </Title>
              <ScrollArea h={600} offsetScrollbars>
                <Stack gap="sm">
                  {wordResults.length > 0 ? (
                    wordResults.map((entry, index) => renderResultCard(entry, index))
                  ) : (
                    <Text c="dimmed" ta="center" py="xl">No word matches found</Text>
                  )}
                </Stack>
              </ScrollArea>
            </Card>
          </Grid.Col>

          {/* Phrases Column */}
          <Grid.Col span={{ base: 12, md: 6 }}>
            <Card withBorder h="100%">
              <Title order={4} mb="md">
                <Badge color="teal" size="lg" mr="sm" style={{ color: 'white' }}>{phraseResults.length}</Badge>
                Phrases & Sentences
              </Title>
              <ScrollArea h={600} offsetScrollbars>
                <Stack gap="sm">
                  {phraseResults.length > 0 ? (
                    phraseResults.map((entry, index) => renderResultCard(entry, index))
                  ) : (
                    <Text c="dimmed" ta="center" py="xl">No phrase matches found</Text>
                  )}
                </Stack>
              </ScrollArea>
            </Card>
          </Grid.Col>
        </Grid>
      )}

      {/* No results message */}
      {!loading && results.length === 0 && word && (
        <Card withBorder>
          <Text ta="center" c="dimmed" py="xl">
            No results found for "{word}". Try a different search term or browse by letter.
          </Text>
        </Card>
      )}
    </Stack>
  )
}

export default Lookup