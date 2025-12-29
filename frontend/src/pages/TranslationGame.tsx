import { useState, useEffect } from 'react'
import { Card, Title, Text, Button, Group, Stack, Badge, Alert, ScrollArea, Paper, Textarea, Modal, TextInput } from '@mantine/core'
import { IconTrophy, IconTarget, IconRefresh, IconCheck, IconX, IconWorld } from '@tabler/icons-react'
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
}

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
    // If already matched, ignore
    if (matches.some(m => m.englishId === id)) return
    
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
    // If already matched, ignore
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

  const openEditModal = (englishId: number, chuukeseIds: number[]) => {
    const englishSentence = englishSentences.find(s => s.id === englishId)
    if (englishSentence) {
      setEditingEnglishId(englishId)
      setPendingChuukeseIds(chuukeseIds)
      setEditedText(englishSentence.editedText || englishSentence.text)
      setEditModalOpen(true)
    }
  }

  const handleSaveEdit = () => {
    if (editingEnglishId !== null && pendingChuukeseIds.length > 0) {
      // Update the sentence with edited text
      setEnglishSentences(prev => 
        prev.map(s => s.id === editingEnglishId 
          ? { ...s, editedText: editedText } 
          : s
        )
      )
      
      // Proceed with match
      attemptMatch(editingEnglishId, pendingChuukeseIds, editedText)
      
      setEditModalOpen(false)
      setEditingEnglishId(null)
      setPendingChuukeseIds([])
      setEditedText('')
    }
  }

  const handleCancelEdit = () => {
    setEditModalOpen(false)
    setEditingEnglishId(null)
    setPendingChuukeseIds([])
    setEditedText('')
    setSelectedEnglish(null)
    setSelectedChuukese([])
  }

  const attemptMatch = async (englishId: number, chuukeseIds: number[], customEnglishText?: string) => {
    // For now, assume matches are correct
    const isCorrect = true
    
    const englishSentence = englishSentences.find(s => s.id === englishId)
    const englishText = customEnglishText || englishSentence?.editedText || englishSentence?.text || ''
    const chuukeseTexts = chuukeseIds.map(id => 
      chuukeseSentences.find(s => s.id === id)?.text || ''
    ).join(' ')
    
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
      
      // Add to matches with edited text if provided
      setMatches([...matches, { 
        englishId, 
        chuukeseIds,
        editedEnglishText: customEnglishText || englishSentence?.editedText
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
    setArticleUrl('')
    setArticleTitle('')
    setEnglishSentences([])
    setChuukeseSentences([])
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
                      onClick={() => !matched && handleEnglishClick(sentence.id)}
                      style={{
                        cursor: matched ? 'not-allowed' : 'pointer',
                        opacity: matched ? 0.5 : 1,
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
                          {matched && <IconCheck size={20} color="green" />}
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
                        <Text size="sm" className="chuukese-text-style" style={{ flex: 1 }}>{sentence.text}</Text>
                        {matched && <IconCheck size={20} color="green" />}
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

      {/* Edit English Translation Modal */}
      <Modal
        opened={editModalOpen}
        onClose={handleCancelEdit}
        title="Edit English Translation"
        size="lg"
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Review and edit the English translation if needed before matching:
          </Text>
          
          <Textarea
            label="English Translation"
            value={editedText}
            onChange={(e) => setEditedText(e.target.value)}
            minRows={4}
            maxRows={8}
            autosize
          />
          
          {pendingChuukeseIds.length > 0 && (
            <Paper p="sm" withBorder bg="gray.0">
              <Text size="xs" fw={500} c="dimmed" mb="xs">
                Matching with {pendingChuukeseIds.length} Chuukese sentence{pendingChuukeseIds.length > 1 ? 's' : ''}:
              </Text>
              <Stack gap="xs">
                {pendingChuukeseIds.map(id => {
                  const sentence = chuukeseSentences.find(s => s.id === id)
                  return sentence ? (
                    <Text key={id} size="sm" className="chuukese-text-style">
                      {sentence.text}
                    </Text>
                  ) : null
                })}
              </Stack>
            </Paper>
          )}
          
          <Group justify="flex-end" mt="md">
            <Button variant="subtle" onClick={handleCancelEdit}>
              Cancel
            </Button>
            <Button onClick={handleSaveEdit}>
              Confirm Match
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}

export default TranslationGame
