import { useState, useEffect, useRef } from 'react'
import { Card, Title, Text, Textarea, Button, Group, Stack, Radio, Alert, Badge, Paper, LoadingOverlay, Progress, Autocomplete, Table, ActionIcon, Modal, Divider, Slider } from '@mantine/core'
import { IconLanguage, IconArrowsExchange, IconCheck, IconAlertCircle, IconRobot, IconRefresh, IconBrandGoogle, IconDeviceFloppy, IconBrain, IconBook, IconPlus } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import axios from 'axios'
import { useUser } from '../contexts/UserContext'
import { useUserCache } from '../hooks/useUserCache'

interface TranslationResults {
  google?: string
  helsinki?: string
  ollama?: string
}

interface TrainingStatus {
  is_training: boolean
  models_training: string[]
  progress?: number
  message?: string
  last_training?: string
}

interface PhraseTranslation {
  original: string
  translation: string
  confidence: 'low' | 'medium' | 'high' | 'verified'
  sources: Record<string, string>
}

function Translate() {
  const { email: userEmail } = useUser()
  
  // Cached state - persists across sessions
  const [cachedText, setCachedText] = useUserCache('translate_text', '', userEmail)
  const [cachedDirection, setCachedDirection] = useUserCache<'chk_to_en' | 'en_to_chk'>('translate_direction', 'chk_to_en', userEmail)
  const [cachedTranslations, setCachedTranslations] = useUserCache<TranslationResults>('translate_results', {}, userEmail)
  
  const [text, setText] = useState(cachedText)
  const [translations, setTranslations] = useState<TranslationResults>(cachedTranslations)
  const [phraseTranslations, setPhraseTranslations] = useState<PhraseTranslation[]>([])
  const [correction, setCorrection] = useState('')
  const [direction, setDirection] = useState<'chk_to_en' | 'en_to_chk'>(cachedDirection)
  const [loading, setLoading] = useState(false)
  const [savingCorrection, setSavingCorrection] = useState(false)
  const [error, setError] = useState('')
  const [modelStatus, setModelStatus] = useState<'available' | 'unavailable' | 'checking'>('checking')
  const [trainingStatus, setTrainingStatus] = useState<TrainingStatus | null>(null)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [relatedEntries, setRelatedEntries] = useState<any[]>([])
  const [saveModalOpen, setSaveModalOpen] = useState(false)
  const [selectedPhrase, setSelectedPhrase] = useState<PhraseTranslation | null>(null)
  const [userConfidence, setUserConfidence] = useState<number>(3)
  const [existingPhraseMatch, setExistingPhraseMatch] = useState<any>(null)
  const textInputRef = useRef<HTMLInputElement>(null)

  // Sync local state to cache when it changes
  useEffect(() => {
    setCachedText(text)
  }, [text, setCachedText])

  useEffect(() => {
    setCachedDirection(direction)
  }, [direction, setCachedDirection])

  useEffect(() => {
    if (Object.keys(translations).length > 0) {
      setCachedTranslations(translations)
    }
  }, [translations, setCachedTranslations])

  // Load cached state on mount (when userEmail changes)
  useEffect(() => {
    setText(cachedText)
    setDirection(cachedDirection)
    setTranslations(cachedTranslations)
  }, [userEmail])

  // Poll training status
  useEffect(() => {
    const checkTrainingStatus = async () => {
      try {
        const response = await axios.get('/api/translate/training-status')
        setTrainingStatus(response.data)
      } catch (err) {
        console.error('Failed to check training status:', err)
      }
    }

    // Check immediately
    checkTrainingStatus()

    // Poll every 5 seconds
    const interval = setInterval(checkTrainingStatus, 5000)

    return () => clearInterval(interval)
  }, [])

  // Load suggestions when text changes
  useEffect(() => {
    const loadSuggestions = async () => {
      if (!text || text.length < 2) {
        setSuggestions([])
        return
      }

      try {
        const response = await axios.get('/api/database/entries', {
          params: { search: text, limit: 10 }
        })
        const data = response.data
        if (data.entries && data.entries.length > 0) {
          // Deduplicate suggestions
          const uniqueWords = [...new Set(data.entries.map((entry: any) => entry.chuukese_word))] as string[]
          setSuggestions(uniqueWords)
        } else {
          setSuggestions([])
        }
      } catch (err) {
        console.error('Failed to load suggestions:', err)
        setSuggestions([])
      }
    }

    const debounce = setTimeout(() => {
      loadSuggestions()
    }, 300)

    return () => clearTimeout(debounce)
  }, [text])

  const insertAccent = (char: string) => {
    const input = textInputRef.current
    if (!input) return

    const start = input.selectionStart || 0
    const end = input.selectionEnd || 0
    const newText = text.substring(0, start) + char + text.substring(end)
    
    setText(newText)
    
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

  const handleTranslate = async () => {
    if (!text.trim()) return

    setLoading(true)
    setError('')
    setTranslations({})
    setPhraseTranslations([])
    setCorrection('') // Clear previous correction
    setRelatedEntries([])
    setExistingPhraseMatch(null)

    try {
      // Check if exact phrase exists in database first
      const existingResponse = await axios.get('/api/database/entries', {
        params: { search: text.trim(), limit: 1 }
      })
      
      if (existingResponse.data.entries && existingResponse.data.entries.length > 0) {
        const exactMatch = existingResponse.data.entries.find((e: any) => 
          e.chuukese_word.toLowerCase() === text.trim().toLowerCase()
        )
        if (exactMatch) {
          setExistingPhraseMatch(exactMatch)
        }
      }

      // Call FULL text translation API (for the cards)
      const fullTextResponse = await axios.post('/api/translate', {
        text: text.trim(),
        direction
      })

      if (fullTextResponse.data.success) {
        setTranslations(fullTextResponse.data.translations)
      }

      // Split text into phrases for phrase-by-phrase breakdown
      const phrases = text.match(/[^,.!?;]+[,.!?;]?/g) || [text]
      
      const phraseResponse = await axios.post('/api/translate', {
        phrases: phrases.map(p => p.trim()),
        direction
      })

      if (phraseResponse.data.success && phraseResponse.data.phrases) {
        setPhraseTranslations(phraseResponse.data.phrases)
      }
      
      // Search for related entries
      await searchRelatedEntries(text.trim())
      
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to translate text')
      notifications.show({
        title: 'Translation Error',
        message: err.response?.data?.error || 'Failed to translate text',
        color: 'red'
      })
    } finally {
      setLoading(false)
    }
  }

  const searchRelatedEntries = async (searchText: string) => {
    try {
      // Split text into words and search for entries containing any of them
      const words = searchText.split(/\s+/).filter(w => w.length > 2)
      
      if (words.length === 0) return

      const response = await axios.get('/api/database/entries', {
        params: {
          search: words.join(' '),
          limit: 10,
          type: 'phrase,sentence'
        }
      })

      if (response.data.entries) {
        setRelatedEntries(response.data.entries)
      }
    } catch (err) {
      console.error('Failed to load related entries:', err)
    }
  }

  const openSaveModal = (phrase: PhraseTranslation) => {
    setSelectedPhrase(phrase)
    // Set initial confidence based on auto-detected level (0-100)
    const confidenceMap = { low: 25, medium: 50, high: 75, verified: 100 }
    setUserConfidence(confidenceMap[phrase.confidence] || 50)
    setSaveModalOpen(true)
  }

  const savePhraseToDatabase = async () => {
    if (!selectedPhrase) return

    try {
      // Convert percentage to confidence level
      let confidenceLevel = 'low'
      if (userConfidence >= 90) confidenceLevel = 'verified'
      else if (userConfidence >= 70) confidenceLevel = 'high'
      else if (userConfidence >= 40) confidenceLevel = 'medium'
      
      const response = await axios.post('/api/database/entries', {
        chuukese_word: selectedPhrase.original,
        english_translation: selectedPhrase.translation,
        type: 'phrase',
        confidence_level: confidenceLevel,
        confidence_score: userConfidence,
        source: 'User Translation',
        notes: `Auto-translated with ${selectedPhrase.confidence} confidence, user-verified at ${userConfidence}%`
      })

      if (response.status === 201) {
        notifications.show({
          title: 'Phrase Saved',
          message: 'Translation added to dictionary',
          color: 'green'
        })
        setSaveModalOpen(false)
        setSelectedPhrase(null)
      }
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: 'Failed to save phrase',
        color: 'red'
      })
    }
  }

  const handleSaveCorrection = async () => {
    if (!text.trim() || !correction.trim()) {
      notifications.show({
        title: 'Invalid Input',
        message: 'Both original text and correction are required',
        color: 'red'
      })
      return
    }

    setSavingCorrection(true)

    try {
      const response = await axios.post('/api/translate/correction', {
        original_text: text.trim(),
        corrected_text: correction.trim(),
        direction,
        retrain: true // Trigger retraining
      })

      if (response.data.success) {
        notifications.show({
          title: 'Correction Saved',
          message: 'Translation corrected and models will be retrained',
          color: 'green'
        })
        // Clear inputs after successful save
        setText('')
        setCorrection('')
        setTranslations({})
      } else {
        notifications.show({
          title: 'Error',
          message: response.data.error || 'Failed to save correction',
          color: 'red'
        })
      }
    } catch (err: any) {
      notifications.show({
        title: 'Error',
        message: err.response?.data?.error || 'Failed to save correction',
        color: 'red'
      })
    } finally {
      setSavingCorrection(false)
    }
  }

  const checkModelStatus = async () => {
    try {
      const response = await axios.get('/api/translate/status')
      setModelStatus(response.data.available ? 'available' : 'unavailable')
    } catch {
      setModelStatus('unavailable')
    }
  }

  const trainModel = async (modelType: 'llm' | 'helsinki') => {
    try {
      notifications.show({
        title: 'Training Started',
        message: `Training ${modelType === 'llm' ? 'Ollama' : 'Helsinki-NLP'} model...`,
        color: 'blue'
      })

      const endpoint = modelType === 'llm' ? '/api/train/ollama' : '/api/train/helsinki'
      await axios.post(endpoint)

      notifications.show({
        title: 'Training Complete',
        message: 'Model training completed successfully',
        color: 'green'
      })

      checkModelStatus()
    } catch (err) {
      notifications.show({
        title: 'Training Failed',
        message: 'Failed to train model',
        color: 'red'
      })
    }
  }

  return (
    <Stack gap="lg">
      {/* Header Card */}
      <Card withBorder>
        <Title order={2} mb="md">
          <IconLanguage size={24} style={{ marginRight: 8 }} />
          AI-Powered Chuukese Translation
        </Title>
        <Text color="dimmed">
          Compare translations from Google Translate, Helsinki-NLP, and Ollama AI models side-by-side.
        </Text>
      </Card>

      {/* Model Status */}
      {modelStatus === 'available' ? (
        <Alert icon={<IconCheck size={16} />} title="AI Translation Models Ready" color="green">
          <Text size="sm" mb="md">
            Local Chuukese translators are trained and ready to use.
          </Text>
          <Group gap="xs">
            <Button
              size="xs"
              variant="outline"
              leftSection={<IconRefresh size={14} />}
              onClick={() => trainModel('llm')}
            >
              Retrain Ollama
            </Button>
            <Button
              size="xs"
              variant="outline"
              color="green"
              leftSection={<IconRefresh size={14} />}
              onClick={() => trainModel('helsinki')}
            >
              Fine-tune Helsinki
            </Button>
          </Group>
        </Alert>
      ) : modelStatus === 'unavailable' ? (
        <Alert icon={<IconAlertCircle size={16} />} title="Local AI Model Not Available" color="yellow">
          <Text size="sm" mb="md">
            The translation model needs to be installed and trained first.
          </Text>
          <Button
            size="sm"
            leftSection={<IconRobot size={16} />}
            onClick={() => trainModel('llm')}
          >
            Train AI Model
          </Button>
        </Alert>
      ) : null}

      {/* Translation Direction */}
      <Card withBorder>
        <Title order={3} mb="md">Translation Direction</Title>
        <Radio.Group value={direction} onChange={(val) => setDirection(val as any)}>
          <Stack gap="sm">
            <Radio value="chk_to_en" label="➡️ Chuukese → English" />
            <Radio value="en_to_chk" label="⬅️ English → Chuukese" />
          </Stack>
        </Radio.Group>
      </Card>

      {/* Translation Interface */}
      <Card withBorder>
        <Card.Section withBorder inheritPadding py="sm">
          <Title order={4}>Input Text</Title>
        </Card.Section>
        <Card.Section inheritPadding py="md">
          <Stack gap="sm">
            <Autocomplete
              ref={textInputRef}
              placeholder="Enter text to translate..."
              value={text}
              onChange={setText}
              data={suggestions}
              limit={10}
              maxDropdownHeight={300}
              size="md"
              styles={{
                input: {
                  fontFamily: '"Noto Sans", "Arial Unicode MS", system-ui, sans-serif',
                  fontSize: '18px',
                  fontWeight: 700,
                  padding: '10px 12px'
                }
              }}
            />
            
            {/* Accent buttons */}
            <Group gap="xs">
              <Text size="xs" c="dimmed">
                Accents:
              </Text>
              {accentChars.map((char) => (
                <Button
                  key={char}
                  size="xs"
                  variant="light"
                  onClick={() => insertAccent(char)}
                >
                  {char}
                </Button>
              ))}
            </Group>
          </Stack>
        </Card.Section>
      </Card>

      {/* Translate Button */}
      <Group justify="center">
        <Button
          size="lg"
          leftSection={<IconArrowsExchange size={20} />}
          onClick={handleTranslate}
          loading={loading}
          disabled={!text.trim()}
        >
          Translate Text
        </Button>
      </Group>

      {error && (
        <Alert icon={<IconAlertCircle size={16} />} color="red">
          {error}
        </Alert>
      )}

      {/* Translation Results - Four columns */}
      {(translations.google || translations.helsinki || translations.ollama) && (
        <>
          <Group grow align="stretch">
            {/* Google Translate */}
            <Card withBorder>
              <Card.Section withBorder inheritPadding py="sm">
                <Group gap="xs">
                  <IconBrandGoogle size={20} color="var(--mantine-color-blue-6)" />
                  <Title order={4}>Google Translate</Title>
                </Group>
              </Card.Section>
              <Card.Section inheritPadding py="md" pos="relative">
                <LoadingOverlay visible={loading} />
                {translations.google ? (
                  <Paper p="md" withBorder style={{ backgroundColor: 'var(--mantine-color-blue-0)', minHeight: '150px' }}>
                    <Text
                      style={{
                        fontFamily: '"Noto Sans", "Arial Unicode MS", system-ui, sans-serif',
                        whiteSpace: 'pre-wrap'
                      }}
                    >
                      {translations.google}
                    </Text>
                  </Paper>
                ) : (
                  <Text color="dimmed" ta="center" py="xl">
                    Translating...
                  </Text>
                )}
              </Card.Section>
            </Card>

            {/* Helsinki-NLP */}
            <Card withBorder>
              <Card.Section withBorder inheritPadding py="sm">
                <Group gap="xs">
                  <IconLanguage size={20} color="var(--mantine-color-green-6)" />
                  <Title order={4}>Helsinki-NLP</Title>
                </Group>
              </Card.Section>
              <Card.Section inheritPadding py="md" pos="relative">
                <LoadingOverlay visible={loading} />
                {translations.helsinki ? (
                  <Paper p="md" withBorder style={{ backgroundColor: 'var(--mantine-color-green-0)', minHeight: '150px' }}>
                    <Text
                      style={{
                        fontFamily: '"Noto Sans", "Arial Unicode MS", system-ui, sans-serif',
                        whiteSpace: 'pre-wrap'
                      }}
                    >
                      {translations.helsinki}
                    </Text>
                  </Paper>
                ) : (
                  <Text color="dimmed" ta="center" py="xl">
                    Translating...
                  </Text>
                )}
              </Card.Section>
            </Card>

            {/* Ollama */}
            <Card withBorder>
              <Card.Section withBorder inheritPadding py="sm">
                <Group gap="xs">
                  <IconRobot size={20} color="var(--mantine-color-violet-6)" />
                  <Title order={4}>Ollama AI</Title>
                </Group>
              </Card.Section>
              <Card.Section inheritPadding py="md" pos="relative">
                <LoadingOverlay visible={loading} />
                {translations.ollama ? (
                  <Paper p="md" withBorder style={{ backgroundColor: 'var(--mantine-color-violet-0)', minHeight: '150px' }}>
                    <Text
                      style={{
                        fontFamily: '"Noto Sans", "Arial Unicode MS", system-ui, sans-serif',
                        whiteSpace: 'pre-wrap'
                      }}
                    >
                      {translations.ollama}
                    </Text>
                  </Paper>
                ) : (
                  <Text color="dimmed" ta="center" py="xl">
                    Translating...
                  </Text>
                )}
              </Card.Section>
            </Card>

            {/* Correction Panel */}
            <Card withBorder>
              <Card.Section withBorder inheritPadding py="sm">
                <Group gap="xs">
                  <IconDeviceFloppy size={20} color="var(--mantine-color-orange-6)" />
                  <Title order={4}>Your Correction</Title>
                </Group>
              </Card.Section>
              <Card.Section inheritPadding py="md">
                <Stack gap="md">
                  <Textarea
                    placeholder="Enter the correct translation..."
                    value={correction}
                    onChange={(e) => setCorrection(e.target.value)}
                    minRows={4}
                    styles={{
                      input: {
                        fontFamily: '"Noto Sans", "Arial Unicode MS", system-ui, sans-serif',
                        backgroundColor: 'var(--mantine-color-orange-0)'
                      }
                    }}
                  />
                  <Button
                    leftSection={<IconCheck size={16} />}
                    onClick={handleSaveCorrection}
                    loading={savingCorrection}
                    disabled={!correction.trim()}
                    color="orange"
                  >
                    Save & Retrain Models
                  </Button>
                  <Text size="xs" c="dimmed">
                    This will add your correction to the database and retrain the AI models for better accuracy.
                  </Text>
                </Stack>
              </Card.Section>
            </Card>
          </Group>
          
          {/* Existing Phrase Match */}
          {existingPhraseMatch && (
            <Alert color="teal" variant="light" title="Phrase Found in Dictionary">
              <Stack gap="sm">
                <div>
                  <Text size="sm" fw={500}>Chuukese:</Text>
                  <Text 
                    size="lg" 
                    fw={700}
                    style={{ 
                      fontFamily: '"Noto Sans", "Arial Unicode MS", system-ui, sans-serif'
                    }}
                  >
                    {existingPhraseMatch.chuukese_word}
                  </Text>
                </div>
                <div>
                  <Text size="sm" fw={500}>English:</Text>
                  <Text size="md">{existingPhraseMatch.english_translation}</Text>
                </div>
                {existingPhraseMatch.confidence_level && (
                  <Group gap="xs">
                    <Badge 
                      size="lg"
                      variant="filled"
                      color={
                        existingPhraseMatch.confidence_level === 'verified' ? 'blue' :
                        existingPhraseMatch.confidence_level === 'high' ? 'green' :
                        existingPhraseMatch.confidence_level === 'medium' ? 'yellow' : 'red'
                      }
                    >
                      {existingPhraseMatch.confidence_score || 
                        (existingPhraseMatch.confidence_level === 'verified' ? '100' :
                         existingPhraseMatch.confidence_level === 'high' ? '75' :
                         existingPhraseMatch.confidence_level === 'medium' ? '50' : '25')}% Confidence
                    </Badge>
                    <Text size="xs" c="dimmed">
                      {existingPhraseMatch.confidence_level.charAt(0).toUpperCase() + 
                       existingPhraseMatch.confidence_level.slice(1)} Quality
                    </Text>
                  </Group>
                )}
              </Stack>
            </Alert>
          )}

          {/* Phrase-by-Phrase Breakdown */}
          {phraseTranslations.length > 0 && (
            <Card withBorder>
              <Card.Section withBorder inheritPadding py="sm">
                <Group gap="xs">
                  <IconBook size={20} color="var(--mantine-color-blue-6)" />
                  <Title order={4}>Phrase-by-Phrase Breakdown</Title>
                </Group>
              </Card.Section>
              <Card.Section inheritPadding py="md">
                <Stack gap="xs">
                  {phraseTranslations.map((phrase, idx) => {
                    const confidenceColors = {
                      low: 'red',
                      medium: 'yellow',
                      high: 'green',
                      verified: 'blue'
                    }
                    const confidenceIcons = {
                      low: '⚠️',
                      medium: '👍',
                      high: '✅',
                      verified: '🔥'
                    }
                    const confidenceLabels = {
                      low: 'Machine Translation',
                      medium: 'Auto-Translated',
                      high: 'Database Match',
                      verified: 'Verified'
                    }
                    
                    return (
                      <Paper key={idx} p="sm" withBorder style={{ backgroundColor: 'var(--mantine-color-gray-0)' }}>
                        <Stack gap="xs">
                          <Group justify="space-between" align="flex-start">
                            <div style={{ flex: 1 }}>
                              <Text 
                                fw={700} 
                                size="lg"
                                style={{ 
                                  fontFamily: '"Noto Sans", "Arial Unicode MS", system-ui, sans-serif'
                                }}
                              >
                                {phrase.original}
                              </Text>
                              <Text 
                                size="md" 
                                c="dimmed"
                                mt="xs"
                              >
                                {phrase.translation}
                              </Text>
                            </div>
                            <Group gap="xs">
                              <Badge 
                                color={confidenceColors[phrase.confidence]} 
                                variant="light"
                                leftSection={confidenceIcons[phrase.confidence]}
                              >
                                {confidenceLabels[phrase.confidence]}
                              </Badge>
                              <ActionIcon
                                variant="light"
                                color="teal"
                                onClick={() => openSaveModal(phrase)}
                                title="Save to dictionary"
                              >
                                <IconPlus size={16} />
                              </ActionIcon>
                            </Group>
                          </Group>
                        </Stack>
                      </Paper>
                    )
                  })}
                </Stack>
              </Card.Section>
            </Card>
          )}

          {/* Save Phrase Modal */}
          <Modal
            opened={saveModalOpen}
            onClose={() => setSaveModalOpen(false)}
            title="Save Phrase to Dictionary"
            size="md"
          >
            {selectedPhrase && (
              <Stack gap="md">
                <div>
                  <Text size="sm" c="dimmed" mb="xs">Chuukese Phrase:</Text>
                  <Text 
                    fw={700} 
                    size="lg"
                    style={{ 
                      fontFamily: '"Noto Sans", "Arial Unicode MS", system-ui, sans-serif'
                    }}
                  >
                    {selectedPhrase.original}
                  </Text>
                </div>
                
                <div>
                  <Text size="sm" c="dimmed" mb="xs">English Translation:</Text>
                  <Text size="md">{selectedPhrase.translation}</Text>
                </div>
                
                <Divider />
                
                <div>
                  <Text size="sm" fw={500} mb="md">Confidence Assessment</Text>
                  
                  <Stack gap="md">
                    <Slider
                      value={userConfidence}
                      onChange={setUserConfidence}
                      min={0}
                      max={100}
                      step={5}
                      size="lg"
                      marks={[
                        { value: 0, label: '0%' },
                        { value: 25, label: '25%' },
                        { value: 50, label: '50%' },
                        { value: 75, label: '75%' },
                        { value: 100, label: '100%' }
                      ]}
                      color={
                        userConfidence >= 90 ? 'blue' :
                        userConfidence >= 70 ? 'green' :
                        userConfidence >= 40 ? 'yellow' : 'red'
                      }
                    />
                    
                    <Paper p="md" withBorder mt="lg" style={{ 
                      backgroundColor: 
                        userConfidence >= 90 ? 'var(--mantine-color-blue-0)' :
                        userConfidence >= 70 ? 'var(--mantine-color-green-0)' :
                        userConfidence >= 40 ? 'var(--mantine-color-yellow-0)' : 'var(--mantine-color-red-0)'
                    }}>
                      <Group gap="xs" align="center">
                        <Badge 
                          size="xl" 
                          variant="filled"
                          color={
                            userConfidence >= 90 ? 'blue' :
                            userConfidence >= 70 ? 'green' :
                            userConfidence >= 40 ? 'yellow' : 'red'
                          }
                        >
                          {userConfidence}%
                        </Badge>
                        <div>
                          <Text fw={600} size="sm">
                            {userConfidence >= 90 ? 'Verified / Native' :
                             userConfidence >= 70 ? 'High Confidence' :
                             userConfidence >= 40 ? 'Medium Confidence' : 'Low Confidence'}
                          </Text>
                          <Text size="xs" c="dimmed">
                            {userConfidence >= 90 ? 'Perfect translation, verified by native speaker' :
                             userConfidence >= 70 ? 'Very good translation, highly reliable' :
                             userConfidence >= 40 ? 'Decent translation, may need review' : 
                             'Uncertain translation, requires verification'}
                          </Text>
                        </div>
                      </Group>
                    </Paper>
                  </Stack>
                </div>
                
                <Group justify="flex-end" mt="md">
                  <Button variant="subtle" onClick={() => setSaveModalOpen(false)}>
                    Cancel
                  </Button>
                  <Button 
                    leftSection={<IconCheck size={16} />}
                    onClick={savePhraseToDatabase}
                    color="teal"
                    style={{ color: 'white' }}
                  >
                    Save to Dictionary
                  </Button>
                </Group>
              </Stack>
            )}
          </Modal>

          {/* Related Entries from Database */}
          {relatedEntries.length > 0 && (
            <Card withBorder>
              <Card.Section withBorder inheritPadding py="sm">
                <Group gap="xs" justify="space-between">
                  <Group gap="xs">
                    <IconBook size={20} color="var(--mantine-color-teal-6)" />
                    <Title order={4}>Related Phrases & Sentences</Title>
                  </Group>
                  <Badge color="teal" variant="light">
                    {relatedEntries.length} found
                  </Badge>
                </Group>
              </Card.Section>
              <Card.Section inheritPadding py="md">
                <Stack gap="sm">
                  <Text size="sm" c="dimmed">
                    Similar phrases and sentences from the dictionary that use these words:
                  </Text>
                  <Table highlightOnHover>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Chuukese</Table.Th>
                        <Table.Th>English</Table.Th>
                        <Table.Th>Type</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {relatedEntries.map((entry, idx) => (
                        <Table.Tr key={idx}>
                          <Table.Td>
                            <Text 
                              fw={500}
                              style={{ 
                                fontFamily: '"Noto Sans", "Arial Unicode MS", system-ui, sans-serif'
                              }}
                            >
                              {entry.chuukese_word}
                            </Text>
                          </Table.Td>
                          <Table.Td>
                            <Text>{entry.english_translation}</Text>
                          </Table.Td>
                          <Table.Td>
                            <Badge size="sm" variant="light">
                              {entry.type || 'word'}
                            </Badge>
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Stack>
              </Card.Section>
            </Card>
          )}
        </>
      )}

      {/* Tips */}
      <Card withBorder>
        <Title order={3} mb="md">Translation Tips</Title>
        <Stack gap="sm">
          <Text size="sm">
            • <strong>Google Translate</strong> uses general translation but may not support Chuukese directly
          </Text>
          <Text size="sm">
            • <strong>Helsinki-NLP</strong> is trained specifically on Chuukese and works best for direct translations
          </Text>
          <Text size="sm">
            • <strong>Ollama AI</strong> provides contextual understanding and natural language processing
          </Text>
          <Text size="sm">
            • Compare all three results to get the best translation
          </Text>
        </Stack>
      </Card>

      {/* Training Status */}
      {trainingStatus && (
        <Card withBorder>
          <Group justify="space-between" mb="md">
            <Group gap="xs">
              <IconBrain size={24} color="var(--mantine-color-violet-6)" />
              <Title order={3}>Model Training Status</Title>
            </Group>
            {trainingStatus.is_training && (
              <Badge color="violet" variant="light" size="lg" leftSection="🔄">
                Training in Progress
              </Badge>
            )}
          </Group>

          {trainingStatus.is_training ? (
            <Stack gap="md">
              <Text size="sm" c="dimmed">
                {trainingStatus.message || 'Training models with your corrections...'}
              </Text>
              
              {trainingStatus.models_training && trainingStatus.models_training.length > 0 && (
                <Stack gap="xs">
                  {trainingStatus.models_training.map((model) => {
                    // Determine color based on model type
                    let progressColor = 'violet';
                    if (model.includes('Google')) progressColor = 'blue';
                    else if (model.includes('Helsinki')) progressColor = 'green';
                    else if (model.includes('Ollama')) progressColor = 'violet';
                    
                    return (
                      <Group key={model} gap="sm">
                        <Text size="sm" fw={500} style={{ minWidth: '180px' }}>
                          {model}
                        </Text>
                        <Progress
                          value={trainingStatus.progress || 0}
                          size="lg"
                          radius="xl"
                          striped
                          animated
                          style={{ flex: 1 }}
                          color={progressColor}
                        />
                        <Text size="xs" c="dimmed">
                          {trainingStatus.progress || 0}%
                        </Text>
                      </Group>
                    );
                  })}
                </Stack>
              )}

              <Alert color="blue" variant="light">
                Please wait while the models learn from your corrections. This may take a few minutes.
              </Alert>
            </Stack>
          ) : (
            <Stack gap="sm">
              <Text size="sm" c="dimmed">
                Models are ready. Add corrections to improve translation accuracy.
              </Text>
              {trainingStatus.last_training && (
                <Text size="xs" c="dimmed">
                  Last trained: {new Date(trainingStatus.last_training).toLocaleString()}
                </Text>
              )}
            </Stack>
          )}
        </Card>
      )}
    </Stack>
  )
}

export default Translate
