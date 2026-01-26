import { useState, useCallback, useMemo } from 'react'
import { Card, Title, Text, Stack, Group, Badge, Paper, Button, Progress, Alert } from '@mantine/core'
import { IconHandStop, IconUser, IconMapPin, IconQuestionMark, IconHeart, IconUsers, IconCheck, IconX, IconRefresh, IconArrowRight, IconInfoCircle, IconTrophy } from '@tabler/icons-react'
import composeData from '../data/composeData.json'
import styles from './Compose.module.css'

interface Word {
  chuukese: string
  english: string
  position?: number
}

interface Sentence {
  id: string
  english: string
  chuukese: string
  words: Word[]
  distractors: Word[]
  notes: string
}

interface Category {
  id: string
  label: string
  icon: string
  sentences: Sentence[]
}

const categories = composeData.categories as Category[]

// Icon mapping
const iconMap: Record<string, React.ReactNode> = {
  hand: <IconHandStop size={18} />,
  user: <IconUser size={18} />,
  map: <IconMapPin size={18} />,
  location: <IconMapPin size={18} />,
  question: <IconQuestionMark size={18} />,
  heart: <IconHeart size={18} />,
  users: <IconUsers size={18} />,
}

// Shuffle array helper
function shuffleArray<T>(array: T[]): T[] {
  const shuffled = [...array]
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
  }
  return shuffled
}

function Compose() {
  const [activeCategory, setActiveCategory] = useState<string>(categories[0]?.id || '')
  const [currentSentenceIndex, setCurrentSentenceIndex] = useState(0)
  const [selectedWords, setSelectedWords] = useState<Word[]>([])
  const [availableWords, setAvailableWords] = useState<Word[]>([])
  const [isChecked, setIsChecked] = useState(false)
  const [isCorrect, setIsCorrect] = useState(false)
  const [score, setScore] = useState(0)
  const [totalAttempts, setTotalAttempts] = useState(0)
  const [showHint, setShowHint] = useState(false)

  const currentCategory = categories.find(c => c.id === activeCategory)
  const currentSentence = currentCategory?.sentences[currentSentenceIndex]

  // Initialize available words when sentence changes
  const initializeWords = useCallback((sentence: Sentence) => {
    const allWords = [...sentence.words, ...sentence.distractors]
    setAvailableWords(shuffleArray(allWords))
    setSelectedWords([])
    setIsChecked(false)
    setIsCorrect(false)
    setShowHint(false)
  }, [])

  // Initialize on first load
  useMemo(() => {
    if (currentSentence) {
      initializeWords(currentSentence)
    }
  }, [currentSentence?.id])

  const handleCategoryChange = useCallback((categoryId: string) => {
    setActiveCategory(categoryId)
    setCurrentSentenceIndex(0)
    setScore(0)
    setTotalAttempts(0)
    const category = categories.find(c => c.id === categoryId)
    if (category?.sentences[0]) {
      initializeWords(category.sentences[0])
    }
  }, [initializeWords])

  const handleWordSelect = useCallback((word: Word) => {
    if (isChecked) return
    
    // Move word from available to selected
    setAvailableWords(prev => prev.filter(w => w.chuukese !== word.chuukese))
    setSelectedWords(prev => [...prev, word])
  }, [isChecked])

  const handleWordRemove = useCallback((word: Word, index: number) => {
    if (isChecked) return
    
    // Move word from selected back to available
    setSelectedWords(prev => prev.filter((_, i) => i !== index))
    setAvailableWords(prev => [...prev, word])
  }, [isChecked])

  const handleCheck = useCallback(() => {
    if (!currentSentence) return
    
    // Check if selected words match the correct order
    const correctOrder = currentSentence.words.map(w => w.chuukese).join(' ')
    const userOrder = selectedWords.map(w => w.chuukese).join(' ')
    
    const correct = correctOrder === userOrder
    setIsCorrect(correct)
    setIsChecked(true)
    setTotalAttempts(prev => prev + 1)
    
    if (correct) {
      setScore(prev => prev + 1)
    }
  }, [currentSentence, selectedWords])

  const handleNextSentence = useCallback(() => {
    if (!currentCategory) return
    
    const nextIndex = currentSentenceIndex + 1
    if (nextIndex < currentCategory.sentences.length) {
      setCurrentSentenceIndex(nextIndex)
      initializeWords(currentCategory.sentences[nextIndex])
    } else {
      // End of category - show summary or restart
      setCurrentSentenceIndex(0)
      if (currentCategory.sentences[0]) {
        initializeWords(currentCategory.sentences[0])
      }
    }
  }, [currentCategory, currentSentenceIndex, initializeWords])

  const handleRetry = useCallback(() => {
    if (currentSentence) {
      initializeWords(currentSentence)
    }
  }, [currentSentence, initializeWords])

  const handleShowHint = useCallback(() => {
    setShowHint(true)
  }, [])

  const progressPercent = currentCategory 
    ? ((currentSentenceIndex + 1) / currentCategory.sentences.length) * 100 
    : 0

  return (
    <Stack gap="lg" className={styles.container}>
      <Card shadow="sm" p="lg" radius="md">
        <Group justify="space-between" mb="md">
          <div>
            <Title order={2}>Build Sentences</Title>
            <Text c="dimmed" size="sm" mt={4}>
              Arrange the words to form the correct Chuukese sentence
            </Text>
          </div>
          <Group gap="sm">
            <Badge size="lg" variant="light" color="green" leftSection={<IconTrophy size={14} />}>
              {score} / {totalAttempts}
            </Badge>
          </Group>
        </Group>

        {/* Category Navigation */}
        <div className={styles.categoryNav}>
          {categories.map(category => (
            <button
              key={category.id}
              className={activeCategory === category.id ? styles.categoryButtonActive : styles.categoryButton}
              onClick={() => handleCategoryChange(category.id)}
            >
              {iconMap[category.icon] || <IconUser size={18} />}
              <span>{category.label}</span>
              <Badge size="sm" variant="light" color={activeCategory === category.id ? 'violet' : 'gray'}>
                {category.sentences.length}
              </Badge>
            </button>
          ))}
        </div>

        {/* Progress Bar */}
        {currentCategory && (
          <div className={styles.progressSection}>
            <Group justify="space-between" mb="xs">
              <Text size="sm" c="dimmed">
                Sentence {currentSentenceIndex + 1} of {currentCategory.sentences.length}
              </Text>
              <Text size="sm" c="dimmed">
                {Math.round(progressPercent)}% complete
              </Text>
            </Group>
            <Progress value={progressPercent} color="violet" size="sm" radius="xl" />
          </div>
        )}

        {/* Current Sentence Challenge */}
        {currentSentence && (
          <Paper className={styles.challengeCard}>
            {/* English sentence to translate */}
            <div className={styles.targetSentence}>
              <Text size="xs" c="dimmed" tt="uppercase" fw={600} mb={4}>
                Translate this sentence:
              </Text>
              <Text className={styles.englishText}>
                "{currentSentence.english}"
              </Text>
            </div>

            {/* Selected words area (drop zone) */}
            <div className={styles.answerArea}>
              <Text size="xs" c="dimmed" tt="uppercase" fw={600} mb={8}>
                Your answer:
              </Text>
              <div className={styles.selectedWordsContainer}>
                {selectedWords.length === 0 ? (
                  <Text c="dimmed" size="sm" className={styles.placeholder}>
                    Tap words below to build your sentence...
                  </Text>
                ) : (
                  selectedWords.map((word, index) => (
                    <button
                      key={`${word.chuukese}-${index}`}
                      className={`${styles.wordChip} ${styles.selectedWord} ${
                        isChecked 
                          ? isCorrect 
                            ? styles.wordCorrect 
                            : currentSentence.words[index]?.chuukese === word.chuukese
                              ? styles.wordCorrect
                              : styles.wordIncorrect
                          : ''
                      }`}
                      onClick={() => handleWordRemove(word, index)}
                      disabled={isChecked}
                    >
                      <span className={styles.wordChuukese}>{word.chuukese}</span>
                      <span className={styles.wordEnglish}>{word.english}</span>
                    </button>
                  ))
                )}
              </div>
            </div>

            {/* Available words to choose from */}
            <div className={styles.wordBankArea}>
              <Text size="xs" c="dimmed" tt="uppercase" fw={600} mb={8}>
                Available words:
              </Text>
              <div className={styles.wordBank}>
                {availableWords.map((word, index) => (
                  <button
                    key={`${word.chuukese}-${index}`}
                    className={styles.wordChip}
                    onClick={() => handleWordSelect(word)}
                    disabled={isChecked}
                  >
                    <span className={styles.wordChuukese}>{word.chuukese}</span>
                    <span className={styles.wordEnglish}>{word.english}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Hint */}
            {showHint && !isChecked && (
              <Alert 
                icon={<IconInfoCircle size={16} />} 
                color="blue" 
                variant="light"
                className={styles.hintAlert}
              >
                <Text size="sm"><strong>Hint:</strong> {currentSentence.notes}</Text>
                <Text size="sm" mt={4}>
                  <strong>First word:</strong> {currentSentence.words[0]?.chuukese} ({currentSentence.words[0]?.english})
                </Text>
              </Alert>
            )}

            {/* Result feedback */}
            {isChecked && (
              <Alert 
                icon={isCorrect ? <IconCheck size={16} /> : <IconX size={16} />}
                color={isCorrect ? 'green' : 'red'}
                variant="light"
                className={styles.resultAlert}
              >
                {isCorrect ? (
                  <>
                    <Text fw={600}>Correct! 🎉</Text>
                    <Text size="sm" mt={4}>{currentSentence.notes}</Text>
                  </>
                ) : (
                  <>
                    <Text fw={600}>Not quite right</Text>
                    <Text size="sm" mt={4}>
                      <strong>Correct answer:</strong> {currentSentence.chuukese}
                    </Text>
                    <Text size="sm" mt={2}>{currentSentence.notes}</Text>
                  </>
                )}
              </Alert>
            )}

            {/* Action buttons */}
            <Group mt="lg" justify="center" gap="sm">
              {!isChecked ? (
                <>
                  <Button 
                    variant="light" 
                    color="gray" 
                    onClick={handleRetry}
                    leftSection={<IconRefresh size={16} />}
                  >
                    Clear
                  </Button>
                  {!showHint && (
                    <Button 
                      variant="light" 
                      color="blue" 
                      onClick={handleShowHint}
                      leftSection={<IconInfoCircle size={16} />}
                    >
                      Hint
                    </Button>
                  )}
                  <Button 
                    color="violet" 
                    onClick={handleCheck}
                    disabled={selectedWords.length === 0}
                    leftSection={<IconCheck size={16} />}
                  >
                    Check Answer
                  </Button>
                </>
              ) : (
                <>
                  {!isCorrect && (
                    <Button 
                      variant="light" 
                      color="orange" 
                      onClick={handleRetry}
                      leftSection={<IconRefresh size={16} />}
                    >
                      Try Again
                    </Button>
                  )}
                  <Button 
                    color="violet" 
                    onClick={handleNextSentence}
                    rightSection={<IconArrowRight size={16} />}
                  >
                    {currentSentenceIndex + 1 >= (currentCategory?.sentences.length || 0) 
                      ? 'Start Over' 
                      : 'Next Sentence'}
                  </Button>
                </>
              )}
            </Group>
          </Paper>
        )}
      </Card>
    </Stack>
  )
}

export default Compose
