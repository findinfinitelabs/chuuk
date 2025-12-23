import { useState, useEffect, useRef } from 'react'
import { Card, Title, Text, Button, Group, Stack, Table, TextInput, Badge, Pagination, Alert, Loader, Modal, Textarea, Select, Autocomplete } from '@mantine/core'
import { IconDatabase, IconSearch, IconRefresh, IconAlertCircle, IconEdit, IconPlus, IconTrash } from '@tabler/icons-react'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import axios from 'axios'

interface DictionaryEntry {
  _id?: string
  chuukese_word: string // Can be a word or phrase
  english_translation: string // Can be a word or phrase
  definition?: string
  examples?: string[]
  word_type?: string
  inflection_type?: string
  notes?: string
  search_direction?: string
  primary_language?: string
  secondary_language?: string
}

interface DatabaseStats {
  total_entries: number
  total_chuukese_words: number // Includes phrases
  total_english_words: number // Includes phrases
  last_updated?: string
}

function Database() {
  const [entries, setEntries] = useState<DictionaryEntry[]>([])
  const [stats, setStats] = useState<DatabaseStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [error, setError] = useState('')
  const [opened, { open, close }] = useDisclosure(false)
  const [editingEntry, setEditingEntry] = useState<DictionaryEntry | null>(null)
  const [isNewEntry, setIsNewEntry] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const entriesPerPage = 20
  const searchInputRef = useRef<HTMLInputElement>(null)

  // Form state for editing
  const [formData, setFormData] = useState({
    chuukese_word: '',
    english_translation: '',
    definition: '',
    word_type: '',
    examples: [] as string[],
    notes: ''
  })

  useEffect(() => {
    loadDatabaseStats()
    loadEntries()
  }, [currentPage])

  // Live search effect
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (searchTerm) {
        setCurrentPage(1)
        loadEntries()
        loadSuggestions()
      } else {
        loadEntries()
      }
    }, 300) // Debounce for 300ms

    return () => clearTimeout(timeoutId)
  }, [searchTerm])

  const loadDatabaseStats = async () => {
    try {
      const response = await axios.get('/api/database/stats')
      setStats(response.data)
    } catch (err) {
      console.error('Failed to load database stats:', err)
    }
  }

  const loadSuggestions = async () => {
    if (!searchTerm || searchTerm.length < 2) {
      setSuggestions([])
      return
    }

    try {
      const response = await axios.get('/api/database/entries', {
        params: { search: searchTerm, limit: 10 }
      })
      const data = response.data
      if (data.entries && data.entries.length > 0) {
        // Deduplicate suggestions - multiple entries can have the same word
        const uniqueWords = [...new Set(data.entries.map((entry: DictionaryEntry) => entry.chuukese_word))] as string[]
        setSuggestions(uniqueWords)
      } else {
        setSuggestions([])
      }
    } catch (err) {
      console.error('Failed to load suggestions:', err)
      setSuggestions([])
    }
  }

  const loadEntries = async () => {
    setLoading(true)
    setError('')
    
    try {
      const params = {
        page: currentPage,
        limit: entriesPerPage,
        search: searchTerm || undefined
      }
      
      const response = await axios.get('/api/database/entries', { params })
      const data = response.data
      
      // Only show sample data if no search term and database is truly empty
      if (!data.entries || data.entries.length === 0) {
        if (!searchTerm) {
          // Show sample data only when browsing, not when searching
          const sampleEntries: DictionaryEntry[] = [
            {
              _id: 'sample1',
              chuukese_word: 'mwochen',
              english_translation: 'good, well',
              definition: 'An adjective meaning good, well, fine',
              word_type: 'adjective',
              examples: ['Mwochen an néni', 'Good morning'],
            },
            {
              _id: 'sample2', 
              chuukese_word: 'pwúpwú',
              english_translation: 'book',
              definition: 'A book, written material',
              word_type: 'noun',
              examples: ['Pwúpwú en skuul', 'School book'],
            },
            {
              _id: 'sample3',
              chuukese_word: 'wúnúmei',
              english_translation: 'thank you',
              definition: 'Expression of gratitude',
              word_type: 'interjection',
              examples: ['Wúnúmei non kewe', 'Thank you very much'],
            }
          ]
          setEntries(sampleEntries)
          setTotalPages(1)
        } else {
          // When searching and nothing found, show empty array
          setEntries([])
          setTotalPages(1)
        }
      } else {
        setEntries(data.entries || [])
        setTotalPages(Math.ceil((data.total || 0) / entriesPerPage))
      }
    } catch (err) {
      setError('Failed to load database entries')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    setCurrentPage(1)
    loadEntries()
  }

  const refreshDatabase = () => {
    setCurrentPage(1)
    loadDatabaseStats()
    loadEntries()
  }

  const openEditModal = (entry?: DictionaryEntry, preFillWord?: string) => {
    if (entry) {
      setEditingEntry(entry)
      setFormData({
        chuukese_word: entry.chuukese_word,
        english_translation: entry.english_translation,
        definition: entry.definition || '',
        word_type: entry.word_type || '',
        examples: entry.examples || [],
        notes: ''
      })
      setIsNewEntry(false)
    } else {
      setEditingEntry(null)
      setFormData({
        chuukese_word: preFillWord || '',
        english_translation: '',
        definition: '',
        word_type: '',
        examples: [],
        notes: ''
      })
      setIsNewEntry(true)
    }
    open()
  }

  const saveEntry = async () => {
    try {
      if (isNewEntry) {
        await axios.post('/api/database/entries', formData)
        notifications.show({
          title: 'Success',
          message: 'New entry created successfully',
          color: 'green'
        })
      } else if (editingEntry?._id) {
        await axios.put(`/api/database/entries/${editingEntry._id}`, formData)
        notifications.show({
          title: 'Success', 
          message: 'Entry updated successfully',
          color: 'green'
        })
      }
      close()
      refreshDatabase()
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: 'Failed to save entry',
        color: 'red'
      })
    }
  }

  const deleteEntry = async (id: string) => {
    try {
      await axios.delete(`/api/database/entries/${id}`)
      notifications.show({
        title: 'Success',
        message: 'Entry deleted successfully',
        color: 'green'
      })
      refreshDatabase()
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: 'Failed to delete entry',
        color: 'red'
      })
    }
  }

  const formatExamples = (examples?: string[]) => {
    if (!examples || examples.length === 0) return '—'
    return examples.slice(0, 2).join('; ') + (examples.length > 2 ? '...' : '')
  }

  const highlightText = (text: string, highlight: string) => {
    if (!highlight.trim()) {
      return text
    }
    
    const parts = text.split(new RegExp(`(${highlight})`, 'gi'))
    return (
      <>
        {parts.map((part, i) => 
          part.toLowerCase() === highlight.toLowerCase() ? (
            <mark key={i} className="search-highlight">{part}</mark>
          ) : (
            part
          )
        )}
      </>
    )
  }

  const insertAccent = (char: string) => {
    const input = searchInputRef.current
    if (!input) return

    const start = input.selectionStart || 0
    const end = input.selectionEnd || 0
    const text = searchTerm
    const newText = text.substring(0, start) + char + text.substring(end)
    
    setSearchTerm(newText)
    
    // Set cursor position after inserted character
    setTimeout(() => {
      input.focus()
      input.setSelectionRange(start + 1, start + 1)
    }, 0)
  }

  const accentChars = [
    'á', 'à', 'â', 'ä', 'ã',
    'é', 'è', 'ê', 'ë',
    'í', 'ì', 'î', 'ï',
    'ó', 'ò', 'ô', 'ö', 'õ',
    'ú', 'ù', 'û', 'ü',
    'ñ', 'ç'
  ]

  return (
    <Stack gap="lg">
      {/* Database Statistics */}
      <Card withBorder>
        <Group justify="space-between" mb="md">
          <Title order={2}>
            <IconDatabase size={24} className="title-icon" />
            Dictionary Database
          </Title>
          <Button 
            variant="outline" 
            leftSection={<IconRefresh size={16} />}
            onClick={refreshDatabase}
            loading={loading}
          >
            Refresh
          </Button>
        </Group>
        
        <Text color="dimmed" mb="lg">
          Browse and search all entries in your Chuukese dictionary database. This includes words and phrases extracted from uploaded publications.
        </Text>

        {stats && (
          <Group gap="lg">
            <div>
              <Text size="sm" color="dimmed">Total Entries</Text>
              <Text size="xl" fw={700} c="ocean.6">{stats.total_entries.toLocaleString()}</Text>
            </div>
            <div>
              <Text size="sm" color="dimmed">Chuukese Entries</Text>
              <Text size="xl" fw={700} c="coral.6">{stats.total_chuukese_words.toLocaleString()}</Text>
            </div>
            <div>
              <Text size="sm" color="dimmed">English Translations</Text>
              <Text size="xl" fw={700} c="teal.6">{stats.total_english_words.toLocaleString()}</Text>
            </div>
          </Group>
        )}
      </Card>

      {/* Search Interface */}
      <Card withBorder>
        <Title order={3} mb="md">Search Database</Title>
        <Stack gap="sm">
          <Group gap="md" align="flex-end">
            <Autocomplete
              ref={searchInputRef}
              placeholder="Search Chuukese or English words and phrases..."
              value={searchTerm}
              onChange={setSearchTerm}
              data={suggestions}
              style={{ flex: 1 }}
              label="Search"
              error={searchTerm && !loading && entries.length === 0}
              limit={10}
              maxDropdownHeight={300}
            />
            <Button 
              leftSection={<IconSearch size={16} />}
              onClick={handleSearch}
              loading={loading}
            >
              Search
            </Button>
          </Group>
          
          {/* Accent buttons */}
          <Group gap="xs">
            <Text size="xs" color="dimmed" style={{ minWidth: 'fit-content' }}>
              Accents:
            </Text>
            {accentChars.map((char) => (
              <Button
                key={char}
                size="xs"
                variant="light"
                onClick={() => insertAccent(char)}
                style={{ minWidth: '28px', padding: '4px 8px' }}
              >
                {char}
              </Button>
            ))}
          </Group>
        </Stack>
      </Card>

      {error && (
        <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
          {error}
        </Alert>
      )}

      {/* Database Entries Table */}
      <Card withBorder>
        <Group justify="space-between" mb="md">
          <Title order={3}>Database Entries</Title>
          <Group>
            <Button 
              leftSection={<IconPlus size={16} />}
              onClick={() => openEditModal()}
            >
              Add Entry
            </Button>
            <Text size="sm" color="dimmed">
              {searchTerm && `Filtered by: "${searchTerm}" • `}
              Page {currentPage} of {totalPages}
            </Text>
          </Group>
        </Group>

        {loading ? (
          <Group justify="center" p="xl">
            <Loader />
            <Text>Loading entries...</Text>
          </Group>
        ) : (
          <>
            <div className="table-overflow">
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Chuukese</Table.Th>
                    <Table.Th>English Translation</Table.Th>
                    <Table.Th>Type</Table.Th>
                    <Table.Th>Direction</Table.Th>
                    <Table.Th>Languages</Table.Th>
                    <Table.Th>Definition</Table.Th>
                    <Table.Th>Examples</Table.Th>
                    <Table.Th>Actions</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {entries.length === 0 ? (
                    <Table.Tr>
                      <Table.Td colSpan={8}>
                        {searchTerm ? (
                          <Group justify="center" gap="sm" p="md">
                            <Text size="sm" color="dimmed">
                              No results found for "{searchTerm}".
                            </Text>
                            <Button
                              size="xs"
                              variant="light"
                              leftSection={<IconPlus size={14} />}
                              onClick={() => openEditModal(undefined, searchTerm)}
                            >
                              Add to Dictionary
                            </Button>
                          </Group>
                        ) : (
                          <Text color="dimmed" ta="center" p="md">
                            No dictionary entries found.
                          </Text>
                        )}
                      </Table.Td>
                    </Table.Tr>
                  ) : (
                    entries.map((entry, index) => (
                      <Table.Tr key={entry._id || index}>
                        <Table.Td>
                          <Text fw={500} className="chuukese-text-style">
                            {highlightText(entry.chuukese_word, searchTerm)}
                          </Text>
                        </Table.Td>
                        <Table.Td>
                          <Text>{highlightText(entry.english_translation, searchTerm)}</Text>
                        </Table.Td>
                        <Table.Td>
                          {entry.word_type ? (
                            <Badge color="orange" variant="light" size="sm">
                              {entry.word_type}
                            </Badge>
                          ) : (
                            <Text color="dimmed">—</Text>
                          )}
                        </Table.Td>
                        <Table.Td>
                          {entry.search_direction ? (
                            <Badge color="violet" variant="light" size="sm">
                              {entry.search_direction === 'chk_to_eng' ? 'Chk→Eng' : 'Eng→Chk'}
                            </Badge>
                          ) : (
                            <Text color="dimmed" size="sm">—</Text>
                          )}
                        </Table.Td>
                        <Table.Td>
                          {entry.primary_language && entry.secondary_language ? (
                            <Text size="xs" color="dimmed">
                              {entry.primary_language} → {entry.secondary_language}
                            </Text>
                          ) : (
                            <Text color="dimmed" size="sm">—</Text>
                          )}
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm" color="dimmed" className="text-max-width-200">
                            {entry.definition ? 
                              highlightText(
                                entry.definition.length > 100 ? 
                                  entry.definition.substring(0, 97) + '...' : 
                                  entry.definition,
                                searchTerm
                              ) : '—'
                            }
                          </Text>
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm" color="dimmed" className="text-max-width-200">
                            {formatExamples(entry.examples)}
                          </Text>
                        </Table.Td>
                        <Table.Td>
                          <Group gap="xs">
                            <Button 
                              size="xs" 
                              variant="outline" 
                              leftSection={<IconEdit size={12} />}
                              onClick={() => openEditModal(entry)}
                            >
                              Edit
                            </Button>
                            <Button 
                              size="xs" 
                              variant="outline" 
                              color="red"
                              leftSection={<IconTrash size={12} />}
                              onClick={() => entry._id && deleteEntry(entry._id)}
                            >
                              Delete
                            </Button>
                          </Group>
                        </Table.Td>
                      </Table.Tr>
                    ))
                  )}
                </Table.Tbody>
              </Table>
            </div>

            {totalPages > 1 && (
              <Group justify="center" mt="md">
                <Pagination
                  total={totalPages}
                  value={currentPage}
                  onChange={setCurrentPage}
                  size="sm"
                />
              </Group>
            )}
          </>
        )}
      </Card>
      
      {/* Edit Modal */}
      <Modal 
        opened={opened} 
        onClose={close} 
        title={isNewEntry ? 'Add New Dictionary Entry' : 'Edit Dictionary Entry'}
        size="lg"
      >
        <Stack gap="md">
          <TextInput
            label="Chuukese Word or Phrase"
            placeholder="Enter Chuukese word or phrase..."
            value={formData.chuukese_word}
            onChange={(e) => setFormData({...formData, chuukese_word: e.target.value})}
            required
            description="Can be a single word or a multi-word phrase"
          />
          
          <TextInput
            label="English Translation"
            placeholder="Enter English translation..."
            value={formData.english_translation}
            onChange={(e) => setFormData({...formData, english_translation: e.target.value})}
            required
            description="Translation can also be a phrase"
          />
          
          <Textarea
            label="Definition"
            placeholder="Enter detailed definition..."
            value={formData.definition}
            onChange={(e) => setFormData({...formData, definition: e.target.value})}
            rows={3}
          />
          
          <Select
            label="Type"
            placeholder="Select type..."
            value={formData.word_type}
            onChange={(value) => setFormData({...formData, word_type: value || ''})}
            data={[
              'noun',
              'verb', 
              'adjective',
              'adverb',
              'pronoun',
              'preposition',
              'conjunction',
              'interjection',
              'phrase',
              'idiom',
              'expression'
            ]}
            searchable
            clearable
            description="For phrases, select 'phrase', 'idiom', or 'expression'"
          />
          
          <Textarea
            label="Examples (one per line)"
            placeholder="Enter usage examples..."
            value={formData.examples.join('\n')}
            onChange={(e) => setFormData({
              ...formData, 
              examples: e.target.value.split('\n').filter(ex => ex.trim())
            })}
            rows={3}
          />
          
          <Group justify="flex-end" mt="md">
            <Button variant="outline" onClick={close}>
              Cancel
            </Button>
            <Button onClick={saveEntry}>
              {isNewEntry ? 'Create Entry' : 'Save Changes'}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}

export default Database