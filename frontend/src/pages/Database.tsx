import { useState, useEffect, useRef } from 'react'
import { Card, Title, Text, Button, Group, Stack, Table, TextInput, Badge, Pagination, Alert, Loader, Modal, Textarea, Select, Autocomplete, Progress, Collapse, Box, SimpleGrid } from '@mantine/core'
import { IconDatabase, IconSearch, IconRefresh, IconAlertCircle, IconEdit, IconPlus, IconTrash, IconBook, IconSortAscending, IconSortDescending, IconArrowsSort, IconChevronDown, IconChevronRight, IconCheck, IconX } from '@tabler/icons-react'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import axios from 'axios'
import './Database.css'

interface BibleBookCoverage {
  book: string
  num: number
  chapters: number
  total_verses: number
  loaded_verses: number
  coverage_percent: number
}

interface ChapterCoverage {
  chapter: number
  total_verses: number
  loaded: number[]
  missing: number[]
  loaded_count: number
  missing_count: number
}

interface BookDetail {
  book: string
  chapters: ChapterCoverage[]
  total_verses: number
  total_loaded: number
  total_missing: number
  coverage_percent: number
}

interface DictionaryEntry {
  _id?: string
  chuukese_word: string // Can be a word or phrase
  english_translation: string // Can be a word or phrase
  definition?: string
  examples?: string[]
  grammar?: string // noun, verb, adjective, etc.
  type?: string // word, phrase, sentence, paragraph
  inflection_type?: string
  notes?: string
  search_direction?: string // chk_to_en or en_to_chk
  scripture?: string // Scripture reference like "Genesis 1:1"
  references?: string // Additional scripture references
  chuukese_scripture?: string // Fetched Chuukese scripture text
  english_scripture?: string // Fetched English scripture text
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
  const [scriptureModalOpened, { open: openScriptureModal, close: closeScriptureModal }] = useDisclosure(false)
  const [selectedScripture, setSelectedScripture] = useState<DictionaryEntry | null>(null)
  const [addScriptureModalOpened, { open: openAddScriptureModal, close: closeAddScriptureModal }] = useDisclosure(false)
  const [scriptureRef, setScriptureRef] = useState('')
  const [scripturePreview, setScripturePreview] = useState<{ chuukese: string; english: string; error?: string } | null>(null)
  const [loadingScripture, setLoadingScripture] = useState(false)
  const [sortBy, setSortBy] = useState<string>('')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')
  const [filterType, setFilterType] = useState<string>('')
  const [filterGrammar, setFilterGrammar] = useState<string>('')
  const [filterScripture, setFilterScripture] = useState<string>('')
  const [typeOptions, setTypeOptions] = useState<string[]>([])
  const [grammarOptions, setGrammarOptions] = useState<string[]>([])
  const [scriptureOptions, setScriptureOptions] = useState<string[]>([])
  const [filterBook, setFilterBook] = useState<string>('')
  const [bibleBooks, setBibleBooks] = useState<BibleBookCoverage[]>([])
  const [selectedBookDetail, setSelectedBookDetail] = useState<BookDetail | null>(null)
  const [bibleCoverageOpened, { open: openBibleCoverage, close: closeBibleCoverage }] = useDisclosure(false)
  const [expandedChapters, setExpandedChapters] = useState<number[]>([])
  const entriesPerPage = 20
  const searchInputRef = useRef<HTMLInputElement>(null)

  // Form state for editing
  const [formData, setFormData] = useState({
    chuukese_word: '',
    english_translation: '',
    definition: '',
    type: '',
    grammar: '',
    examples: [] as string[],
    notes: '',
    scripture: '',
    references: ''
  })

  useEffect(() => {
    loadDatabaseStats()
    loadEntries()
    loadFilterOptions()
  }, [currentPage, sortBy, sortOrder, filterType, filterGrammar, filterScripture, filterBook])

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

  const handleSort = (column: string) => {
    if (sortBy === column) {
      // Toggle sort order if same column
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      // New column, start with ascending
      setSortBy(column)
      setSortOrder('asc')
    }
    setCurrentPage(1)
  }

  const getSortIcon = (column: string) => {
    if (sortBy !== column) {
      return <IconArrowsSort size={14} style={{ opacity: 0.3 }} />
    }
    return sortOrder === 'asc' ? 
      <IconSortAscending size={14} /> : 
      <IconSortDescending size={14} />
  }

  const loadDatabaseStats = async () => {
    try {
      const response = await axios.get('/api/database/stats')
      setStats(response.data)
    } catch (err) {
      console.error('Failed to load database stats:', err)
    }
  }

  const loadFilterOptions = async () => {
    try {
      const [typeRes, grammarRes, scriptureRes, bibleRes] = await Promise.all([
        axios.get('/api/database/distinct', { params: { field: 'type' } }),
        axios.get('/api/database/distinct', { params: { field: 'grammar' } }),
        axios.get('/api/database/distinct', { params: { field: 'scripture' } }),
        axios.get('/api/database/bible-coverage')
      ])
      setTypeOptions(typeRes.data.values || [])
      setGrammarOptions(grammarRes.data.values || [])
      setScriptureOptions(scriptureRes.data.values || [])
      setBibleBooks(bibleRes.data.books || [])
    } catch (err) {
      console.error('Failed to load filter options:', err)
    }
  }

  const loadBookDetail = async (bookName: string) => {
    try {
      const response = await axios.get('/api/database/bible-coverage', { params: { book: bookName } })
      setSelectedBookDetail(response.data)
      setExpandedChapters([])
    } catch (err) {
      console.error('Failed to load book detail:', err)
    }
  }

  const toggleChapter = (chapter: number) => {
    setExpandedChapters(prev => 
      prev.includes(chapter) 
        ? prev.filter(c => c !== chapter)
        : [...prev, chapter]
    )
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
      const params: Record<string, string | number | undefined> = {
        page: currentPage,
        limit: entriesPerPage,
        search: searchTerm || undefined,
        sort_by: sortBy || undefined,
        sort_order: sortBy ? sortOrder : undefined,
        filter_type: filterType || undefined,
        filter_grammar: filterGrammar || undefined,
        filter_scripture: filterScripture || filterBook || undefined
      }
      
      const response = await axios.get('/api/database/entries', { params })
      const data = response.data
      
      setEntries(data.entries || [])
      setTotalPages(Math.ceil((data.total || 0) / entriesPerPage))
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
        type: entry.type || '',
        grammar: entry.grammar || '',
        examples: entry.examples || [],
        notes: '',
        scripture: entry.scripture || '',
        references: entry.references || ''
      })
      setIsNewEntry(false)
    } else {
      setEditingEntry(null)
      setFormData({
        chuukese_word: preFillWord || '',
        english_translation: '',
        definition: '',
        type: '',
        grammar: '',
        examples: [],
        notes: '',
        scripture: '',
        references: ''
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

  const previewScripture = async () => {
    if (!scriptureRef.trim()) {
      notifications.show({
        title: 'Error',
        message: 'Please enter a scripture reference',
        color: 'red'
      })
      return
    }

    setLoadingScripture(true)
    setScripturePreview(null)

    try {
      const response = await axios.post('/api/scripture/preview', {
        scripture: scriptureRef
      })
      const data = response.data

      if (data.error && !data.chuukese && !data.english) {
        notifications.show({
          title: 'Error',
          message: data.error,
          color: 'red'
        })
      } else {
        setScripturePreview({
          chuukese: data.chuukese || '',
          english: data.english || '',
          error: data.error
        })
      }
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: 'Failed to fetch scripture',
        color: 'red'
      })
    } finally {
      setLoadingScripture(false)
    }
  }

  const saveScriptureEntry = async () => {
    if (!scripturePreview || (!scripturePreview.chuukese && !scripturePreview.english)) {
      notifications.show({
        title: 'Error',
        message: 'Please preview the scripture first',
        color: 'red'
      })
      return
    }

    try {
      await axios.post('/api/database/entries', {
        chuukese_word: scripturePreview.chuukese,
        english_translation: scripturePreview.english,
        scripture: scriptureRef,
        type: 'scripture'
      })

      notifications.show({
        title: 'Success',
        message: 'Scripture entry added successfully',
        color: 'green'
      })

      // Reset and close modal
      setScriptureRef('')
      setScripturePreview(null)
      closeAddScriptureModal()
      refreshDatabase()
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: 'Failed to save scripture entry',
        color: 'red'
      })
    }
  }

  const fetchAndSaveVerse = async (bookName: string, chapter: number, verse: number) => {
    const reference = `${bookName} ${chapter}:${verse}`
    
    try {
      // Fetch the scripture text
      const response = await axios.post('/api/scripture/preview', {
        scripture: reference
      })
      const data = response.data

      if (data.error && !data.chuukese && !data.english) {
        notifications.show({
          title: 'Error',
          message: `Failed to fetch ${reference}: ${data.error}`,
          color: 'red'
        })
        return
      }

      // Save the entry
      await axios.post('/api/database/entries', {
        chuukese_word: data.chuukese || '',
        english_translation: data.english || '',
        scripture: reference,
        type: 'scripture'
      })

      notifications.show({
        title: 'Success',
        message: `Added ${reference}`,
        color: 'green'
      })

      // Refresh the view without closing the expanded chapter
      refreshDatabase()
      if (selectedBookDetail) {
        const currentExpandedChapters = expandedChapters
        await loadBookDetail(selectedBookDetail.book)
        // Restore the expanded chapters after reload
        setExpandedChapters(currentExpandedChapters)
      }
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: `Failed to add ${reference}`,
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
              className="search-input-wrapper"
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
            <Text size="xs" color="dimmed" className="accent-label">
              Accents:
            </Text>
            {accentChars.map((char) => (
              <Button
                key={char}
                size="xs"
                variant="light"
                onClick={() => insertAccent(char)}
                className="accent-button"
              >
                {char}
              </Button>
            ))}
          </Group>

          {/* Filter dropdowns */}
          <Group gap="md">
            <Text size="xs" color="dimmed">Filters:</Text>
            <Select
              placeholder="Type"
              value={filterType}
              onChange={(value) => {
                setFilterType(value || '')
                setCurrentPage(1)
              }}
              data={typeOptions}
              clearable
              searchable
              size="xs"
              style={{ width: 150 }}
            />
            <Select
              placeholder="Grammar"
              value={filterGrammar}
              onChange={(value) => {
                setFilterGrammar(value || '')
                setCurrentPage(1)
              }}
              data={grammarOptions}
              clearable
              searchable
              size="xs"
              style={{ width: 150 }}
            />
            <Select
              placeholder="Scripture"
              value={filterScripture}
              onChange={(value) => {
                setFilterScripture(value || '')
                setCurrentPage(1)
              }}
              data={scriptureOptions}
              clearable
              searchable
              size="xs"
              style={{ width: 180 }}
            />
            <Select
              placeholder="Bible Book"
              value={filterBook}
              onChange={(value) => {
                setFilterBook(value || '')
                setFilterScripture('')
                setCurrentPage(1)
              }}
              data={bibleBooks.map(b => ({ value: b.book, label: `${b.book} (${b.loaded_verses}/${b.total_verses})` }))}
              clearable
              searchable
              size="xs"
              style={{ width: 220 }}
            />
            <Button
              size="xs"
              variant="light"
              leftSection={<IconBook size={14} />}
              onClick={openBibleCoverage}
            >
              Bible Coverage
            </Button>
            {(filterType || filterGrammar || filterScripture || filterBook) && (
              <Button
                size="xs"
                variant="subtle"
                color="gray"
                onClick={() => {
                  setFilterType('')
                  setFilterGrammar('')
                  setFilterScripture('')
                  setFilterBook('')
                  setCurrentPage(1)
                }}
              >
                Clear filters
              </Button>
            )}
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
            <Button 
              leftSection={<IconBook size={16} />}
              variant="light"
              color="blue"
              onClick={openAddScriptureModal}
            >
              Add Scripture
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
                    <Table.Th onClick={() => handleSort('chuukese')} style={{ cursor: 'pointer' }}>
                      <Group gap={4} wrap="nowrap">Chuukese {getSortIcon('chuukese')}</Group>
                    </Table.Th>
                    <Table.Th onClick={() => handleSort('english')} style={{ cursor: 'pointer' }}>
                      <Group gap={4} wrap="nowrap">English Translation {getSortIcon('english')}</Group>
                    </Table.Th>
                    <Table.Th onClick={() => handleSort('type')} style={{ cursor: 'pointer' }}>
                      <Group gap={4} wrap="nowrap">Type {getSortIcon('type')}</Group>
                    </Table.Th>
                    <Table.Th onClick={() => handleSort('grammar')} style={{ cursor: 'pointer' }}>
                      <Group gap={4} wrap="nowrap">Grammar {getSortIcon('grammar')}</Group>
                    </Table.Th>
                    <Table.Th onClick={() => handleSort('scripture')} style={{ cursor: 'pointer' }}>
                      <Group gap={4} wrap="nowrap">Scripture {getSortIcon('scripture')}</Group>
                    </Table.Th>
                    <Table.Th onClick={() => handleSort('search_direction')} style={{ cursor: 'pointer' }}>
                      <Group gap={4} wrap="nowrap">Search Dir {getSortIcon('search_direction')}</Group>
                    </Table.Th>
                    <Table.Th onClick={() => handleSort('definition')} style={{ cursor: 'pointer' }}>
                      <Group gap={4} wrap="nowrap">Definition {getSortIcon('definition')}</Group>
                    </Table.Th>
                    <Table.Th>Examples</Table.Th>
                    <Table.Th>Actions</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {entries.length === 0 ? (
                    <Table.Tr>
                      <Table.Td colSpan={9}>
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
                          {entry.type ? (
                            <Badge color="blue" variant="light" size="sm">
                              {entry.type}
                            </Badge>
                          ) : (
                            <Text color="dimmed">—</Text>
                          )}
                        </Table.Td>
                        <Table.Td>
                          {entry.grammar ? (
                            <Badge color="orange" variant="light" size="sm">
                              {entry.grammar}
                            </Badge>
                          ) : (
                            <Text color="dimmed">—</Text>
                          )}
                        </Table.Td>
                        <Table.Td>
                          {entry.scripture ? (
                            <Button
                              size="xs"
                              variant="subtle"
                              color="blue"
                              onClick={() => {
                                setSelectedScripture(entry)
                                openScriptureModal()
                              }}
                            >
                              {entry.scripture}
                            </Button>
                          ) : (
                            <Text color="dimmed">—</Text>
                          )}
                        </Table.Td>
                        <Table.Td>
                          {entry.search_direction ? (
                            <Badge color="violet" variant="light" size="sm">
                              {entry.search_direction === 'chk_to_eng' || entry.search_direction === 'chk_to_en' ? 'Chk→Eng' : 'Eng→Chk'}
                            </Badge>
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
            value={formData.type}
            onChange={(value) => setFormData({...formData, type: value || ''})}
            data={[
              'word',
              'phrase',
              'sentence',
              'paragraph',
              'question',
              'scripture'
            ]}
            searchable
            clearable
            description="Entry type: word, phrase, sentence, paragraph, question, or scripture"
          />
          
          <Select
            label="Grammar"
            placeholder="Select grammar type..."
            value={formData.grammar}
            onChange={(value) => setFormData({...formData, grammar: value || ''})}
            data={[
              'noun',
              'verb',
              'transitive verb',
              'intransitive verb',
              'adjective',
              'adverb',
              'pronoun',
              'preposition',
              'conjunction',
              'interjection',
              'auxiliary',
              'determiner',
              'particle',
              'article'
            ]}
            searchable
            clearable
            description="Part of speech (noun, verb, adjective, etc.)"
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
            description="Enter examples, one per line"
          />
          
          <TextInput
            label="Scripture Reference"
            placeholder="e.g., Matthew 24:14, Genesis 1:1"
            value={formData.scripture}
            onChange={(e) => setFormData({...formData, scripture: e.target.value})}
            description="Enter scripture reference to auto-fill Chuukese and English fields"
          />
          
          <Textarea
            label="References"
            placeholder="e.g., Genesis 1:1, John 3:16, Romans 8:28"
            value={formData.references}
            onChange={(e) => setFormData({...formData, references: e.target.value})}
            description="Additional scripture references related to this entry"
            rows={2}
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

      {/* Scripture Display Modal */}
      <Modal
        opened={scriptureModalOpened}
        onClose={closeScriptureModal}
        title={selectedScripture?.scripture || 'Scripture'}
        size="lg"
      >
        <Stack gap="md">
          <div>
            <Text size="sm" fw={600} c="dimmed" mb="xs">Chuukese</Text>
            <Text className="chuukese-text-style">
              {selectedScripture?.chuukese_word || '—'}
            </Text>
          </div>
          
          <div>
            <Text size="sm" fw={600} c="dimmed" mb="xs">English</Text>
            <Text>
              {selectedScripture?.english_translation || '—'}
            </Text>
          </div>
          
          <Group justify="flex-end" mt="md">
            <Button variant="outline" onClick={closeScriptureModal}>
              Close
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* Add Scripture Modal */}
      <Modal
        opened={addScriptureModalOpened}
        onClose={() => {
          setScriptureRef('')
          setScripturePreview(null)
          closeAddScriptureModal()
        }}
        title="Add Scripture Entry"
        size="lg"
      >
        <Stack gap="md">
          <TextInput
            label="Scripture Reference"
            placeholder="e.g., Matthew 24:14, Genesis 1:1, John 3:16"
            value={scriptureRef}
            onChange={(e) => setScriptureRef(e.target.value)}
            description="Enter a Bible book, chapter, and verse (e.g., Genesis 1:1)"
            required
          />

          <Button
            onClick={previewScripture}
            loading={loadingScripture}
            variant="outline"
            leftSection={<IconSearch size={16} />}
          >
            Fetch Scripture
          </Button>

          {scripturePreview && (
            <Card withBorder p="md" bg="gray.0">
              <Stack gap="md">
                {scripturePreview.error && (
                  <Alert color="yellow" title="Note">
                    {scripturePreview.error}
                  </Alert>
                )}

                <div>
                  <Text size="sm" fw={600} c="dimmed" mb="xs">Chuukese</Text>
                  <Text className="chuukese-text-style" style={{ whiteSpace: 'pre-wrap' }}>
                    {scripturePreview.chuukese || '(Not available)'}
                  </Text>
                </div>

                <div>
                  <Text size="sm" fw={600} c="dimmed" mb="xs">English</Text>
                  <Text style={{ whiteSpace: 'pre-wrap' }}>
                    {scripturePreview.english || '(Not available)'}
                  </Text>
                </div>
              </Stack>
            </Card>
          )}

          <Group justify="flex-end" mt="md">
            <Button 
              variant="outline" 
              onClick={() => {
                setScriptureRef('')
                setScripturePreview(null)
                closeAddScriptureModal()
              }}
            >
              Cancel
            </Button>
            <Button 
              onClick={saveScriptureEntry}
              disabled={!scripturePreview || (!scripturePreview.chuukese && !scripturePreview.english)}
              leftSection={<IconPlus size={16} />}
            >
              Save Scripture
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* Bible Coverage Modal */}
      <Modal
        opened={bibleCoverageOpened}
        onClose={() => {
          closeBibleCoverage()
          setSelectedBookDetail(null)
        }}
        title="Bible Verse Coverage"
        size="xl"
      >
        <Stack gap="md">
          {!selectedBookDetail ? (
            <>
              <Text size="sm" c="dimmed">
                Select a book to see which verses are loaded and which are missing.
              </Text>
              <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }} spacing="xs">
                {bibleBooks.map((book) => (
                  <Card
                    key={book.book}
                    withBorder
                    padding="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => loadBookDetail(book.book)}
                  >
                    <Text size="sm" fw={500} truncate>{book.book}</Text>
                    <Progress 
                      value={book.coverage_percent} 
                      size="sm" 
                      color={book.coverage_percent === 100 ? 'green' : book.coverage_percent > 0 ? 'blue' : 'gray'}
                      mt={4}
                    />
                    <Text size="xs" c="dimmed" mt={2}>
                      {book.loaded_verses}/{book.total_verses} verses ({book.coverage_percent}%)
                    </Text>
                  </Card>
                ))}
              </SimpleGrid>
            </>
          ) : (
            <>
              <Group justify="space-between">
                <Group>
                  <Button 
                    variant="subtle" 
                    size="xs" 
                    onClick={() => setSelectedBookDetail(null)}
                    leftSection={<IconChevronRight size={14} style={{ transform: 'rotate(180deg)' }} />}
                  >
                    Back to Books
                  </Button>
                  <Title order={4}>{selectedBookDetail.book}</Title>
                </Group>
                <Badge size="lg" color={selectedBookDetail.coverage_percent === 100 ? 'green' : 'blue'}>
                  {selectedBookDetail.total_loaded}/{selectedBookDetail.total_verses} verses ({selectedBookDetail.coverage_percent}%)
                </Badge>
              </Group>

              <Progress 
                value={selectedBookDetail.coverage_percent} 
                size="md" 
                color={selectedBookDetail.coverage_percent === 100 ? 'green' : 'blue'}
              />

              <Stack gap="xs">
                {selectedBookDetail.chapters.map((chapter) => (
                  <Card key={chapter.chapter} withBorder padding="xs">
                    <Group 
                      justify="space-between" 
                      style={{ cursor: 'pointer' }}
                      onClick={() => toggleChapter(chapter.chapter)}
                    >
                      <Group gap="xs">
                        {expandedChapters.includes(chapter.chapter) ? 
                          <IconChevronDown size={16} /> : 
                          <IconChevronRight size={16} />
                        }
                        <Text fw={500}>Chapter {chapter.chapter}</Text>
                      </Group>
                      <Group gap="xs">
                        <Badge size="sm" color="green" variant="light">
                          {chapter.loaded_count} loaded
                        </Badge>
                        {chapter.missing_count > 0 && (
                          <Badge size="sm" color="red" variant="light">
                            {chapter.missing_count} missing
                          </Badge>
                        )}
                      </Group>
                    </Group>
                    
                    <Collapse in={expandedChapters.includes(chapter.chapter)}>
                      <Box mt="sm">
                        <Group gap={4} wrap="wrap">
                          {Array.from({ length: chapter.total_verses }, (_, i) => i + 1).map((verse) => {
                            const isLoaded = chapter.loaded.includes(verse)
                            return (
                              <Badge
                                key={verse}
                                size="xs"
                                variant={isLoaded ? 'filled' : 'outline'}
                                color={isLoaded ? 'green' : 'red'}
                                style={{ cursor: 'pointer', color: isLoaded ? 'white' : undefined }}
                                onClick={() => {
                                  if (isLoaded) {
                                    // Filter to show this verse
                                    setFilterScripture(`${selectedBookDetail.book} ${chapter.chapter}:${verse}`)
                                    closeBibleCoverage()
                                    setSelectedBookDetail(null)
                                  } else {
                                    // Fetch and save this missing verse
                                    fetchAndSaveVerse(selectedBookDetail.book, chapter.chapter, verse)
                                  }
                                }}
                              >
                                {verse}
                              </Badge>
                            )
                          })}
                        </Group>
                        <Group gap="xs" mt="xs">
                          <Group gap={4}>
                            <IconCheck size={12} color="green" />
                            <Text size="xs" c="dimmed">Loaded</Text>
                          </Group>
                          <Group gap={4}>
                            <IconX size={12} color="red" />
                            <Text size="xs" c="dimmed">Missing</Text>
                          </Group>
                        </Group>
                      </Box>
                    </Collapse>
                  </Card>
                ))}
              </Stack>
            </>
          )}
        </Stack>
      </Modal>
    </Stack>
  )
}

export default Database