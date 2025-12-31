import { useState, useEffect, useRef } from 'react'
import { Card, Title, Text, Button, Group, Stack, Table, TextInput, Badge, Pagination, Alert, Loader, Modal, Textarea, Select, Autocomplete, Progress, Collapse, Box, SimpleGrid, Slider, Checkbox, HoverCard, Divider } from '@mantine/core'
import { IconDatabase, IconSearch, IconRefresh, IconAlertCircle, IconEdit, IconPlus, IconTrash, IconBook, IconSortAscending, IconSortDescending, IconArrowsSort, IconChevronDown, IconChevronRight, IconCheck, IconX } from '@tabler/icons-react'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import axios from 'axios'
import './Database.css'

// Grammar type descriptions with examples
const GRAMMAR_DESCRIPTIONS: Record<string, { description: string; englishExample: string; chuukeseExample: string }> = {
  'noun': {
    description: 'A word that represents a person, place, thing, or idea.',
    englishExample: 'The house is big.',
    chuukeseExample: 'Imw mei lап.'
  },
  'verb': {
    description: 'A word that describes an action, state, or occurrence.',
    englishExample: 'He runs fast.',
    chuukeseExample: 'E pwéér ngonuk.'
  },
  'transitive verb': {
    description: 'A verb that requires a direct object to complete its meaning.',
    englishExample: 'She eats fish.',
    chuukeseExample: 'E mongó iik.'
  },
  'intransitive verb': {
    description: 'A verb that does not require a direct object.',
    englishExample: 'The baby sleeps.',
    chuukeseExample: 'Semirit e mééúr.'
  },
  'adjective': {
    description: 'A word that describes or modifies a noun.',
    englishExample: 'The beautiful flower.',
    chuukeseExample: 'Séúséú mei chóóchó.'
  },
  'adverb': {
    description: 'A word that modifies a verb, adjective, or other adverb.',
    englishExample: 'He speaks slowly.',
    chuukeseExample: 'E kapas féúnúfén.'
  },
  'pronoun': {
    description: 'A word that takes the place of a noun.',
    englishExample: 'He went there.',
    chuukeseExample: 'E fééri ikéé.'
  },
  'preposition': {
    description: 'A word that shows the relationship between a noun and other words.',
    englishExample: 'The book is on the table.',
    chuukeseExample: 'Puk mi won téépur.'
  },
  'conjunction': {
    description: 'A word that connects words, phrases, or clauses.',
    englishExample: 'I eat and drink.',
    chuukeseExample: 'Úwa mongó me ún.'
  },
  'particle': {
    description: 'A small word that adds grammatical meaning but has no fixed category.',
    englishExample: 'Do you want it? (question particle)',
    chuukeseExample: 'Kopwe mochen? (aa)'
  },
  'auxiliary': {
    description: 'A helping verb used with main verbs to express tense, mood, or voice.',
    englishExample: 'I will go.',
    chuukeseExample: 'Upwe fééri.'
  },
  'classifier': {
    description: 'A word used when counting that categorizes nouns by shape or type.',
    englishExample: 'Three long things (sticks).',
    chuukeseExample: 'Éénú kéú (for long objects).'
  },
  'numeral': {
    description: 'A word that represents a number.',
    englishExample: 'One, two, three.',
    chuukeseExample: 'Éét, éruwa, éénú.'
  },
  'ordinal': {
    description: 'A number word indicating position in a sequence.',
    englishExample: 'The first one.',
    chuukeseExample: 'Ekewe ewe maas.'
  },
  'demonstrative': {
    description: 'A word that points to a specific noun (this, that, these, those).',
    englishExample: 'This house is mine.',
    chuukeseExample: 'Imwen iei mei néúi.'
  },
  'possessive': {
    description: 'A word that shows ownership or possession.',
    englishExample: 'My book.',
    chuukeseExample: 'Néúi puk.'
  },
  'interjection': {
    description: 'A word or phrase that expresses strong emotion.',
    englishExample: 'Wow! That is amazing!',
    chuukeseExample: 'Ioó! E pwúng!'
  },
  'quantifier': {
    description: 'A word that indicates amount or quantity.',
    englishExample: 'Many people came.',
    chuukeseExample: 'Chóón meinisin ra wá.'
  },
  'article': {
    description: 'A word that defines a noun as specific or unspecific (the, a, an).',
    englishExample: 'The man is here.',
    chuukeseExample: 'Mwáán e mi iéi.'
  },
  'verb + suffix': {
    description: 'A verb with an attached suffix that modifies its meaning.',
    englishExample: 'He is eating it (with object marker).',
    chuukeseExample: 'E mongóóni.'
  },
  'verb + directional': {
    description: 'A verb with a directional suffix indicating movement toward/away.',
    englishExample: 'Come here / Go there.',
    chuukeseExample: 'Wá me / Fééri nó.'
  },
  'verb + pronoun suffix': {
    description: 'A verb with an attached pronoun indicating the object.',
    englishExample: 'He sees me.',
    chuukeseExample: 'E kúnééi.'
  },
  'verb (reduplicated)': {
    description: 'A verb with repeated syllables to indicate ongoing or repeated action.',
    englishExample: 'Walking around (repeatedly).',
    chuukeseExample: 'Féénúféén (walking about).'
  },
  'verb + reciprocal': {
    description: 'A verb form indicating mutual action between parties.',
    englishExample: 'They see each other.',
    chuukeseExample: 'Ra kúnééir.'
  },
  'transitive verb + suffix': {
    description: 'A transitive verb with an attached suffix modifying its meaning.',
    englishExample: 'He is cooking it.',
    chuukeseExample: 'E téwéni.'
  },
  'transitive verb + pronoun suffix': {
    description: 'A transitive verb with a pronoun suffix indicating the object.',
    englishExample: 'She loves him.',
    chuukeseExample: 'E tongeni.'
  },
  'noun + suffix': {
    description: 'A noun with an attached suffix that modifies its meaning.',
    englishExample: 'The houses (plural).',
    chuukeseExample: 'Ekewe imw.'
  },
  'noun + possessive': {
    description: 'A noun with a possessive suffix indicating ownership.',
    englishExample: 'His hand.',
    chuukeseExample: 'Péúéún.'
  },
  'adjective + suffix': {
    description: 'An adjective with an attached suffix that modifies its meaning.',
    englishExample: 'Very big.',
    chuukeseExample: 'Mei lapelap.'
  },
  'adjective (reduplicated)': {
    description: 'An adjective with repeated syllables for emphasis or intensity.',
    englishExample: 'Very very small.',
    chuukeseExample: 'Kúkúnú.'
  },
  'locational noun': {
    description: 'A noun that indicates location or position.',
    englishExample: 'Inside the house.',
    chuukeseExample: 'Lón imw.'
  },
  'relational noun': {
    description: 'A noun that expresses a relationship, often with possessive suffixes.',
    englishExample: 'Beside him.',
    chuukeseExample: 'Rééún.'
  },
  'transitive verb + directional': {
    description: 'A transitive verb with a directional suffix indicating movement.',
    englishExample: 'Bring it here.',
    chuukeseExample: 'Wáténg me.'
  },
  'interrogative classifier': {
    description: 'A question word used for counting or classifying.',
    englishExample: 'How many (of a type)?',
    chuukeseExample: 'Efén?'
  },
  'possessed form': {
    description: 'A word in its possessed state, marked for ownership.',
    englishExample: 'My thing (possessed).',
    chuukeseExample: 'Néúi (possessed form).'
  },
  'locational noun + possessive': {
    description: 'A locational noun with possessive marking.',
    englishExample: 'On top of it.',
    chuukeseExample: 'Wónúún.'
  },
  'temporal noun': {
    description: 'A noun that expresses time or temporal concepts.',
    englishExample: 'Yesterday, today, tomorrow.',
    chuukeseExample: 'Néésor, ráán, némén.'
  },
  'temporal noun + possessive': {
    description: 'A temporal noun with possessive marking.',
    englishExample: 'In his time.',
    chuukeseExample: 'Ráánnúún.'
  },
  'temporal phrase': {
    description: 'A phrase expressing time or temporal relationships.',
    englishExample: 'A long time ago.',
    chuukeseExample: 'Mé ewe ngonuk.'
  },
  'verb participle': {
    description: 'A verb form used as an adjective or noun.',
    englishExample: 'The running man.',
    chuukeseExample: 'Mwáán e pwéér.'
  },
  'noun (reduplicated)': {
    description: 'A noun with repeated syllables for emphasis or plurality.',
    englishExample: 'Many houses.',
    chuukeseExample: 'Imwimw.'
  }
}

// Bible book sections with pastel colors (based on JW.org categorization)
interface BibleSection {
  name: string
  color: string
  backgroundColor: string
  books: string[]
}

const BIBLE_SECTIONS: BibleSection[] = [
  {
    name: 'Pentateuch',
    color: '#1e3a5f',
    backgroundColor: '#e3f2fd', // Pastel blue
    books: ['Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy']
  },
  {
    name: 'Historical',
    color: '#1b5e20',
    backgroundColor: '#e8f5e9', // Pastel green
    books: ['Joshua', 'Judges', 'Ruth', '1 Samuel', '2 Samuel', '1 Kings', '2 Kings', '1 Chronicles', '2 Chronicles', 'Ezra', 'Nehemiah', 'Esther']
  },
  {
    name: 'Poetic',
    color: '#4a148c',
    backgroundColor: '#f3e5f5', // Pastel purple
    books: ['Job', 'Psalms', 'Proverbs', 'Ecclesiastes', 'Song of Solomon']
  },
  {
    name: 'Major Prophets',
    color: '#e65100',
    backgroundColor: '#fff3e0', // Pastel orange
    books: ['Isaiah', 'Jeremiah', 'Lamentations', 'Ezekiel', 'Daniel']
  },
  {
    name: 'Minor Prophets',
    color: '#880e4f',
    backgroundColor: '#fce4ec', // Pastel pink
    books: ['Hosea', 'Joel', 'Amos', 'Obadiah', 'Jonah', 'Micah', 'Nahum', 'Habakkuk', 'Zephaniah', 'Haggai', 'Zechariah', 'Malachi']
  },
  {
    name: 'Gospels',
    color: '#00695c',
    backgroundColor: '#e0f2f1', // Pastel teal
    books: ['Matthew', 'Mark', 'Luke', 'John']
  },
  {
    name: 'Acts',
    color: '#006064',
    backgroundColor: '#e0f7fa', // Pastel cyan
    books: ['Acts']
  },
  {
    name: "Paul's Letters",
    color: '#f57f17',
    backgroundColor: '#fffde7', // Pastel yellow
    books: ['Romans', '1 Corinthians', '2 Corinthians', 'Galatians', 'Ephesians', 'Philippians', 'Colossians', '1 Thessalonians', '2 Thessalonians', '1 Timothy', '2 Timothy', 'Titus', 'Philemon']
  },
  {
    name: 'Other Inspired Letters',
    color: '#b71c1c',
    backgroundColor: '#ffebee', // Pastel rose
    books: ['Hebrews', 'James', '1 Peter', '2 Peter', '1 John', '2 John', '3 John', 'Jude']
  },
  {
    name: 'Revelation',
    color: '#311b92',
    backgroundColor: '#ede7f6', // Pastel deep purple
    books: ['Revelation']
  }
]

// Helper function to get section info for a book
const getBookSection = (bookName: string): BibleSection | undefined => {
  return BIBLE_SECTIONS.find(section => section.books.includes(bookName))
}

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
  confidence_level?: string // low, medium, high, verified
  confidence_score?: number // 0-100
  user_confirmed?: boolean // User confirmed match from translation game
  is_base_word?: boolean // Whether this is a base word (not inflected)
}

interface DatabaseStats {
  total_entries: number
  total_chuukese_words: number // Unique Chuukese entries
  total_english_words: number // Unique English entries
  total_words: number // Single word entries
  total_phrases: number // Multi-word entries
  total_sentences: number // Sentence type entries
  total_with_scripture: number // Entries with scripture references
  grammar_breakdown: Record<string, number> // Grammar type counts
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
  const [sortBy, setSortBy] = useState<string>('chuukese')
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

  // Column order state
  const defaultColumnOrder = ['chuukese', 'english', 'type', 'grammar', 'scripture', 'definition', 'examples']
  const [columnOrder, setColumnOrder] = useState<string[]>(() => {
    const saved = localStorage.getItem('databaseColumnOrder')
    return saved ? JSON.parse(saved) : defaultColumnOrder
  })
  const [draggedColumn, setDraggedColumn] = useState<string | null>(null)

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
    references: '',
    confidence_score: undefined as number | undefined,
    user_confirmed: false,
    is_base_word: false
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

  const handleDragStart = (column: string) => {
    setDraggedColumn(column)
  }

  const handleDragOver = (e: React.DragEvent, column: string) => {
    e.preventDefault()
    if (draggedColumn && draggedColumn !== column) {
      const newOrder = [...columnOrder]
      const draggedIndex = newOrder.indexOf(draggedColumn)
      const targetIndex = newOrder.indexOf(column)
      
      newOrder.splice(draggedIndex, 1)
      newOrder.splice(targetIndex, 0, draggedColumn)
      
      setColumnOrder(newOrder)
      localStorage.setItem('databaseColumnOrder', JSON.stringify(newOrder))
    }
  }

  const handleDragEnd = () => {
    setDraggedColumn(null)
  }

  const getColumnHeader = (column: string) => {
    const headers: Record<string, string> = {
      'chuukese': 'Chuukese',
      'english': 'English Translation',
      'type': 'Type',
      'grammar': 'Grammar',
      'scripture': 'Scripture',
      'definition': 'Definition',
      'examples': 'Examples'
    }
    return headers[column] || column
  }

  const renderTableCell = (entry: DictionaryEntry, column: string, index: number) => {
    switch (column) {
      case 'chuukese':
        return (
          <Table.Td key={`${column}-${index}`}>
            <Text fw={500} className="chuukese-text-style">
              {renderChuukeseWord(entry, searchTerm)}
            </Text>
          </Table.Td>
        )
      case 'english':
        return (
          <Table.Td key={`${column}-${index}`}>
            <Text>{highlightText(entry.english_translation, searchTerm)}</Text>
          </Table.Td>
        )
      case 'type':
        return (
          <Table.Td key={`${column}-${index}`}>
            {entry.type ? (
              <Badge color="blue" variant="light" size="sm">
                {entry.type}
              </Badge>
            ) : (
              <Text color="dimmed">—</Text>
            )}
          </Table.Td>
        )
      case 'grammar':
        return (
          <Table.Td key={`${column}-${index}`}>
            {entry.grammar ? (
              GRAMMAR_DESCRIPTIONS[entry.grammar] ? (
                <HoverCard width={320} shadow="md" withArrow openDelay={200}>
                  <HoverCard.Target>
                    <Badge color="orange" variant="light" size="sm" style={{ cursor: 'help' }}>
                      {entry.grammar}
                    </Badge>
                  </HoverCard.Target>
                  <HoverCard.Dropdown>
                    <Stack gap="xs">
                      <Text size="sm" fw={600} c="orange">{entry.grammar}</Text>
                      <Text size="xs">{GRAMMAR_DESCRIPTIONS[entry.grammar].description}</Text>
                      <div>
                        <Text size="xs" fw={500} c="dimmed">English Example:</Text>
                        <Text size="xs" fs="italic">{GRAMMAR_DESCRIPTIONS[entry.grammar].englishExample}</Text>
                      </div>
                      <div>
                        <Text size="xs" fw={500} c="dimmed">Chuukese Example:</Text>
                        <Text size="xs" fs="italic">{GRAMMAR_DESCRIPTIONS[entry.grammar].chuukeseExample}</Text>
                      </div>
                    </Stack>
                  </HoverCard.Dropdown>
                </HoverCard>
              ) : (
                <Badge color="orange" variant="light" size="sm">
                  {entry.grammar}
                </Badge>
              )
            ) : (
              <Text color="dimmed">—</Text>
            )}
          </Table.Td>
        )
      case 'scripture':
        return (
          <Table.Td key={`${column}-${index}`}>
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
        )
      case 'definition':
        return (
          <Table.Td key={`${column}-${index}`}>
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
        )
      case 'examples':
        return (
          <Table.Td key={`${column}-${index}`}>
            <Text size="sm" color="dimmed" className="text-max-width-200">
              {formatExamples(entry.examples)}
            </Text>
          </Table.Td>
        )
      default:
        return <Table.Td key={`${column}-${index}`}>—</Table.Td>
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
        references: entry.references || '',
        confidence_score: entry.confidence_score,
        user_confirmed: entry.user_confirmed || false,
        is_base_word: entry.is_base_word || false
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
        references: '',
        confidence_score: undefined,
        user_confirmed: false,
        is_base_word: false
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

  const renderChuukeseWord = (entry: DictionaryEntry, highlight: string) => {
    const word = entry.chuukese_word
    
    // If this is a base word, render it with special styling
    if (entry.is_base_word) {
      if (!highlight.trim()) {
        return <span style={{ color: '#5B21B6', fontWeight: 700 }}>{word}</span>
      }
      
      // Apply both base word styling and search highlighting
      const parts = word.split(new RegExp(`(${highlight})`, 'gi'))
      return (
        <>
          {parts.map((part, i) => 
            part.toLowerCase() === highlight.toLowerCase() ? (
              <mark key={i} className="search-highlight" style={{ color: '#5B21B6', fontWeight: 700 }}>{part}</mark>
            ) : (
              <span key={i} style={{ color: '#5B21B6', fontWeight: 700 }}>{part}</span>
            )
          )}
        </>
      )
    }
    
    // Regular word - just apply search highlighting
    return highlightText(word, highlight)
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
          <Stack gap="md">
            {/* Primary stats row */}
            <Group gap="lg">
              <div>
                <Text size="sm" color="dimmed">Total Entries</Text>
                <Text size="xl" fw={700} c="ocean.6">{stats.total_entries.toLocaleString()}</Text>
              </div>
              <div>
                <Text size="sm" color="dimmed">Unique Chuukese</Text>
                <Text size="xl" fw={700} c="coral.6">{stats.total_chuukese_words.toLocaleString()}</Text>
              </div>
              <div>
                <Text size="sm" color="dimmed">Unique English</Text>
                <Text size="xl" fw={700} c="teal.6">{stats.total_english_words.toLocaleString()}</Text>
              </div>
            </Group>
            
            {/* Secondary stats row */}
            <Group gap="lg">
              <div>
                <Text size="sm" color="dimmed">Words</Text>
                <Text size="lg" fw={600} c="blue">{stats.total_words?.toLocaleString() || 0}</Text>
              </div>
              <div>
                <Text size="sm" color="dimmed">Phrases</Text>
                <Text size="lg" fw={600} c="violet">{stats.total_phrases?.toLocaleString() || 0}</Text>
              </div>
              <div>
                <Text size="sm" color="dimmed">Sentences</Text>
                <Text size="lg" fw={600} c="grape">{stats.total_sentences?.toLocaleString() || 0}</Text>
              </div>
              <div>
                <Text size="sm" color="dimmed">With Scripture</Text>
                <Text size="lg" fw={600} c="indigo">{stats.total_with_scripture?.toLocaleString() || 0}</Text>
              </div>
            </Group>
            
            {/* Grammar breakdown */}
            {stats.grammar_breakdown && Object.keys(stats.grammar_breakdown).length > 0 && (
              <div>
                <Text size="sm" color="dimmed" mb="xs">Grammar Types (hover for details)</Text>
                <Group gap="xs">
                  {Object.entries(stats.grammar_breakdown).map(([grammar, count]) => {
                    const grammarInfo = GRAMMAR_DESCRIPTIONS[grammar]
                    if (grammarInfo) {
                      return (
                        <HoverCard key={grammar} width={320} shadow="md" withArrow openDelay={200}>
                          <HoverCard.Target>
                            <Badge variant="light" color="orange" size="sm" style={{ cursor: 'help' }}>
                              {grammar}: {count.toLocaleString()}
                            </Badge>
                          </HoverCard.Target>
                          <HoverCard.Dropdown>
                            <Stack gap="xs">
                              <Text size="sm" fw={600} c="orange">{grammar}</Text>
                              <Text size="xs">{grammarInfo.description}</Text>
                              <div>
                                <Text size="xs" fw={500} c="dimmed">English Example:</Text>
                                <Text size="xs" fs="italic">{grammarInfo.englishExample}</Text>
                              </div>
                              <div>
                                <Text size="xs" fw={500} c="dimmed">Chuukese Example:</Text>
                                <Text size="xs" fs="italic">{grammarInfo.chuukeseExample}</Text>
                              </div>
                            </Stack>
                          </HoverCard.Dropdown>
                        </HoverCard>
                      )
                    }
                    return (
                      <Badge key={grammar} variant="light" color="orange" size="sm">
                        {grammar}: {count.toLocaleString()}
                      </Badge>
                    )
                  })}
                </Group>
              </div>
            )}
          </Stack>
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
                    {columnOrder.map((column) => (
                      <Table.Th 
                        key={column}
                        onClick={() => handleSort(column)} 
                        onDragStart={() => handleDragStart(column)}
                        onDragOver={(e) => handleDragOver(e, column)}
                        onDragEnd={handleDragEnd}
                        draggable
                        style={{ 
                          cursor: 'move',
                          opacity: draggedColumn === column ? 0.5 : 1
                        }}
                      >
                        <Group gap={4} wrap="nowrap">{getColumnHeader(column)} {getSortIcon(column)}</Group>
                      </Table.Th>
                    ))}
                    <Table.Th onClick={() => handleSort('confidence_score')} style={{ cursor: 'pointer' }}>
                      <Group gap={4} wrap="nowrap">Confidence {getSortIcon('confidence_score')}</Group>
                    </Table.Th>
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
                        {columnOrder.map((column) => renderTableCell(entry, column, index))}
                        <Table.Td>
                          <Group gap="xs">
                            {entry.confidence_score !== undefined ? (
                              <Badge
                                color={
                                  entry.confidence_score >= 90 ? 'blue' :
                                  entry.confidence_score >= 70 ? 'green' :
                                  entry.confidence_score >= 40 ? 'yellow' : 'red'
                                }
                                variant="filled"
                                size="sm"
                                style={{ color: 'white' }}
                              >
                                {entry.confidence_score}%
                              </Badge>
                            ) : (
                              <Text color="dimmed" size="sm">—</Text>
                            )}
                            {entry.user_confirmed && (
                              <Badge color="teal" variant="light" size="sm" leftSection={<IconCheck size={10} />}>
                                Verified
                              </Badge>
                            )}
                          </Group>
                        </Table.Td>
                        <Table.Td>
                          <Group gap="xs" wrap="nowrap">
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
                              variant="subtle" 
                              color="red"
                              onClick={() => entry._id && deleteEntry(entry._id)}
                              p={4}
                            >
                              <IconTrash size={16} />
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
        title={
          <Text size="xl" fw={700}>
            {isNewEntry ? 'Add New Dictionary Entry' : 'Edit Dictionary Entry'}
          </Text>
        }
        size="lg"
      >
        <Stack gap="md">
          <Checkbox
            label="User Confirmed Match"
            description="Check if this translation has been manually verified by a user"
            checked={formData.user_confirmed}
            onChange={(e) => setFormData({...formData, user_confirmed: e.currentTarget.checked})}
            color="teal"
          />
          
          <Checkbox
            label="Base Word (Root Form)"
            description="Check if this is a base/root word (not inflected). Base words will be shown in dark purple and bold."
            checked={formData.is_base_word}
            onChange={(e) => setFormData({...formData, is_base_word: e.currentTarget.checked})}
            color="violet"
          />
          
          <Divider />
          
          <div>
            <Text size="sm" fw={500} mb="xs">
              Confidence Level: {formData.confidence_score !== undefined ? `${formData.confidence_score}%` : 'Not set'}
            </Text>
            <Slider
              value={formData.confidence_score || 0}
              onChange={(value) => setFormData({...formData, confidence_score: value})}
              min={0}
              max={100}
              step={1}
              marks={[
                { value: 0, label: '0%' },
                { value: 40, label: '40%' },
                { value: 70, label: '70%' },
                { value: 90, label: '90%' },
                { value: 100, label: '100%' }
              ]}
              color={
                !formData.confidence_score ? 'gray' :
                formData.confidence_score >= 90 ? 'blue' :
                formData.confidence_score >= 70 ? 'green' :
                formData.confidence_score >= 40 ? 'yellow' : 'red'
              }
              mb="md"
              mt="md"
            />
            {formData.confidence_score !== undefined && formData.confidence_score > 0 && (
              <Text size="xs" c="dimmed">
                {formData.confidence_score >= 90 ? '🔥 Verified - Professionally confirmed' :
                 formData.confidence_score >= 70 ? '✅ High - Very confident' :
                 formData.confidence_score >= 40 ? '👍 Medium - Reasonably confident' :
                 '⚠️ Low - Needs verification'}
              </Text>
            )}
          </div>
          
          <Divider />
          
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
                Select a book to see which verses are loaded and which are missing. Colors represent Bible sections.
              </Text>
              
              {/* Section legend */}
              <Group gap="xs" wrap="wrap">
                {BIBLE_SECTIONS.map((section) => (
                  <Badge 
                    key={section.name}
                    size="xs"
                    style={{ 
                      backgroundColor: section.backgroundColor,
                      color: section.color,
                      border: `1px solid ${section.color}30`
                    }}
                  >
                    {section.name}
                  </Badge>
                ))}
              </Group>
              
              {/* Books grouped by section */}
              <Stack gap="lg">
                {BIBLE_SECTIONS.map((section) => {
                  const sectionBooks = bibleBooks.filter(book => section.books.includes(book.book))
                  if (sectionBooks.length === 0) return null
                  
                  return (
                    <div key={section.name}>
                      <Text size="sm" fw={600} mb="xs" style={{ color: section.color }}>
                        {section.name}
                      </Text>
                      <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }} spacing="xs">
                        {sectionBooks.map((book) => (
                          <Card
                            key={book.book}
                            withBorder
                            padding="xs"
                            style={{ 
                              cursor: 'pointer',
                              backgroundColor: section.backgroundColor,
                              borderColor: `${section.color}30`
                            }}
                            onClick={() => loadBookDetail(book.book)}
                          >
                            <Text size="sm" fw={500} truncate style={{ color: section.color }}>{book.book}</Text>
                            <Progress 
                              value={book.coverage_percent} 
                              size="sm" 
                              color={book.coverage_percent === 100 ? 'green' : book.coverage_percent > 0 ? 'blue' : 'gray'}
                              mt={4}
                            />
                            <Text size="xs" c="dimmed" mt={2}>
                              {book.loaded_verses}/{book.total_verses} ({book.coverage_percent}%)
                            </Text>
                          </Card>
                        ))}
                      </SimpleGrid>
                    </div>
                  )
                })}
              </Stack>
            </>
          ) : (
            (() => {
              const bookSection = getBookSection(selectedBookDetail.book)
              return (
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
                  <Title order={4} style={{ color: bookSection?.color }}>{selectedBookDetail.book}</Title>
                  {bookSection && (
                    <Badge 
                      size="sm"
                      style={{ 
                        backgroundColor: bookSection.backgroundColor,
                        color: bookSection.color,
                        border: `1px solid ${bookSection.color}30`
                      }}
                    >
                      {bookSection.name}
                    </Badge>
                  )}
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
          )})()
          )}
        </Stack>
      </Modal>
    </Stack>
  )
}

export default Database