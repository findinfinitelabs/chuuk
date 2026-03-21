import { useState, useEffect, useRef } from 'react'
import { Card, Title, Text, Button, Group, Stack, Badge, Alert, ScrollArea, Paper, Textarea, Modal, TextInput, ActionIcon, CopyButton, Tooltip, Divider, Loader, Tabs } from '@mantine/core'
import { IconTrophy, IconTarget, IconRefresh, IconCheck, IconX, IconWorld, IconCopy, IconLink, IconUnlink, IconPencil, IconEye, IconEdit } from '@tabler/icons-react'
import MarkdownIt from 'markdown-it'
import { notifications } from '@mantine/notifications'
import axios from 'axios'
import './TranslationGame.css'

interface Sentence {
  id: number
  text: string
  editedText?: string
  paragraph_index?: number
}

interface Match {
  englishId: number
  chuukeseIds: number[]  // Changed to array to support multiple Chuukese sentences
  editedEnglishText?: string
  savedWordPairs?: WordPair[]
}

interface WordSuggestion {
  chuukese: string
  helsinki_translation: string
  matched_english_words: string[]
  grammar_suggestion: string
  in_dictionary: boolean
  confidence: 'high' | 'low'
}

interface WordPair {
  id: string
  englishIndices: number[]
  chuukeseIndices: number[]
  englishWords: string[]
  chuukeseWords: string[]
  grammar: string
  color: string
  description: string
  inDatabase: boolean
}

const _md = new MarkdownIt()

const PAIR_COLORS = ['green', 'blue', 'orange', 'violet', 'teal', 'red', 'cyan', 'pink', 'grape', 'yellow']

function TranslationGame() {
  const [englishSentences, setEnglishSentences] = useState<Sentence[]>([])
  const [chuukeseSentences, setChuukeseSentences] = useState<Sentence[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedEnglish, setSelectedEnglish] = useState<number | null>(null)
  const [selectedChuukese, setSelectedChuukese] = useState<number[]>([])  // Changed to array
  const [matches, setMatches] = useState<Match[]>([])
  const [score, setScore] = useState(0)
  const [totalAttempts, setTotalAttempts] = useState(0)
  const [correctMatches, setCorrectMatches] = useState(0)
  
  // URL input
  const [englishUrl, setEnglishUrl] = useState('')
  const [chuukeseUrl, setChuukeseUrl] = useState('')
  const [articleTitle, setArticleTitle] = useState('')
  
  // Edit modal state
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editingEnglishId, setEditingEnglishId] = useState<number | null>(null)
  const [editedText, setEditedText] = useState('')
  const [pendingChuukeseIds, setPendingChuukeseIds] = useState<number[]>([])  // Changed to array
  const [editedChuukeseTexts, setEditedChuukeseTexts] = useState<Record<number, string>>({})

  // Word-level matching state
  const [englishTokens, setEnglishTokens] = useState<string[]>([])
  const [chuukeseTokens, setChuukeseTokens] = useState<string[]>([])
  const [selEnTokens, setSelEnTokens] = useState<number[]>([])
  const [selChkTokens, setSelChkTokens] = useState<number[]>([])
  const [wordPairs, setWordPairs] = useState<WordPair[]>([])
  const [wordSuggestions, setWordSuggestions] = useState<Record<string, WordSuggestion>>({})
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [showEditTexts, setShowEditTexts] = useState(false)

  // Description editor modal state
  const [descModalOpen, setDescModalOpen] = useState(false)
  const [descEditingPairId, setDescEditingPairId] = useState<string | null>(null)
  const [descContent, setDescContent] = useState('')
  const [descTab, setDescTab] = useState<string | null>('write')
  const descTextareaRef = useRef<HTMLTextAreaElement>(null)
  useEffect(() => {
    loadStats()
    loadGameStateFromCache()
  }, [])

  useEffect(() => {
    // Save game state to localStorage whenever it changes
    if (englishSentences.length > 0 || chuukeseSentences.length > 0) {
      saveGameStateToCache()
    }
  }, [englishSentences, chuukeseSentences, matches, selectedEnglish, selectedChuukese, englishUrl, chuukeseUrl, articleTitle])

  const saveGameStateToCache = () => {
    const gameState = {
      englishSentences,
      chuukeseSentences,
      matches,
      englishUrl,
      chuukeseUrl,
      articleTitle,
      timestamp: Date.now()
    }
    localStorage.setItem('translationGameState', JSON.stringify(gameState))
  }

  const loadGameStateFromCache = () => {
    try {
      const cached = localStorage.getItem('translationGameState')
      if (cached) {
        const gameState = JSON.parse(cached)
        // Check if cache is less than 24 hours old
        const age = Date.now() - gameState.timestamp
        if (age < 24 * 60 * 60 * 1000) {
          setEnglishSentences(gameState.englishSentences || [])
          setChuukeseSentences(gameState.chuukeseSentences || [])
          setMatches(gameState.matches || [])
          setEnglishUrl(gameState.englishUrl || '')
          setChuukeseUrl(gameState.chuukeseUrl || '')
          setArticleTitle(gameState.articleTitle || '')
          
          if (gameState.englishSentences?.length > 0) {
            notifications.show({
              title: 'Game State Restored',
              message: 'Your previous session has been restored',
              color: 'blue'
            })
          }
        } else {
          // Clear old cache
          localStorage.removeItem('translationGameState')
        }
      }
    } catch (error) {
      console.error('Failed to load game state from cache:', error)
    }
  }

  const clearGameState = () => {
    localStorage.removeItem('translationGameState')
    setEnglishSentences([])
    setChuukeseSentences([])
    setMatches([])
    setSelectedEnglish(null)
    setSelectedChuukese([])
    setEnglishUrl('')
    setChuukeseUrl('')
    setArticleTitle('')
    notifications.show({
      title: 'Game Reset',
      message: 'All progress has been cleared',
      color: 'orange'
    })
  }

  const fetchFromUrl = async () => {
    if (!englishUrl.trim()) {
      notifications.show({
        title: 'Error',
        message: 'Please enter an English URL',
        color: 'red'
      })
      return
    }

    if (!chuukeseUrl.trim()) {
      notifications.show({
        title: 'Error',
        message: 'Please enter a Chuukese URL',
        color: 'red'
      })
      return
    }

    try {
      setLoading(true)
      const response = await axios.post('/api/articles/fetch', { 
        englishUrl: englishUrl,
        chuukeseUrl: chuukeseUrl 
      })
      
      setEnglishSentences(response.data.english.sentences)
      setChuukeseSentences(response.data.chuukese.sentences)
      setArticleTitle(response.data.english.title)
      setMatches([])
      setSelectedEnglish(null)
      setSelectedChuukese([])
      
      notifications.show({
        title: 'Success',
        message: `Loaded: ${response.data.english.title}`,
        color: 'green'
      })
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to fetch article. Make sure it\'s a valid wol.jw.org URL.',
        color: 'red'
      })
    } finally {
      setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const response = await axios.get('/api/brochures/stats')
      setScore(response.data.score)
      setCorrectMatches(response.data.correct_matches)
      setTotalAttempts(response.data.total_matches)
    } catch (error) {
      console.error('Failed to load stats:', error)
    }
  }

  const handleEnglishClick = (id: number) => {
    // If already matched, allow re-editing by removing and reopening modal
    const existingMatch = matches.find(m => m.englishId === id)
    if (existingMatch) {
      // Remove from matches so sentence is editable again
      setMatches(prev => prev.filter(m => m.englishId !== id))
      setScore(prev => Math.max(0, prev - 10))
      setCorrectMatches(prev => Math.max(0, prev - 1))
      // Reopen modal with previously saved word pairs
      openEditModal(id, existingMatch.chuukeseIds, existingMatch.savedWordPairs)
      return
    }
    
    // If this English is already selected, deselect it
    if (selectedEnglish === id) {
      setSelectedEnglish(null)
      setSelectedChuukese([])
      return
    }
    
    setSelectedEnglish(id)
    setSelectedChuukese([])  // Reset Chuukese selection when selecting new English
  }

  const handleChuukeseClick = (id: number) => {
    // If already matched, allow clicking to re-pair via the English sentence
    if (matches.some(m => m.chuukeseIds.includes(id))) return
    
    if (!selectedEnglish) {
      notifications.show({
        title: 'Select English First',
        message: 'Please select an English sentence before selecting Chuukese sentences',
        color: 'blue'
      })
      return
    }
    
    // Toggle selection
    setSelectedChuukese(prev => 
      prev.includes(id) 
        ? prev.filter(cid => cid !== id)
        : [...prev, id]
    )
  }

  const handleConfirmMatch = () => {
    if (selectedEnglish === null || selectedChuukese.length === 0) {
      notifications.show({
        title: 'Incomplete Selection',
        message: 'Please select both English and at least one Chuukese sentence',
        color: 'orange'
      })
      return
    }
    
    openEditModal(selectedEnglish, selectedChuukese)
  }

  const openEditModal = (englishId: number, chuukeseIds: number[], existingPairs?: WordPair[]) => {
    const englishSentence = englishSentences.find(s => s.id === englishId)
    if (englishSentence) {
      setEditingEnglishId(englishId)
      setPendingChuukeseIds(chuukeseIds)
      const engText = englishSentence.editedText || englishSentence.text
      setEditedText(engText)

      // Initialize edited Chuukese texts with current values
      const initialChuukeseTexts: Record<number, string> = {}
      chuukeseIds.forEach(id => {
        const sentence = chuukeseSentences.find(s => s.id === id)
        if (sentence) {
          initialChuukeseTexts[id] = sentence.editedText || sentence.text
        }
      })
      setEditedChuukeseTexts(initialChuukeseTexts)

      // Tokenize both sides
      const enTokens = engText.split(/\s+/).filter(Boolean)
      const chkTokens = Object.values(initialChuukeseTexts)
        .join(' ')
        .split(/\s+/)
        .filter(Boolean)
      setEnglishTokens(enTokens)
      setChuukeseTokens(chkTokens)
      setSelEnTokens([])
      setSelChkTokens([])
      setWordSuggestions({})
      setShowEditTexts(false)
      setEditModalOpen(true)

      // Restore previously saved word pairs (re-edit flow), or start fresh
      if (existingPairs && existingPairs.length > 0) {
        setWordPairs(existingPairs)
      } else {
        setWordPairs([])
      }

      // Fetch Helsinki suggestions + DB lookup in parallel
      setLoadingSuggestions(true)
      const suggestionsReq = axios.post('/api/translate/word-suggestions', {
        chuukese_tokens: chkTokens,
        english_sentence: engText
      })
      const dbLookupReq = axios.get('/api/brochures/match/words', {
        params: { chuukese_tokens: chkTokens.join(',') }
      })

      Promise.allSettled([suggestionsReq, dbLookupReq]).then(([suggResult, dbResult]) => {
        // Build suggestions map
        const map: Record<string, WordSuggestion> = {}
        if (suggResult.status === 'fulfilled') {
          suggResult.value.data.suggestions?.forEach((s: WordSuggestion) => {
            map[s.chuukese] = s
          })
        }

        // Layer in DB lookup: mark tokens as in_dictionary if found
        if (dbResult.status === 'fulfilled') {
          const dbPairs: Array<{chuukese: string; english: string; grammar: string; description: string; verified: boolean}> =
            dbResult.value.data.pairs || []

          dbPairs.forEach(dbPair => {
            const existing = map[dbPair.chuukese]
            if (existing) {
              map[dbPair.chuukese] = { ...existing, in_dictionary: true }
            } else {
              // Word found in DB but Helsinki didn't know it
              map[dbPair.chuukese] = {
                chuukese: dbPair.chuukese,
                helsinki_translation: dbPair.english,
                matched_english_words: [],
                grammar_suggestion: dbPair.grammar,
                in_dictionary: true,
                confidence: 'high',
              }
            }
          })

          // If no existing pairs were passed in, auto-populate from DB
          if (!existingPairs || existingPairs.length === 0) {
            const autoPairs: WordPair[] = []
            dbPairs.forEach((dbPair, i) => {
              // Find token index in chkTokens
              const chkIdx = chkTokens.findIndex(
                t => t.toLowerCase() === dbPair.chuukese.toLowerCase()
              )
              // Find token index in enTokens (any word in english translation)
              const enWords = dbPair.english.toLowerCase().split(/\s+/)
              const enIndices = enTokens
                .map((t, idx) => ({ t: t.replace(/[.,!?;:]+$/, '').toLowerCase(), idx }))
                .filter(({ t }) => enWords.includes(t))
                .map(({ idx }) => idx)

              if (chkIdx >= 0) {
                autoPairs.push({
                  id: `db_${i}_${chkIdx}`,
                  englishIndices: enIndices,
                  chuukeseIndices: [chkIdx],
                  englishWords: enIndices.map(i => enTokens[i].replace(/[.,!?;:]+$/, '')),
                  chuukeseWords: [dbPair.chuukese],
                  grammar: dbPair.grammar,
                  color: PAIR_COLORS[autoPairs.length % PAIR_COLORS.length],
                  description: dbPair.description,
                  inDatabase: true,
                })
              }
            })
            if (autoPairs.length > 0) setWordPairs(autoPairs)
          }
        }

        setWordSuggestions(map)
      }).finally(() => setLoadingSuggestions(false))
    }
  }

  const handleSaveEdit = async () => {
    if (editingEnglishId !== null && pendingChuukeseIds.length > 0) {
      // Update the English sentence with edited text
      setEnglishSentences(prev => 
        prev.map(s => s.id === editingEnglishId 
          ? { ...s, editedText: editedText } 
          : s
        )
      )
      
      // Update Chuukese sentences with edited texts
      setChuukeseSentences(prev =>
        prev.map(s => {
          if (editedChuukeseTexts[s.id] !== undefined) {
            return { ...s, editedText: editedChuukeseTexts[s.id] }
          }
          return s
        })
      )
      
      // Proceed with sentence match
      attemptMatch(editingEnglishId, pendingChuukeseIds, wordPairs, editedText, editedChuukeseTexts)

      // Save word pairs if any were linked (awaited so DB is updated before modal closes)
      if (wordPairs.length > 0) {
        try {
          await axios.post('/api/brochures/match/words', {
            word_pairs: wordPairs.map(p => ({
              chuukese: p.chuukeseWords.join(' '),
              english: p.englishWords.join(' '),
              grammar: p.grammar,
              description: p.description,
            })),
            source_sentence_id: `${editingEnglishId}_${pendingChuukeseIds.join('_')}`
          })
        } catch {
          // non-critical — sentence match already saved
        }
      }
      
      setEditModalOpen(false)
      setEditingEnglishId(null)
      setPendingChuukeseIds([])
      setEditedText('')
      setEditedChuukeseTexts({})
      setWordPairs([])
      setSelEnTokens([])
      setSelChkTokens([])
    }
  }

  const toggleEnToken = (idx: number) => {
    setSelEnTokens(prev =>
      prev.includes(idx) ? prev.filter(i => i !== idx) : [...prev, idx]
    )
  }

  const toggleChkToken = (idx: number) => {
    setSelChkTokens(prev =>
      prev.includes(idx) ? prev.filter(i => i !== idx) : [...prev, idx]
    )
  }

  const linkSelectedTokens = () => {
    if (selEnTokens.length === 0 || selChkTokens.length === 0) return
    const enWords = selEnTokens.sort((a,b)=>a-b).map(i => englishTokens[i].replace(/[.,!?;:]+$/, ''))
    const chkWords = selChkTokens.sort((a,b)=>a-b).map(i => chuukeseTokens[i])
    // AI picks grammar from Helsinki suggestions; fall back to 'noun'
    const primaryChk = chkWords[0]
    const sugg = wordSuggestions[primaryChk]
    const grammar = sugg?.grammar_suggestion || 'noun'
    const inDatabase = sugg?.in_dictionary ?? false
    const color = PAIR_COLORS[wordPairs.length % PAIR_COLORS.length]
    setWordPairs(prev => [...prev, {
      id: `${selEnTokens.join('-')}_${selChkTokens.join('-')}`,
      englishIndices: [...selEnTokens],
      chuukeseIndices: [...selChkTokens],
      englishWords: enWords,
      chuukeseWords: chkWords,
      grammar,
      color,
      description: '',
      inDatabase,
    }])
    setSelEnTokens([])
    setSelChkTokens([])
  }

  const openDescEditor = (pairId: string) => {
    const pair = wordPairs.find(p => p.id === pairId)
    if (!pair) return
    setDescEditingPairId(pairId)
    setDescContent(pair.description)
    setDescTab('write')
    setDescModalOpen(true)
  }

  const saveDescription = () => {
    if (!descEditingPairId) return
    setWordPairs(prev => prev.map(p =>
      p.id === descEditingPairId ? { ...p, description: descContent } : p
    ))
    setDescModalOpen(false)
    setDescEditingPairId(null)
  }

  const insertFormatting = (before: string, after = '') => {
    const ta = descTextareaRef.current
    if (!ta) return
    const start = ta.selectionStart
    const end = ta.selectionEnd
    const selected = descContent.slice(start, end)
    const newText = descContent.slice(0, start) + before + selected + after + descContent.slice(end)
    setDescContent(newText)
    // Restore cursor after state update
    setTimeout(() => {
      ta.focus()
      ta.setSelectionRange(start + before.length, start + before.length + selected.length)
    }, 0)
  }

  const unlinkPair = (pairId: string) => {
    setWordPairs(prev => prev.filter(p => p.id !== pairId))
  }

  const handleCancelEdit = () => {
    setEditModalOpen(false)
    setEditingEnglishId(null)
    setPendingChuukeseIds([])
    setEditedText('')
    setEditedChuukeseTexts({})
    setWordPairs([])
    setSelEnTokens([])
    setSelChkTokens([])
    setSelectedEnglish(null)
    setSelectedChuukese([])
  }

  const attemptMatch = async (englishId: number, chuukeseIds: number[], currentWordPairs: WordPair[], customEnglishText?: string, customChuukeseTexts?: Record<number, string>) => {
    // For now, assume matches are correct
    const isCorrect = true
    
    const englishSentence = englishSentences.find(s => s.id === englishId)
    const englishText = customEnglishText || englishSentence?.editedText || englishSentence?.text || ''
    const chuukeseTexts = chuukeseIds.map(id => {
      // Use custom edited text if provided, otherwise fall back to sentence text
      if (customChuukeseTexts && customChuukeseTexts[id]) {
        return customChuukeseTexts[id]
      }
      const sentence = chuukeseSentences.find(s => s.id === id)
      return sentence?.editedText || sentence?.text || ''
    }).join(' ')
    
    try {
      // Save match to backend
      await axios.post('/api/brochures/match', {
        english_id: englishId,
        chuukese_ids: chuukeseIds,
        english_text: englishText,
        original_english_text: englishSentence?.text,
        chuukese_text: chuukeseTexts,
        is_correct: isCorrect,
        user_id: 'anonymous'
      })
      
      // Add to matches with edited text and saved word pairs
      setMatches(prev => [...prev, { 
        englishId, 
        chuukeseIds,
        editedEnglishText: customEnglishText || englishSentence?.editedText,
        savedWordPairs: currentWordPairs,
      }])
      setScore(score + 10)
      setCorrectMatches(correctMatches + 1)
      
      notifications.show({
        title: '✅ Match Saved!',
        message: `+10 points (${chuukeseIds.length} Chuukese sentence${chuukeseIds.length > 1 ? 's' : ''})`,
        color: 'green'
      })
      
      setTotalAttempts(totalAttempts + 1)
      
      // Reset selections
      setSelectedEnglish(null)
      setSelectedChuukese([])
      
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to save match',
        color: 'red'
      })
    }
  }

  const resetGame = () => {
    setMatches([])
    setSelectedEnglish(null)
    setSelectedChuukese([])
    setEnglishUrl('')
    setChuukeseUrl('')
    setArticleTitle('')
    setEnglishSentences([])
    setChuukeseSentences([])
    clearGameState()
  }

  const isMatched = (id: number, type: 'english' | 'chuukese') => {
    return matches.some(m => 
      type === 'english' ? m.englishId === id : m.chuukeseIds.includes(id)
    )
  }

  const accuracy = totalAttempts > 0 ? Math.round((correctMatches / totalAttempts) * 100) : 0

  return (
    <Stack gap="lg">
      {/* Header Card */}
      <Card withBorder>
        <Group justify="space-between">
          <div>
            <Title order={2} mb="xs">
              <IconTarget size={28} style={{ marginRight: '8px', verticalAlign: 'middle' }} />
              Translation Matching Game
            </Title>
            <Text c="dimmed">
              {articleTitle || 'Fetch an article from wol.jw.org to start matching'}
            </Text>
          </div>
          {englishSentences.length > 0 && (
            <Button 
              leftSection={<IconRefresh size={16} />}
              onClick={resetGame}
              variant="outline"
            >
              New Article
            </Button>
          )}
        </Group>
      </Card>

      {/* URL Display Card - shown when article is loaded */}
      {englishSentences.length > 0 && (
        <Card withBorder>
          <Stack gap="sm">
            <Group justify="space-between" align="flex-start">
              <Title order={4}>
                <IconWorld size={20} style={{ marginRight: '8px', verticalAlign: 'middle' }} />
                Article URLs
              </Title>
              <Button 
                onClick={fetchFromUrl}
                loading={loading}
                leftSection={<IconRefresh size={16} />}
                variant="light"
                size="sm"
              >
                Rescan Document
              </Button>
            </Group>
            <Group gap="xs" wrap="nowrap">
              <Text size="sm" fw={500} style={{ minWidth: '60px' }}>English:</Text>
              <Text 
                size="sm" 
                c="blue" 
                style={{ 
                  wordBreak: 'break-all', 
                  cursor: 'pointer',
                  textDecoration: 'underline',
                  flex: 1
                }}
                onClick={() => window.open(englishUrl, '_blank')}
                title="Click to open in new tab"
              >
                {englishUrl}
              </Text>
              <CopyButton value={englishUrl}>
                {({ copied, copy }) => (
                  <Tooltip label={copied ? 'Copied!' : 'Copy URL'}>
                    <ActionIcon color={copied ? 'teal' : 'gray'} variant="subtle" onClick={copy} size="sm">
                      {copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
                    </ActionIcon>
                  </Tooltip>
                )}
              </CopyButton>
            </Group>
            <Group gap="xs" wrap="nowrap">
              <Text size="sm" fw={500} style={{ minWidth: '60px' }}>Chuukese:</Text>
              <Text 
                size="sm" 
                c="blue" 
                style={{ 
                  wordBreak: 'break-all', 
                  cursor: 'pointer',
                  textDecoration: 'underline',
                  flex: 1
                }}
                onClick={() => window.open(chuukeseUrl, '_blank')}
                title="Click to open in new tab"
              >
                {chuukeseUrl}
              </Text>
              <CopyButton value={chuukeseUrl}>
                {({ copied, copy }) => (
                  <Tooltip label={copied ? 'Copied!' : 'Copy URL'}>
                    <ActionIcon color={copied ? 'teal' : 'gray'} variant="subtle" onClick={copy} size="sm">
                      {copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
                    </ActionIcon>
                  </Tooltip>
                )}
              </CopyButton>
            </Group>
          </Stack>
        </Card>
      )}

      {/* URL Input Card */}
      {englishSentences.length === 0 && (
        <Card withBorder>
          <Stack gap="md">
            <Title order={4}>
              <IconWorld size={20} style={{ marginRight: '8px', verticalAlign: 'middle' }} />
              Load Article from JW.org
            </Title>
            <TextInput
              placeholder="https://wol.jw.org/en/wol/d/r1/lp-e/..."
              label="English Article URL"
              description="Enter the English article URL"
              value={englishUrl}
              onChange={(e) => setEnglishUrl(e.target.value)}
            />
            <TextInput
              placeholder="https://wol.jw.org/chk/wol/d/r303/lp-te/..."
              label="Chuukese Article URL"
              description="Enter the Chuukese article URL (note: /chk/ and /lp-te/)"
              value={chuukeseUrl}
              onChange={(e) => setChuukeseUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && fetchFromUrl()}
            />
            <Group>
              <Button 
                onClick={fetchFromUrl}
                loading={loading}
                leftSection={<IconWorld size={16} />}
              >
                Fetch Article
              </Button>
              {(englishSentences.length > 0 || chuukeseSentences.length > 0) && (
                <Button 
                  onClick={clearGameState}
                  variant="outline"
                  color="red"
                  leftSection={<IconRefresh size={16} />}
                >
                  Reset Game
                </Button>
              )}
            </Group>
          </Stack>
        </Card>
      )}

      {/* Stats Card */}
      <Card withBorder>
        <Group justify="space-around">
          <Stack gap="xs" align="center">
            <IconTrophy size={32} color="#FFD700" />
            <Text size="xl" fw={700}>{score}</Text>
            <Text size="sm" c="dimmed">Score</Text>
          </Stack>
          <Stack gap="xs" align="center">
            <IconCheck size={32} color="green" />
            <Text size="xl" fw={700}>{correctMatches}</Text>
            <Text size="sm" c="dimmed">Correct</Text>
          </Stack>
          <Stack gap="xs" align="center">
            <IconX size={32} color="red" />
            <Text size="xl" fw={700}>{totalAttempts - correctMatches}</Text>
            <Text size="sm" c="dimmed">Incorrect</Text>
          </Stack>
          <Stack gap="xs" align="center">
            <IconTarget size={32} color="blue" />
            <Text size="xl" fw={700}>{accuracy}%</Text>
            <Text size="sm" c="dimmed">Accuracy</Text>
          </Stack>
        </Group>
      </Card>

      {/* Game Instructions */}
      {englishSentences.length > 0 && (
        <>
          <Alert title="How to Play" color="blue">
            <Text size="sm">
              1. Click an English sentence<br />
              2. Click one or more Chuukese sentences that match it<br />
              3. Click "Confirm Match" button<br />
              4. Edit the English text if needed before saving
            </Text>
          </Alert>
          
          {/* Confirm Match Button */}
          {selectedEnglish !== null && selectedChuukese.length > 0 && (
            <Button 
              size="md" 
              onClick={handleConfirmMatch}
              color="green"
            >
              Confirm Match ({selectedChuukese.length} Chuukese sentence{selectedChuukese.length > 1 ? 's' : ''})
            </Button>
          )}
        </>
      )}

      {/* Game Board */}
      {englishSentences.length > 0 && (
        <Group align="flex-start" grow style={{ minHeight: '500px' }}>
          {/* English Column */}
          <Card withBorder>
            <Title order={4} mb="md">
              <Badge color="blue" size="lg" mb="xs">English ({englishSentences.length})</Badge>
            </Title>
            <ScrollArea h={600}>
              <Stack gap="xs">
                {englishSentences.map((sentence) => {
                  const matched = isMatched(sentence.id, 'english')
                  const selected = selectedEnglish === sentence.id
                  
                  return (
                    <Paper
                      key={sentence.id}
                      p="md"
                      withBorder
                      className={`sentence-card ${matched ? 'matched' : ''} ${selected ? 'selected' : ''}`}
                      onClick={() => handleEnglishClick(sentence.id)}
                      style={{
                        cursor: 'pointer',
                        opacity: matched ? 0.75 : 1,
                        backgroundColor: matched ? '#e8f5e9' : selected ? '#e3f2fd' : 'white',
                        border: selected ? '2px solid #2196F3' : matched ? '2px solid #4CAF50' : '1px solid #dee2e6'
                      }}
                    >
                      <Group justify="space-between" align="flex-start">
                        <Text size="sm" style={{ flex: 1 }}>
                          {sentence.editedText || sentence.text}
                        </Text>
                        <Group gap="xs">
                          {sentence.editedText && (
                            <Badge size="xs" color="orange" variant="dot">Edited</Badge>
                          )}
                          {matched ? (
                            <Tooltip label="Click to re-edit this match" withArrow>
                              <Group gap={4}>
                                <IconCheck size={16} color="green" />
                                <IconEdit size={14} color="gray" />
                              </Group>
                            </Tooltip>
                          ) : null}
                        </Group>
                      </Group>
                    </Paper>
                  )
                })}
              </Stack>
            </ScrollArea>
          </Card>

          {/* Chuukese Column */}
          <Card withBorder>
            <Title order={4} mb="md">
              <Badge color="green" size="lg" mb="xs">Chuukese ({chuukeseSentences.length})</Badge>
            </Title>
            <ScrollArea h={600}>
              <Stack gap="xs">
                {chuukeseSentences.map((sentence) => {
                  const matched = isMatched(sentence.id, 'chuukese')
                  const selected = selectedChuukese.includes(sentence.id)
                  
                  return (
                    <Paper
                      key={sentence.id}
                      p="md"
                      withBorder
                      className={`sentence-card ${matched ? 'matched' : ''} ${selected ? 'selected' : ''}`}
                      onClick={() => !matched && handleChuukeseClick(sentence.id)}
                      style={{
                        cursor: matched ? 'not-allowed' : 'pointer',
                        opacity: matched ? 0.5 : 1,
                        backgroundColor: matched ? '#e8f5e9' : selected ? '#e3f2fd' : 'white',
                        border: selected ? '2px solid #2196F3' : matched ? '2px solid #4CAF50' : '1px solid #dee2e6'
                      }}
                    >
                      <Group justify="space-between" align="flex-start">
                        <Text size="sm" className="chuukese-text-style" style={{ flex: 1 }}>
                          {sentence.editedText || sentence.text}
                        </Text>
                        <Group gap="xs">
                          {sentence.editedText && (
                            <Badge size="xs" color="orange" variant="dot">Edited</Badge>
                          )}
                          {matched && <IconCheck size={20} color="green" />}
                        </Group>
                      </Group>
                    </Paper>
                  )
                })}
              </Stack>
            </ScrollArea>
          </Card>
        </Group>
      )}

      {/* Completion Message */}
      {matches.length === englishSentences.length && englishSentences.length > 0 && (
        <Alert title="🎉 Round Complete!" color="green">
          <Text>
            Congratulations! You matched all {matches.length} sentences.
          </Text>
          <Button 
            mt="md" 
            leftSection={<IconRefresh size={16} />}
            onClick={resetGame}
          >
            Start New Round
          </Button>
        </Alert>
      )}

      {/* Edit Translation Modal */}
      <Modal
        opened={editModalOpen}
        onClose={handleCancelEdit}
        title="Match Words"
        size="xl"
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Select English words (blue) and Chuukese words (orange), then click <strong>Link</strong> to pair them.
            {loadingSuggestions && <Loader size="xs" ml="xs" />}
          </Text>

          {/* English word chips */}
          <Stack gap={4}>
            <Text size="xs" fw={600} tt="uppercase" c="blue">English</Text>
            <Group gap={6} wrap="wrap">
              {englishTokens.map((token, idx) => {
                const pair = wordPairs.find(p => p.englishIndices.includes(idx))
                const isSelected = selEnTokens.includes(idx)
                const isPaired = !!pair
                const pendingColor = PAIR_COLORS[wordPairs.length % PAIR_COLORS.length]
                return (
                  <Badge
                    key={idx}
                    size="lg"
                    variant={isPaired || isSelected ? 'filled' : 'outline'}
                    color={isSelected ? pendingColor : isPaired ? pair!.color : 'gray'}
                    style={{ cursor: 'pointer', userSelect: 'none' }}
                    onClick={() => toggleEnToken(idx)}
                  >
                    {token}
                  </Badge>
                )
              })}
            </Group>
          </Stack>

          {/* Chuukese word chips */}
          <Stack gap={4}>
            <Text size="xs" fw={600} tt="uppercase" c="orange">Chuukese</Text>
            <Group gap={6} wrap="wrap">
              {chuukeseTokens.map((token, idx) => {
                const pair = wordPairs.find(p => p.chuukeseIndices.includes(idx))
                const isSelected = selChkTokens.includes(idx)
                const isPaired = !!pair
                const sugg = wordSuggestions[token]
                const inDb = sugg?.in_dictionary ?? false
                const pendingColor = PAIR_COLORS[wordPairs.length % PAIR_COLORS.length]
                const tooltipLabel = sugg
                  ? `→ "${sugg.helsinki_translation}" (${sugg.confidence})${inDb ? ' · In dictionary ✓' : ''}`
                  : inDb ? 'In dictionary ✓' : ''
                return (
                  <Tooltip
                    key={idx}
                    label={tooltipLabel}
                    disabled={!tooltipLabel}
                    withArrow
                  >
                    <div style={{ position: 'relative', display: 'inline-flex' }}>
                      <Badge
                        size="lg"
                        variant={isPaired || isSelected ? 'filled' : 'outline'}
                        color={isSelected ? pendingColor : isPaired ? pair!.color : 'gray'}
                        style={{ cursor: 'pointer', userSelect: 'none',
                                 outline: sugg?.confidence === 'high' && !isPaired && !isSelected ? '2px solid var(--mantine-color-orange-3)' : undefined }}
                        onClick={() => toggleChkToken(idx)}
                      >
                        {token}
                      </Badge>
                      {inDb && !isPaired && (
                        <span style={{
                          position: 'absolute', top: -3, right: -3,
                          background: 'var(--mantine-color-teal-5)',
                          borderRadius: '50%', width: 8, height: 8,
                          pointerEvents: 'none',
                        }} />
                      )}
                    </div>
                  </Tooltip>
                )
              })}
            </Group>
          </Stack>

          {/* Link button */}
          <Group>
            <Button
              leftSection={<IconLink size={16} />}
              disabled={selEnTokens.length === 0 || selChkTokens.length === 0}
              onClick={linkSelectedTokens}
              variant="light"
              color="teal"
              size="sm"
            >
              Link Selected Words ({selEnTokens.length} EN + {selChkTokens.length} CHK)
            </Button>
            {(selEnTokens.length > 0 || selChkTokens.length > 0) && (
              <Button size="sm" variant="subtle" color="gray"
                onClick={() => { setSelEnTokens([]); setSelChkTokens([]) }}>
                Clear selection
              </Button>
            )}
          </Group>

          {/* Linked pairs */}
          {wordPairs.length > 0 && (
            <>
              <Divider label="Linked word pairs" labelPosition="left" />
              <Stack gap="xs">
                {wordPairs.map(pair => (
                  <Paper key={pair.id} withBorder p="xs" style={{ borderLeft: `4px solid var(--mantine-color-${pair.color}-5)` }}>
                    <Group justify="space-between" wrap="nowrap" mb={4}>
                      <Group gap="xs" wrap="wrap">
                        <Badge color={pair.color} variant="filled">{pair.englishWords.join(' ')}</Badge>
                        <Text size="sm" c="dimmed">↔</Text>
                        <Badge color={pair.color} variant="light">{pair.chuukeseWords.join(' ')}</Badge>
                        <Badge size="xs" variant="outline" color="gray">{pair.grammar}</Badge>
                        {pair.inDatabase && (
                          <Tooltip label="Already in database" withArrow>
                            <span style={{
                              display: 'inline-block',
                              width: 8, height: 8,
                              borderRadius: '50%',
                              background: 'var(--mantine-color-teal-5)',
                              flexShrink: 0,
                            }} />
                          </Tooltip>
                        )}
                      </Group>
                      <ActionIcon size="sm" color="red" variant="subtle" onClick={() => unlinkPair(pair.id)}>
                        <IconUnlink size={14} />
                      </ActionIcon>
                    </Group>
                    {/* Clickable description */}
                    <Text
                      size="xs"
                      c={pair.description ? 'dark' : 'dimmed'}
                      style={{ cursor: 'pointer', fontStyle: pair.description ? 'normal' : 'italic',
                               padding: '4px 6px', borderRadius: 4,
                               background: 'var(--mantine-color-gray-0)',
                               border: '1px dashed var(--mantine-color-gray-3)' }}
                      onClick={() => openDescEditor(pair.id)}
                    >
                      {pair.description
                        ? pair.description.length > 80 ? pair.description.slice(0, 80) + '…' : pair.description
                        : '+ Add description…'}
                    </Text>
                  </Paper>
                ))}
              </Stack>
            </>
          )}

          {/* Toggle sentence edit */}
          <Divider
            label={
              <Text size="xs" style={{ cursor: 'pointer' }} c="dimmed"
                onClick={() => setShowEditTexts(v => !v)}>
                {showEditTexts ? '▲ Hide sentence edit' : '▼ Edit sentences'}
              </Text>
            }
            labelPosition="left"
          />
          {showEditTexts && (
            <Stack gap="sm">
              <Textarea
                label="English Translation"
                value={editedText}
                onChange={(e) => setEditedText(e.target.value)}
                minRows={2}
                maxRows={5}
                autosize
              />
              {pendingChuukeseIds.map(id => {
                const sentence = chuukeseSentences.find(s => s.id === id)
                return sentence ? (
                  <Textarea
                    key={id}
                    label="Chuukese"
                    value={editedChuukeseTexts[id] || sentence.text}
                    onChange={(e) => setEditedChuukeseTexts(prev => ({ ...prev, [id]: e.target.value }))}
                    minRows={2}
                    maxRows={4}
                    autosize
                    className="chuukese-text-style"
                  />
                ) : null
              })}
            </Stack>
          )}

          <Group justify="flex-end" mt="md">
            <Button variant="subtle" onClick={handleCancelEdit}>Cancel</Button>
            <Button leftSection={<IconCheck size={16} />} onClick={handleSaveEdit}>
              Confirm Match{wordPairs.length > 0 ? ` & Save ${wordPairs.length} Word Pair${wordPairs.length > 1 ? 's' : ''}` : ''}
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* Description Editor Modal */}
      <Modal
        opened={descModalOpen}
        onClose={() => setDescModalOpen(false)}
        title={(() => {
          const pair = wordPairs.find(p => p.id === descEditingPairId)
          return pair ? `Description — ${pair.chuukeseWords.join(' ')} ↔ ${pair.englishWords.join(' ')}` : 'Description'
        })()}
        size="lg"
        zIndex={300}
      >
        <Stack gap="sm">
          <Tabs value={descTab} onChange={setDescTab}>
            <Tabs.List>
              <Tabs.Tab value="write" leftSection={<IconPencil size={14} />}>Write</Tabs.Tab>
              <Tabs.Tab value="preview" leftSection={<IconEye size={14} />}>Preview</Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="write" pt="sm">
              {/* Formatting toolbar */}
              <Group gap={4} mb={6}>
                {([
                  { label: 'B', title: 'Bold', before: '**', after: '**' },
                  { label: 'I', title: 'Italic', before: '_', after: '_' },
                  { label: 'H', title: 'Heading', before: '## ', after: '' },
                ] as { label: string; title: string; before: string; after: string }[]).map(btn => (
                  <Button
                    key={btn.label}
                    size="xs"
                    variant="default"
                    title={btn.title}
                    onClick={() => insertFormatting(btn.before, btn.after)}
                    style={{ fontWeight: btn.label === 'B' ? 700 : btn.label === 'I' ? 400 : undefined,
                             fontStyle: btn.label === 'I' ? 'italic' : undefined, minWidth: 32 }}
                  >
                    {btn.label}
                  </Button>
                ))}
                <Button size="xs" variant="default" title="Bullet list"
                  onClick={() => insertFormatting('\n- ', '')}>• List</Button>
                <Button size="xs" variant="default" title="Numbered list"
                  onClick={() => insertFormatting('\n1. ', '')}>1. List</Button>
              </Group>
              <Textarea
                ref={descTextareaRef}
                value={descContent}
                onChange={e => setDescContent(e.currentTarget.value)}
                minRows={8}
                autosize
                placeholder="Write a description using Markdown…"
                styles={{ input: { fontFamily: 'monospace', fontSize: 13 } }}
              />
            </Tabs.Panel>

            <Tabs.Panel value="preview" pt="sm">
              {descContent.trim() ? (
                <Paper withBorder p="md" style={{ minHeight: 160 }}>
                  <div
                    style={{ lineHeight: 1.6 }}
                    dangerouslySetInnerHTML={{ __html: _md.render(descContent) }}
                  />
                </Paper>
              ) : (
                <Text c="dimmed" size="sm" p="md">Nothing to preview yet.</Text>
              )}
            </Tabs.Panel>
          </Tabs>

          <Group justify="flex-end" mt="sm">
            <Button variant="subtle" onClick={() => setDescModalOpen(false)}>Cancel</Button>
            <Button leftSection={<IconCheck size={16} />} onClick={saveDescription}>
              Save Description
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}

export default TranslationGame
