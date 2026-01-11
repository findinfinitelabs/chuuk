import { useState } from 'react'
import { Container, Title, Text, Textarea, Button, Stack, Card, Group, Badge, Divider, Loader, Alert, Paper, Grid, Modal } from '@mantine/core'
import { IconLanguage, IconArrowRight, IconAlertCircle, IconFileText } from '@tabler/icons-react'
import axios from 'axios'
import styles from './Sentences.module.css'

interface WordAnalysis {
  original: string
  english: string
  grammar: string
  grammar_modifier?: string
  found: boolean
  definition?: string
  full_entry?: any // Complete dictionary entry for modal
}

interface PhraseMatch {
  phrase: string
  english: string
  definition: string
  grammar: string
}

interface SentenceAnalysis {
  original_sentence: string
  word_by_word: WordAnalysis[]
  phrases: PhraseMatch[]
  rearranged_translation: string
  structure_info: string
}

function Sentences() {
  const [sentence, setSentence] = useState('')
  const [analysis, setAnalysis] = useState<SentenceAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedWord, setSelectedWord] = useState<WordAnalysis | null>(null)
  const [modalOpened, setModalOpened] = useState(false)
  const [addWordModalOpened, setAddWordModalOpened] = useState(false)
  const [newWordData, setNewWordData] = useState({ chuukese: '', english: '', definition: '', grammar: '' })
  const [saveLoading, setSaveLoading] = useState(false)

  const addNewWord = async () => {
    if (!newWordData.english.trim() || !newWordData.grammar.trim()) {
      setError('English translation and grammar type are required')
      return
    }

    setSaveLoading(true)
    setError('')

    try {
      const response = await axios.post('/api/dictionary/add', {
        chuukese_word: newWordData.chuukese,
        english_translation: newWordData.english,
        definition: newWordData.definition,
        grammar: newWordData.grammar,
        confidence: 100,
        verified: true,
        chuukese_example: sentence,
        type: 'sentence'
      })

      if (response.data.success) {
        // Re-analyze the sentence to show the newly added word
        setAddWordModalOpened(false)
        setNewWordData({ chuukese: '', english: '', definition: '', grammar: '' })
        await analyzeSentence()
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to add word to dictionary')
    } finally {
      setSaveLoading(false)
    }
  }

  const analyzeSentence = async () => {
    if (!sentence.trim()) {
      setError('Please enter a sentence')
      return
    }

    setLoading(true)
    setError('')
    setAnalysis(null)

    try {
      const response = await axios.post('/api/sentences/analyze', {
        sentence: sentence.trim()
      })
      setAnalysis(response.data)
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to analyze sentence')
    } finally {
      setLoading(false)
    }
  }

  const getGrammarColor = (grammar: string) => {
    const colors: Record<string, string> = {
      'verb': 'blue',
      'noun': 'green',
      'adjective': 'orange',
      'adverb': 'cyan',
      'pronoun': 'grape',
      'preposition': 'pink',
      'conjunction': 'indigo',
      'particle': 'teal',
      'auxiliary': 'violet',
      'classifier': 'lime',
      'demonstrative': 'yellow',
      'interrogative': 'red'
    }
    return grammar ? colors[grammar.toLowerCase()] || 'gray' : 'gray'
  }

  return (
    <Container size="lg" py="xl">
      <Stack gap="xl">
        {/* Header */}
        <Paper p="xl" radius="md" withBorder>
          <Group gap="md" mb="md">
            <IconFileText size={40} color="#228be6" />
            <div>
              <Title order={1}>Sentence Analysis</Title>
              <Text c="dimmed" size="sm">
                Word-by-word translation with grammar structure and English rearrangement
              </Text>
            </div>
          </Group>
        </Paper>

        {/* Input Section */}
        <Card withBorder radius="md" p="xl">
          <Stack gap="lg">
            <div>
              <Text fw={600} mb="xs">Chuukese Sentence</Text>
              <Textarea
                placeholder="Enter or paste a Chuukese sentence..."
                value={sentence}
                onChange={(e) => setSentence(e.target.value)}
                minRows={3}
                size="md"
                styles={{
                  input: { 
                    fontSize: '16px',
                    fontWeight: 500
                  }
                }}
              />
            </div>
            <Button
              onClick={analyzeSentence}
              loading={loading}
              size="lg"
              leftSection={<IconLanguage size={20} />}
              fullWidth
            >
              Analyze Sentence
            </Button>
          </Stack>
        </Card>

        {/* Error Display */}
        {error && (
          <Alert icon={<IconAlertCircle size={16} />} color="red" title="Error" radius="md">
            {error}
          </Alert>
        )}

        {/* Loading State */}
        {loading && (
          <Card withBorder radius="md" p="xl">
            <Group justify="center" gap="md">
              <Loader size="lg" />
              <Text size="lg" fw={500}>Analyzing sentence...</Text>
            </Group>
          </Card>
        )}

        {/* Analysis Results */}
        {analysis && !loading && (
          <Stack gap="lg">
            {/* Original Sentence */}
            <Paper withBorder radius="md" p="xl" bg="blue.0">
              <Stack gap="xs">
                <Text size="xs" tt="uppercase" fw={700} c="dimmed">Original Sentence</Text>
                <Text size="xl" fw={600} c="blue.9">
                  {analysis.original_sentence}
                </Text>
              </Stack>
            </Paper>

            {/* Word-by-Word Translation */}
            <Card withBorder radius="md" p="xl">
              <Stack gap="md">
                <Group gap="xs">
                  <IconLanguage size={20} color="gray" />
                  <Text size="xs" tt="uppercase" fw={700} c="dimmed">Word-by-Word Analysis</Text>
                </Group>
                <Divider />
                <Grid gutter="md">
                  {analysis.word_by_word.map((word, index) => (
                    <Grid.Col key={index} span={{ base: 6, sm: 4, md: 3 }}>
                      <Paper 
                        withBorder 
                        p="md" 
                        radius="md" 
                        h="100%"
                        className={`${styles['word-card']} ${styles['word-card--clickable']}`}
                        onClick={() => {
                          if (word.found) {
                            setSelectedWord(word)
                            setModalOpened(true)
                          } else {
                            // Open add word modal for not found words
                            setNewWordData({
                              chuukese: word.original,
                              english: '',
                              definition: '',
                              grammar: ''
                            })
                            setAddWordModalOpened(true)
                          }
                        }}
                      >
                        <Stack gap="sm" align="center">
                          <Text fw={700} size="lg" c="blue.7">{word.original}</Text>
                          <IconArrowRight size={16} color="#adb5bd" />
                          {word.found ? (
                            <>
                              <Text size="sm" ta="center" fw={500}>{word.english}</Text>
                              <Group gap="4" justify="center">
                                <Badge size="sm" color={getGrammarColor(word.grammar)} variant="filled">
                                  {word.grammar}
                                </Badge>
                                {word.grammar_modifier && (
                                  <Badge size="xs" color="gray" variant="outline">
                                    {word.grammar_modifier}
                                  </Badge>
                                )}
                              </Group>
                              <Badge size="xs" color="blue" variant="light">
                                Click for details
                              </Badge>
                            </>
                          ) : (
                            <>
                              <Badge color="red" variant="light">not found</Badge>
                              <Badge size="xs" color="green" variant="light">
                                Click to add
                              </Badge>
                            </>
                          )}                          
                        </Stack>
                      </Paper>
                    </Grid.Col>
                  ))}
                </Grid>
              </Stack>
            </Card>

            {/* Grammar Structure */}
            <Paper withBorder radius="md" p="xl" bg="gray.0">
              <Stack gap="xs">
                <Text size="xs" tt="uppercase" fw={700} c="dimmed">Sentence Structure</Text>
                <Text size="md" fw={500}>{analysis.structure_info}</Text>
              </Stack>
            </Paper>

            {/* Phrases Found */}
            {analysis.phrases && analysis.phrases.length > 0 && (
              <Card withBorder radius="md" p="xl">
                <Stack gap="lg">
                  <Group gap="xs">
                    <IconLanguage size={20} color="gray" />
                    <Text size="xs" tt="uppercase" fw={700} c="dimmed">Phrases in Sentence</Text>
                  </Group>
                  <Divider />
                  <Stack gap="md">
                    {analysis.phrases.map((phrase, index) => (
                      <Paper key={index} p="md" radius="md" withBorder bg="violet.0">
                        <Stack gap="xs">
                          <Group justify="space-between">
                            <Group gap="xs">
                              <Text fw={700} c="violet.9" size="lg">{phrase.phrase}</Text>
                              <IconArrowRight size={16} color="#adb5bd" />
                              <Text fw={600} size="md">{phrase.english}</Text>
                            </Group>
                            {phrase.grammar && (
                              <Badge size="sm" color="violet" variant="filled">
                                {phrase.grammar}
                              </Badge>
                            )}
                          </Group>
                          {phrase.definition && (
                            <Text size="sm" c="dimmed" pl="md">{phrase.definition}</Text>
                          )}
                        </Stack>
                      </Paper>
                    ))}
                  </Stack>
                </Stack>
              </Card>
            )}

            {/* English Translation */}
            <Paper withBorder radius="md" p="xl" bg="teal.0">
              <Stack gap="xs">
                <Text size="xs" tt="uppercase" fw={700} c="dimmed">English Translation</Text>
                <Text size="xl" fw={600} c="teal.9">
                  {analysis.rearranged_translation}
                </Text>
              </Stack>
            </Paper>

            {/* Word Definitions */}
            {analysis.word_by_word.some(w => w.found && w.definition) && (
              <Card withBorder radius="md" p="xl">
                <Stack gap="lg">
                  <Text size="xs" tt="uppercase" fw={700} c="dimmed">Detailed Definitions</Text>
                  <Divider />
                  <Stack gap="md">
                    {analysis.word_by_word
                      .filter(w => w.found && w.definition)
                      .map((word, index) => (
                        <Paper key={index} p="md" radius="md" bg="gray.0">
                          <Group gap="xs" mb="xs">
                            <Text fw={700} c="blue.7" size="lg">{word.original}</Text>
                            <Text c="dimmed" size="sm">({word.english})</Text>
                          </Group>
                          <Text size="sm" pl="md">{word.definition}</Text>
                        </Paper>
                      ))}
                  </Stack>
                </Stack>
              </Card>
            )}
          </Stack>
        )}
      </Stack>

      {/* Word Details Modal */}
      <Modal
        opened={modalOpened}
        onClose={() => setModalOpened(false)}
        title={
          <Group gap="xs">
            <Text size="xl" fw={700}>{selectedWord?.original}</Text>
            {selectedWord?.grammar && (
              <Badge color={getGrammarColor(selectedWord.grammar)}>
                {selectedWord.grammar}
              </Badge>
            )}
          </Group>
        }
        size="lg"
      >
        {selectedWord && (
          <Stack gap="md">
            {/* English Translation */}
            <div className={styles['modal-section']}>
              <span className={styles['modal-section-label']}>English Translation</span>
              <Text size="lg">{selectedWord.english}</Text>
            </div>

            {/* Grammar Info */}
            <div className={styles['modal-section']}>
              <span className={styles['modal-section-label']}>Grammar</span>
              <Group gap="xs">
                <Badge color={getGrammarColor(selectedWord.grammar)}>
                  {selectedWord.grammar}
                </Badge>
                {selectedWord.grammar_modifier && (
                  <Badge color="gray" variant="light">
                    {selectedWord.grammar_modifier}
                  </Badge>
                )}
              </Group>
            </div>

            {/* Definition */}
            {selectedWord.definition && (
              <div className={styles['modal-section']}>
                <span className={styles['modal-section-label']}>Definition</span>
                <Text>{selectedWord.definition}</Text>
              </div>
            )}

            {/* Notes */}
            {selectedWord.full_entry?.notes && (
              <div className={styles['modal-section']}>
                <span className={styles['modal-section-label']}>Notes</span>
                <div className={styles['notes-display']}>
                  {selectedWord.full_entry.notes}
                </div>
              </div>
            )}

            {/* Examples */}
            {selectedWord.full_entry?.examples && (
              <div className={styles['modal-section']}>
                <span className={styles['modal-section-label']}>Examples</span>
                <div className={styles['examples-display']}>
                  {selectedWord.full_entry.examples}
                </div>
              </div>
            )}

            {/* Pronunciation */}
            {selectedWord.full_entry?.pronunciation && (
              <div className={styles['modal-section']}>
                <span className={styles['modal-section-label']}>Pronunciation</span>
                <Text>{selectedWord.full_entry.pronunciation}</Text>
              </div>
            )}

            {/* Source */}
            {selectedWord.full_entry?.source && (
              <div className={styles['modal-section']}>
                <span className={styles['modal-section-label']}>Source</span>
                <Text size="sm" c="dimmed">{selectedWord.full_entry.source}</Text>
              </div>
            )}

            {/* Etymology */}
            {selectedWord.full_entry?.etymology && (
              <div className={styles['modal-section']}>
                <span className={styles['modal-section-label']}>Etymology</span>
                <Text size="sm">{selectedWord.full_entry.etymology}</Text>
              </div>
            )}

            {/* Additional Info */}
            {selectedWord.full_entry?.usage && (
              <div className={styles['modal-section']}>
                <span className={styles['modal-section-label']}>Usage</span>
                <div className={styles['usage-display']}>
                  {selectedWord.full_entry.usage}
                </div>
              </div>
            )}
          </Stack>
        )}
      </Modal>
      {/* Add New Word Modal */}
      <Modal
        opened={addWordModalOpened}
        onClose={() => {
          setAddWordModalOpened(false)
          setNewWordData({ chuukese: '', english: '', definition: '', grammar: '' })
          setError('')
        }}
        title={
          <Group gap="xs">
            <IconFileText size={20} />
            <Text size="xl" fw={700}>Add Word to Dictionary</Text>
          </Group>
        }
        size="lg"
      >
        <Stack gap="md">
          {/* Chuukese Word (readonly) */}
          <div>
            <Text size="sm" c="dimmed" fw={500} mb={4}>Chuukese Word</Text>
            <Text size="lg" fw={700} c="blue.7">{newWordData.chuukese}</Text>
          </div>

          {/* English Translation */}
          <div>
            <Text size="sm" c="dimmed" fw={500} mb={4}>English Translation *</Text>
            <Textarea
              placeholder="Enter English translation"
              value={newWordData.english}
              onChange={(e) => setNewWordData({ ...newWordData, english: e.target.value })}
              minRows={1}
              required
            />
          </div>

          {/* Grammar Type */}
          <div>
            <Text size="sm" c="dimmed" fw={500} mb={4}>Grammar Type *</Text>
            <Textarea
              placeholder="e.g., noun, verb, adjective"
              value={newWordData.grammar}
              onChange={(e) => setNewWordData({ ...newWordData, grammar: e.target.value })}
              minRows={1}
              required
            />
          </div>

          {/* Definition */}
          <div>
            <Text size="sm" c="dimmed" fw={500} mb={4}>Definition (Optional)</Text>
            <Textarea
              placeholder="Enter detailed definition"
              value={newWordData.definition}
              onChange={(e) => setNewWordData({ ...newWordData, definition: e.target.value })}
              minRows={3}
            />
          </div>

          {/* Info about automatic fields */}
          <Paper p="sm" withBorder bg="blue.0" radius="md">
            <Text size="xs" c="dimmed">
              This word will be automatically saved with:
              <br />• Confidence: 100%
              <br />• Verified: Yes
              <br />• Example sentence: "{sentence}"
              <br />• Type: sentence
            </Text>
          </Paper>

          {/* Error Display */}
          {error && (
            <Alert icon={<IconAlertCircle size={16} />} color="red" radius="md">
              {error}
            </Alert>
          )}

          {/* Action Buttons */}
          <Group justify="flex-end" gap="sm">
            <Button
              variant="subtle"
              onClick={() => {
                setAddWordModalOpened(false)
                setNewWordData({ chuukese: '', english: '', definition: '', grammar: '' })
                setError('')
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={addNewWord}
              loading={saveLoading}
              leftSection={<IconFileText size={16} />}
            >
              Add to Dictionary
            </Button>
          </Group>
        </Stack>
      </Modal>    </Container>
  )
}

export default Sentences
