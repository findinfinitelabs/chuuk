import { useState, useEffect, useCallback } from 'react'
import { Card, Title, Text, Stack, Loader, Alert, Badge, Grid, Accordion, Table, Group, Divider, NavLink, Paper, Button, Box, Switch, SimpleGrid } from '@mantine/core'
import { IconAlertCircle, IconBook, IconChevronRight, IconNumbers, IconUsers, IconClock, IconMapPin, IconHandFinger, IconUser, IconPalette, IconRun, IconEye, IconPuzzle, IconRefresh, IconCheck, IconX } from '@tabler/icons-react'
import axios from 'axios'
import grammarData from '../data/grammarData.json'

interface GrammarType {
  grammar: string
  count: number
  examples: {
    chuukese_word: string
    english_translation: string
  }[]
}

type NounCategory = 'general' | 'longThin' | 'round' | 'animate'

interface Noun {
  chuukese: string
  english: string
  category: NounCategory
}

interface Location {
  chuukese: string
  english: string
  preposition: string
  englishPreposition: string
}

type GrammarCategory = 'numbers' | 'singular-plural' | 'time' | 'location' | 'this-that' | 'pronouns' | 'descriptions' | 'actions'

const grammarCategories = [
  { id: 'numbers' as GrammarCategory, label: 'Numbers', icon: IconNumbers },
  { id: 'singular-plural' as GrammarCategory, label: 'Singular and Plural', icon: IconUsers },
  { id: 'time' as GrammarCategory, label: 'Time', icon: IconClock },
  { id: 'location' as GrammarCategory, label: 'Location', icon: IconMapPin },
  { id: 'this-that' as GrammarCategory, label: 'This and That', icon: IconHandFinger },
  { id: 'pronouns' as GrammarCategory, label: 'Personal Pronouns', icon: IconUser },
  { id: 'descriptions' as GrammarCategory, label: 'Descriptions', icon: IconPalette },
  { id: 'actions' as GrammarCategory, label: 'Actions', icon: IconRun },
]

// Data from JSON
const { numbers: numberSystems, nouns, locations, existentialVerb, article, sentences, pronouns } = grammarData as {
  numbers: Record<string, { label: string; words: { chuukese: string; english: string }[] }>
  nouns: Noun[]
  locations: Location[]
  existentialVerb: { chuukese: string; english: string }
  article: { chuukese: string; english: string }
  sentences: { id: string; name: string; pattern: string; english: string; example: { chuukese: string; english: string } }[]
  pronouns: { chuukese: string; english: string }[]
}

function Grammar() {
  const [loading, setLoading] = useState(true)
  const [grammarTypes, setGrammarTypes] = useState<GrammarType[]>([])
  const [error, setError] = useState('')
  const [activeCategory, setActiveCategory] = useState<GrammarCategory | null>(null)
  const [activeSentence, setActiveSentence] = useState<string>('existential')
  const [selectedNumber, setSelectedNumber] = useState<number | null>(1)
  const [highlightedNumber, setHighlightedNumber] = useState<number | null>(null)
  const [selectedNoun, setSelectedNoun] = useState<number>(0)
  const [highlightedNoun, setHighlightedNoun] = useState<number | null>(null)
  const [selectedLocation, setSelectedLocation] = useState<number>(0)
  const [highlightedLocation, setHighlightedLocation] = useState<number | null>(null)
  const [selectedPronoun] = useState<number>(0)
  // const [highlightedPronoun, setHighlightedPronoun] = useState<number | null>(null)
  
  // Build Mode state
  type BuildSlot = 'subject' | 'verb' | 'number' | 'noun' | 'prep' | 'article' | 'location'
  const [mode, setMode] = useState<'explore' | 'build'>('explore')
  const [buildOrder, setBuildOrder] = useState<BuildSlot[]>([])
  const [buildAnswers, setBuildAnswers] = useState<Record<BuildSlot, string | null>>({
    subject: null, verb: null, number: null, noun: null, prep: null, article: null, location: null
  })
  const [buildCorrect, setBuildCorrect] = useState<Record<BuildSlot, boolean | null>>({
    subject: null, verb: null, number: null, noun: null, prep: null, article: null, location: null
  })
  const [showBuildResult, setShowBuildResult] = useState(false)
  const [cumulativeScore, setCumulativeScore] = useState(0)

  // The correct sentence structure order depends on active sentence
  const getSentenceSlots = useCallback((): BuildSlot[] => {
    if (activeSentence === 'possession') {
      return ['subject', 'verb', 'number', 'noun']
    }
    return ['subject', 'verb', 'number', 'noun', 'prep', 'article', 'location']
  }, [activeSentence])
  
  const sentenceSlots = getSentenceSlots()
  
  // Get badge based on cumulative score
  const getBadge = useCallback(() => {
    if (cumulativeScore >= 500) return { label: 'Proficient', color: '#FFD700', icon: '🏆' }
    if (cumulativeScore >= 200) return { label: 'Intermediate', color: '#C0C0C0', icon: '🥈' }
    if (cumulativeScore >= 100) return { label: 'Beginner', color: '#CD7F32', icon: '🥉' }
    return null
  }, [cumulativeScore])

  useEffect(() => {
    loadGrammarData()
  }, [])

  const loadGrammarData = async () => {
    setLoading(true)
    setError('')

    try {
      const response = await axios.get('/api/grammar/types')
      setGrammarTypes(response.data.grammar_types || [])
    } catch (err) {
      setError('Error loading grammar data')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const grammarDescriptions: Record<string, string> = {
    'n.': 'Noun - A word that represents a person, place, thing, or idea',
    'v.': 'Verb - A word that describes an action, state, or occurrence',
    'vi.': 'Intransitive Verb - A verb that does not require a direct object',
    'vt.': 'Transitive Verb - A verb that requires a direct object',
    'adj.': 'Adjective - A word that describes or modifies a noun',
    'adv.': 'Adverb - A word that modifies a verb, adjective, or other adverb',
    'prep.': 'Preposition - A word that shows relationship between a noun/pronoun and other words',
    'conj.': 'Conjunction - A word that connects words, phrases, or clauses',
    'pron.': 'Pronoun - A word that takes the place of a noun',
    'int.': 'Interjection - A word or phrase that expresses strong emotion',
    'num.': 'Numeral - A word that represents a number',
    'part.': 'Particle - A function word that does not belong to main parts of speech',
    'dem.': 'Demonstrative - A word that points to a specific thing',
    'interrog.': 'Interrogative - A word used to ask questions',
  }

  const handleNumberSelect = useCallback((num: number) => {
    setSelectedNumber(num)
    setHighlightedNumber(num)
    
    // Clear highlight after 5 seconds
    setTimeout(() => {
      setHighlightedNumber(null)
    }, 5000)
  }, [])

  const handleNounSelect = useCallback((idx: number) => {
    setSelectedNoun(idx)
    setHighlightedNoun(idx)
    // Reset number selection when noun category changes
    setSelectedNumber(1)
    setHighlightedNumber(null)
    
    // Clear highlight after 5 seconds
    setTimeout(() => {
      setHighlightedNoun(null)
    }, 5000)
  }, [])

  const handleLocationSelect = useCallback((idx: number) => {
    setSelectedLocation(idx)
    setHighlightedLocation(idx)
    
    // Clear highlight after 5 seconds
    setTimeout(() => {
      setHighlightedLocation(null)
    }, 5000)
  }, [])

  const getEnglishNumber = (num: number): string => {
    const numbers = ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
    return numbers[num - 1] || 'one'
  }

  const getEnglishPlural = (num: number, noun: Noun): string => {
    const word = noun.english
    if (num === 1) return word
    // Simple pluralization
    if (word.endsWith('y')) return word.slice(0, -1) + 'ies'
    if (word.endsWith('s') || word.endsWith('x') || word.endsWith('ch') || word.endsWith('sh')) return word + 'es'
    return word + 's'
  }

  // Build mode functions
  // New sentence structure: A wor eu puk woon ewe sanif (There is one book on the shelf)
  const getTargetSentence = useCallback(() => {
    const currentNoun = nouns[selectedNoun]
    const currentCategory = currentNoun.category
    const activeNumberSystem = numberSystems[currentCategory]
    const currentNumberWord = selectedNumber ? activeNumberSystem.words[selectedNumber - 1].chuukese : ''
    const currentLocation = locations[selectedLocation]
    
    return {
      subject: 'A',
      verb: existentialVerb.chuukese,
      number: currentNumberWord,
      noun: currentNoun.chuukese,
      prep: currentLocation.preposition,
      article: article.chuukese,
      location: currentLocation.chuukese,
    }
  }, [selectedNoun, selectedNumber, selectedLocation])

  const slotLabels: Record<string, string> = {
    subject: 'Subject',
    verb: 'Verb',
    number: 'Number',
    noun: 'Noun',
    prep: 'Preposition',
    article: 'Article',
    location: 'Location',
  }

  const resetBuildMode = useCallback(() => {
    setBuildOrder([])
    setBuildAnswers({ subject: null, verb: null, number: null, noun: null, prep: null, article: null, location: null })
    setBuildCorrect({ subject: null, verb: null, number: null, noun: null, prep: null, article: null, location: null })
    setShowBuildResult(false)
  }, [])

  const handleBuildSlotClick = useCallback((slot: string) => {
    if (mode !== 'build' || showBuildResult) return
    
    const targetSentence = getTargetSentence()
    const slotKey = slot as keyof typeof targetSentence
    
    // Add this slot to the build order
    const newOrder = [...buildOrder, slotKey]
    setBuildOrder(newOrder)
    
    // Record the answer (what word goes in this slot)
    const newAnswers = { ...buildAnswers, [slotKey]: targetSentence[slotKey] }
    setBuildAnswers(newAnswers)
    
    // Check if correct position in sentence structure (immediate feedback)
    const expectedSlot = sentenceSlots[buildOrder.length]
    const isCorrectPosition = slotKey === expectedSlot
    const newCorrect = { ...buildCorrect, [slotKey]: isCorrectPosition }
    setBuildCorrect(newCorrect)
    
    // If all slots filled, show result and add to score
    if (newOrder.length === 7) {
      setShowBuildResult(true)
      // Calculate score for this round - 1 point per correct position
      let roundScore = 0
      sentenceSlots.forEach((s, idx) => {
        if (newOrder[idx] === s) roundScore += 1
      })
      setCumulativeScore(prev => prev + roundScore)
    }
  }, [mode, buildOrder, buildAnswers, buildCorrect, getTargetSentence, showBuildResult])

  const handleRemoveSlot = useCallback((indexToRemove: number) => {
    if (showBuildResult) return
    
    const slotToRemove = buildOrder[indexToRemove]
    const newOrder = buildOrder.filter((_, idx) => idx !== indexToRemove)
    setBuildOrder(newOrder)
    
    // Reset the correct status for removed slot
    const newCorrect = { ...buildCorrect, [slotToRemove]: null }
    // Recalculate correctness for remaining slots
    newOrder.forEach((slot, idx) => {
      newCorrect[slot] = slot === sentenceSlots[idx]
    })
    setBuildCorrect(newCorrect)
    
    // Reset the answer for removed slot
    setBuildAnswers({ ...buildAnswers, [slotToRemove]: null })
  }, [buildOrder, buildAnswers, buildCorrect, showBuildResult])

  const getBuildScore = useCallback(() => {
    let correct = 0
    sentenceSlots.forEach((slot, idx) => {
      if (buildOrder[idx] === slot) correct++
    })
    return correct
  }, [buildOrder])

  const renderNumbersContent = () => {
    const currentNoun = nouns[selectedNoun]
    const currentCategory = currentNoun.category
    const activeNumberSystem = numberSystems[currentCategory]
    const currentNumberWord = selectedNumber ? activeNumberSystem.words[selectedNumber - 1].chuukese : ''
    const currentLocation = locations[selectedLocation]
    const currentPronoun = pronouns[selectedPronoun]
    const isNumberHighlighted = highlightedNumber !== null
    const isNounHighlighted = highlightedNoun !== null
    const isLocationHighlighted = highlightedLocation !== null
    
    // Scrambled order for build mode depends on sentence type
    const scrambledSlots: BuildSlot[] = activeSentence === 'possession' 
      ? ['noun', 'subject', 'verb', 'number']
      : ['noun', 'location', 'subject', 'verb', 'article', 'prep', 'number']
    
    // Get remaining unplaced slots
    const remainingSlots = scrambledSlots.filter(slot => !buildOrder.includes(slot))
    
    return (
      <Stack gap="xl">
        {/* Mode Toggle */}
        <Group justify="space-between" align="center">
          <Group gap="sm">
            <IconEye size={18} color={mode === 'explore' ? '#228be6' : '#adb5bd'} />
            <Switch
              checked={mode === 'build'}
              onChange={(e) => {
                const newMode = e.currentTarget.checked ? 'build' : 'explore'
                setMode(newMode)
                if (newMode === 'build') resetBuildMode()
              }}
              size="lg"
              onLabel={<IconPuzzle size={14} />}
              offLabel={<IconEye size={14} />}
            />
            <IconPuzzle size={18} color={mode === 'build' ? '#3B1898' : '#adb5bd'} />
            <Text size="sm" fw={500} style={{ color: mode === 'build' ? '#3B1898' : '#228be6' }}>
              {mode === 'build' ? 'Build Mode' : 'Explore Mode'}
            </Text>
          </Group>
          {mode === 'build' && (
            <Group gap="md" align="center">
              {/* Badge */}
              {getBadge() && (
                <Badge 
                  size="lg" 
                  variant="filled" 
                  style={{ 
                    backgroundColor: getBadge()!.color, 
                    color: getBadge()!.color === '#FFD700' ? '#000' : '#fff',
                    padding: '8px 12px',
                  }}
                  leftSection={getBadge()!.icon}
                >
                  {getBadge()!.label}
                </Badge>
              )}
              {/* Score */}
              <Text size="xl" fw={700} style={{ color: '#3B1898', fontSize: '1.5rem' }}>
                {cumulativeScore} pts
              </Text>
              {/* Reset Button */}
              <Button 
                variant="subtle" 
                size="xs" 
                leftSection={<IconRefresh size={14} />}
                onClick={resetBuildMode}
              >
                Reset
              </Button>
            </Group>
          )}
        </Group>

        {/* Build Mode UI */}
        {mode === 'build' && (
          <Stack gap="md" style={{ position: 'relative' }}>
            {/* Page-level Confetti animation */}
            {showBuildResult && getBuildScore() === sentenceSlots.length && (
              <Box
                style={{
                  position: 'fixed',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  pointerEvents: 'none',
                  zIndex: 1000,
                  overflow: 'hidden',
                }}
              >
                {[...Array(50)].map((_, i) => (
                  <Box
                    key={i}
                    style={{
                      position: 'absolute',
                      width: `${8 + Math.random() * 8}px`,
                      height: `${8 + Math.random() * 8}px`,
                      borderRadius: Math.random() > 0.5 ? '50%' : '2px',
                      backgroundColor: ['#ff6b6b', '#ffd93d', '#27B249', '#4d96ff', '#3B1898', '#ff9f43', '#e64980', '#20c997'][i % 8],
                      left: `${Math.random() * 100}%`,
                      top: '-20px',
                      animation: `confetti ${2 + Math.random() * 2}s ease-out ${Math.random() * 0.5}s forwards`,
                    }}
                  />
                ))}
                <style>{`
                  @keyframes confetti {
                    0% {
                      transform: translateY(0) rotate(0deg);
                      opacity: 1;
                    }
                    100% {
                      transform: translateY(100vh) rotate(${360 + Math.random() * 360}deg);
                      opacity: 0;
                    }
                  }
                `}</style>
              </Box>
            )}

            {/* Target Chuukese sentence to arrange */}
            <Paper p="md" withBorder style={{ backgroundColor: '#f3f0f7' }} radius="md">
              <Text size="sm" fw={600} style={{ color: '#3B1898' }} mb="xs">Arrange the parts to build this sentence:</Text>
              {activeSentence === 'possession' ? (
                <>
                  <Text size="xl" fw={700} style={{ color: '#3B1898', fontSize: '1.5rem' }}>
                    {currentPronoun.chuukese} {existentialVerb.chuukese} {currentNumberWord} {currentNoun.chuukese}
                  </Text>
                  <Text size="sm" c="dimmed" mt="xs">
                    ({currentPronoun.english} {selectedNumber === 1 ? 'have' : 'have'} {selectedNumber ? getEnglishNumber(selectedNumber) : 'one'} {selectedNumber ? getEnglishPlural(selectedNumber, currentNoun) : currentNoun.english})
                  </Text>
                </>
              ) : (
                <>
                  <Text size="xl" fw={700} style={{ color: '#3B1898', fontSize: '1.5rem' }}>
                    A {existentialVerb.chuukese} {currentNumberWord} {currentNoun.chuukese} {currentLocation.preposition} {article.chuukese} {currentLocation.chuukese}
                  </Text>
                  <Text size="sm" c="dimmed" mt="xs">
                    (There {selectedNumber === 1 ? 'is' : 'are'} {selectedNumber ? getEnglishNumber(selectedNumber) : 'one'} {selectedNumber ? getEnglishPlural(selectedNumber, currentNoun) : currentNoun.english} {currentLocation.englishPreposition} {currentLocation.english})
                  </Text>
                </>
              )}
            </Paper>

            {/* Available pills to pick from */}
            {remainingSlots.length > 0 && (
              <Box>
                <Text size="sm" c="dimmed" mb="xs">Click parts in order:</Text>
                <Group gap="sm">
                  {remainingSlots.map((slot) => (
                    <Badge
                      key={slot}
                      size="xl"
                      variant="light"
                      color="gray"
                      style={{ 
                        cursor: 'pointer',
                        padding: '12px 16px',
                        fontSize: '0.95rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                      onClick={() => handleBuildSlotClick(slot)}
                    >
                      {slotLabels[slot]}
                    </Badge>
                  ))}
                </Group>
              </Box>
            )}

            {/* Answer area - where pills land */}
            <Paper 
              p="md" 
              withBorder 
              radius="md" 
              style={{ 
                backgroundColor: '#ffffff',
              }}
            >
              <Text size="sm" c="dimmed" mb="xs">Your sentence structure:</Text>
              <Group gap="sm" mih={50}>
                {buildOrder.length === 0 ? (
                  <Text c="dimmed" fs="italic">Click parts above to start building...</Text>
                ) : (
                  buildOrder.map((slot, idx) => {
                    const isCorrect = sentenceSlots[idx] === slot
                    return (
                      <Badge
                        key={`answer-${idx}`}
                        size="xl"
                        variant="filled"
                        style={{ 
                          padding: '12px 16px', 
                          fontSize: '0.95rem',
                          backgroundColor: isCorrect ? '#27B249' : '#e03131',
                          color: 'white',
                          cursor: !isCorrect && !showBuildResult ? 'pointer' : 'default',
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                        rightSection={
                          isCorrect 
                            ? <IconCheck size={14} color="white" /> 
                            : <IconX 
                                size={14} 
                                color="white" 
                                style={{ cursor: !showBuildResult ? 'pointer' : 'default' }}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  if (!showBuildResult) handleRemoveSlot(idx)
                                }}
                              />
                        }
                        onClick={() => {
                          if (!isCorrect && !showBuildResult) handleRemoveSlot(idx)
                        }}
                      >
                        {slotLabels[slot]}
                      </Badge>
                    )
                  })
                )}
              </Group>
            </Paper>

            {/* Show the Chuukese sentence being built progressively */}
            {buildOrder.length > 0 && (
              <Paper p="lg" withBorder radius="md" bg="blue.0">
                <Text size="sm" fw={600} c="blue.7" mb="md">The Chuukese sentence:</Text>
                <Group gap="xl" justify="flex-start" wrap="wrap">
                  {buildOrder.map((slot, idx) => {
                    const wordMap: Record<BuildSlot, { chuukese: string; english: string }> = activeSentence === 'possession' ? {
                      subject: { chuukese: currentPronoun.chuukese, english: currentPronoun.english },
                      verb: { chuukese: existentialVerb.chuukese, english: 'have' },
                      number: { chuukese: currentNumberWord || '—', english: selectedNumber ? getEnglishNumber(selectedNumber) : '—' },
                      noun: { chuukese: currentNoun.chuukese, english: currentNoun.english },
                      prep: { chuukese: '', english: '' },
                      article: { chuukese: '', english: '' },
                      location: { chuukese: '', english: '' },
                    } : {
                      subject: { chuukese: 'A', english: 'There' },
                      verb: { chuukese: existentialVerb.chuukese, english: existentialVerb.english },
                      number: { chuukese: currentNumberWord || '—', english: selectedNumber ? getEnglishNumber(selectedNumber) : '—' },
                      noun: { chuukese: currentNoun.chuukese, english: currentNoun.english },
                      prep: { chuukese: currentLocation.preposition, english: currentLocation.englishPreposition.replace('the ', '') },
                      article: { chuukese: article.chuukese, english: article.english },
                      location: { chuukese: currentLocation.chuukese, english: currentLocation.english },
                    }
                    const word = wordMap[slot]
                    const isCorrectPosition = sentenceSlots[idx] === slot
                    return (
                      <Box key={`sentence-${idx}`} ta="center">
                        <Text 
                          size="xl" 
                          fw={700} 
                          style={{ 
                            color: isCorrectPosition ? '#27B249' : '#e03131',
                          }}
                        >
                          {word.chuukese}
                        </Text>
                        <Text size="xs" c="dimmed" tt="uppercase">{slotLabels[slot]}</Text>
                        <Text size="sm" c="blue.7">{word.english}</Text>
                      </Box>
                    )
                  })}
                </Group>
              </Paper>
            )}

            {/* Score result after completion */}
            {showBuildResult && (
              <Alert 
                color={getBuildScore() === sentenceSlots.length ? 'green' : 'red'} 
                title={getBuildScore() === sentenceSlots.length ? 'Perfect! 🎉' : `Score: ${getBuildScore()}/${sentenceSlots.length}`}
              >
                {getBuildScore() === sentenceSlots.length 
                  ? 'You got the sentence structure correct!' 
                  : activeSentence === 'possession'
                    ? 'Correct order: Subject → Verb → Number → Noun'
                    : 'Correct order: Subject → Verb → Number → Noun → Preposition → Article → Location'}
              </Alert>
            )}
          </Stack>
        )}

        {/* Explore Mode UI */}
        {mode === 'explore' && (
          <>
            {/* Chuukese sentence with English below each word */}
            <Box py="sm">
              <Group gap="xl" justify="center" wrap="wrap">
                {activeSentence === 'possession' ? (
                  <>
                    <Box ta="center">
                      <Text size="xl" fw={700} style={{ fontSize: '1.6rem', lineHeight: 1.4 }}>{currentPronoun.chuukese}</Text>
                      <Text size="xs" c="dimmed" tt="uppercase">Subject</Text>
                      <Text size="sm" c="dimmed">{currentPronoun.english}</Text>
                    </Box>
                    <Box ta="center">
                      <Text size="xl" fw={700} style={{ fontSize: '1.6rem', lineHeight: 1.4 }}>{existentialVerb.chuukese}</Text>
                      <Text size="xs" c="dimmed" tt="uppercase">Verb</Text>
                      <Text size="sm" c="dimmed">have</Text>
                    </Box>
                    <Box ta="center">
                      <Text 
                        size="xl" 
                        fw={700} 
                        style={{ fontSize: '1.6rem', lineHeight: 1.4, color: isNumberHighlighted ? '#27B249' : 'inherit' }}
                      >
                        {currentNumberWord || '—'}
                      </Text>
                      <Text size="xs" c="dimmed" tt="uppercase">Number</Text>
                      <Text size="sm" c="dimmed">{selectedNumber ? getEnglishNumber(selectedNumber) : '—'}</Text>
                    </Box>
                    <Box ta="center">
                      <Text 
                        size="xl" 
                        fw={700} 
                        style={{ fontSize: '1.6rem', lineHeight: 1.4, color: isNounHighlighted ? '#27B249' : 'inherit' }}
                      >
                        {currentNoun.chuukese}
                      </Text>
                      <Text size="xs" c="dimmed" tt="uppercase">Noun</Text>
                      <Text size="sm" c="dimmed">{selectedNumber ? getEnglishPlural(selectedNumber, currentNoun) : currentNoun.english}</Text>
                    </Box>
                  </>
                ) : (
                  <>
                    <Box ta="center">
                      <Text size="xl" fw={700} style={{ fontSize: '1.6rem', lineHeight: 1.4 }}>A</Text>
                      <Text size="xs" c="dimmed" tt="uppercase">Subject</Text>
                      <Text size="sm" c="dimmed">There</Text>
                    </Box>
                    <Box ta="center">
                      <Text size="xl" fw={700} style={{ fontSize: '1.6rem', lineHeight: 1.4 }}>{existentialVerb.chuukese}</Text>
                      <Text size="xs" c="dimmed" tt="uppercase">Verb</Text>
                      <Text size="sm" c="dimmed">{selectedNumber === 1 ? 'is' : 'are'}</Text>
                    </Box>
                    <Box ta="center">
                      <Text 
                        size="xl" 
                        fw={700} 
                        style={{ fontSize: '1.6rem', lineHeight: 1.4, color: isNumberHighlighted ? '#27B249' : 'inherit' }}
                      >
                        {currentNumberWord || '—'}
                      </Text>
                      <Text size="xs" c="dimmed" tt="uppercase">Number</Text>
                      <Text size="sm" c="dimmed">{selectedNumber ? getEnglishNumber(selectedNumber) : '—'}</Text>
                    </Box>
                    <Box ta="center">
                      <Text 
                        size="xl" 
                        fw={700} 
                        style={{ fontSize: '1.6rem', lineHeight: 1.4, color: isNounHighlighted ? '#27B249' : 'inherit' }}
                      >
                        {currentNoun.chuukese}
                      </Text>
                      <Text size="xs" c="dimmed" tt="uppercase">Noun</Text>
                      <Text size="sm" c="dimmed">{selectedNumber ? getEnglishPlural(selectedNumber, currentNoun) : currentNoun.english}</Text>
                    </Box>
                    <Box ta="center">
                      <Text size="xl" fw={700} style={{ fontSize: '1.6rem', lineHeight: 1.4 }}>{currentLocation.preposition}</Text>
                      <Text size="xs" c="dimmed" tt="uppercase">Prep</Text>
                      <Text size="sm" c="dimmed">{currentLocation.englishPreposition.split(' ')[0]}</Text>
                    </Box>
                    <Box ta="center">
                      <Text size="xl" fw={700} style={{ fontSize: '1.6rem', lineHeight: 1.4 }}>{article.chuukese}</Text>
                      <Text size="xs" c="dimmed" tt="uppercase">Article</Text>
                      <Text size="sm" c="dimmed">{article.english}</Text>
                    </Box>
                    <Box ta="center">
                      <Text 
                        size="xl" 
                        fw={700} 
                        style={{ fontSize: '1.6rem', lineHeight: 1.4, color: isLocationHighlighted ? '#27B249' : 'inherit' }}
                      >
                        {currentLocation.chuukese}
                      </Text>
                      <Text size="xs" c="dimmed" tt="uppercase">Location</Text>
                      <Text size="sm" c="dimmed">{currentLocation.english}</Text>
                    </Box>
                  </>
                )}
              </Group>
              <Text ta="center" size="sm" c="dimmed" mt="xs">
                {activeSentence === 'possession' 
                  ? `"${currentPronoun.english} have ${selectedNumber ? getEnglishNumber(selectedNumber) : '—'} ${selectedNumber ? getEnglishPlural(selectedNumber, currentNoun) : currentNoun.english}."`
                  : `"There ${selectedNumber === 1 ? 'is' : 'are'} ${selectedNumber ? getEnglishNumber(selectedNumber) : '—'} ${selectedNumber ? getEnglishPlural(selectedNumber, currentNoun) : currentNoun.english + 's'} ${currentLocation.englishPreposition} ${currentLocation.english}."`
                }
              </Text>
            </Box>

            <Divider my="sm" />

            {/* Word selection - side by side cards */}
            <Grid gutter="xs">
              {/* Numbers Card - takes more space */}
              <Grid.Col span={{ base: 12, md: 6 }}>
                <Card shadow="xs" p="xs" radius="sm" withBorder h="100%">
                  <Text size="xs" fw={600} c="dimmed" mb="xs">Numbers:</Text>
                  <Stack gap={0}>
                    {Object.entries(numberSystems).map(([systemKey, system], systemIdx, arr) => {
                      const isActiveSystem = systemKey === currentCategory
                      const isLast = systemIdx === arr.length - 1
                      return (
                        <Box key={systemKey}>
                          <Group gap="xs" align="center" wrap="nowrap" py={4}>
                            <Text size="xs" c={isActiveSystem ? 'blue' : 'dimmed'} w={100} style={{ flexShrink: 0, fontSize: '0.7rem' }}>
                              {system.label.split('(')[0].trim()}:
                            </Text>
                            <Group gap={2} style={{ flexWrap: 'wrap' }}>
                              {system.words.map((word, idx) => {
                                const isSelected = selectedNumber === idx + 1 && isActiveSystem
                                const isHighlighted = highlightedNumber === idx + 1 && isActiveSystem
                                return (
                                  <Button
                                    key={`${systemKey}-${idx}`}
                                    variant="subtle"
                                    color={isActiveSystem ? 'blue' : 'gray'}
                                    size="xs"
                                    disabled={!isActiveSystem}
                                    onClick={() => handleNumberSelect(idx + 1)}
                                    styles={{
                                      root: {
                                        transition: 'all 0.3s ease',
                                        borderRadius: '1px',
                                        border: 'none',
                                        outline: 'none',
                                        padding: '10px 12px',
                                        minHeight: 'auto',
                                        height: 'auto',
                                        opacity: isActiveSystem ? 1 : 0.4,
                                        backgroundColor: isHighlighted ? '#27B249' : isSelected ? 'rgba(34, 139, 230, 0.15)' : 'rgba(0, 0, 0, 0.04)',
                                        color: isHighlighted ? 'white' : isSelected ? '#228be6' : 'inherit',
                                        '&:focus': { outline: 'none', boxShadow: 'none' },
                                        '&:focus-visible': { outline: 'none', boxShadow: 'none' },
                                      }
                                    }}
                                  >
                                    {word.chuukese}
                                  </Button>
                                )
                              })}
                            </Group>
                          </Group>
                          {!isLast && <Divider my={6} />}
                        </Box>
                      )
                    })}
                  </Stack>
                </Card>
              </Grid.Col>

              {/* Nouns Card */}
              <Grid.Col span={{ base: 6, md: 3 }}>
                <Card shadow="xs" p="xs" radius="sm" withBorder h="100%">
                  <Text size="xs" fw={600} c="dimmed" mb="xs">Nouns:</Text>
                  <SimpleGrid cols={2} spacing={4}>
                    {nouns.map((noun, idx) => {
                      const isSelected = selectedNoun === idx
                      const isHighlighted = highlightedNoun === idx
                      return (
                        <Button
                          key={`noun-${idx}`}
                          variant="subtle"
                          color="orange"
                          size="xs"
                          onClick={() => handleNounSelect(idx)}
                          styles={{
                            root: {
                              transition: 'all 0.3s ease',
                              borderRadius: '1px',
                              border: 'none',
                              outline: 'none',
                              padding: '10px 12px',
                              minHeight: 'auto',
                              height: 'auto',
                              backgroundColor: isHighlighted ? '#27B249' : isSelected ? 'rgba(255, 146, 43, 0.15)' : 'rgba(0, 0, 0, 0.04)',
                              color: isHighlighted ? 'white' : isSelected ? '#fd7e14' : 'inherit',
                              '&:focus': { outline: 'none', boxShadow: 'none' },
                              '&:focus-visible': { outline: 'none', boxShadow: 'none' },
                            }
                          }}
                        >
                          {noun.chuukese}
                        </Button>
                      )
                    })}
                  </SimpleGrid>
                </Card>
              </Grid.Col>

              {/* Locations Card */}
              <Grid.Col span={{ base: 6, md: 3 }}>
                <Card shadow="xs" p="xs" radius="sm" withBorder h="100%">
                  <Text size="xs" fw={600} c="dimmed" mb="xs">Locations:</Text>
                  <SimpleGrid cols={2} spacing={4}>
                    {locations.map((location, idx) => {
                      const isSelected = selectedLocation === idx
                      const isHighlighted = highlightedLocation === idx
                      return (
                        <Button
                          key={`location-${idx}`}
                          variant="subtle"
                          color="cyan"
                          size="xs"
                          onClick={() => handleLocationSelect(idx)}
                          styles={{
                            root: {
                              transition: 'all 0.3s ease',
                              borderRadius: '1px',
                              border: 'none',
                              outline: 'none',
                              padding: '10px 12px',
                              minHeight: 'auto',
                              height: 'auto',
                              backgroundColor: isHighlighted ? '#27B249' : isSelected ? 'rgba(21, 170, 191, 0.15)' : 'rgba(0, 0, 0, 0.04)',
                              color: isHighlighted ? 'white' : isSelected ? '#15aabf' : 'inherit',
                              '&:focus': { outline: 'none', boxShadow: 'none' },
                              '&:focus-visible': { outline: 'none', boxShadow: 'none' },
                            }
                          }}
                        >
                          {location.chuukese}
                        </Button>
                      )
                    })}
                  </SimpleGrid>
                </Card>
              </Grid.Col>
            </Grid>
          </>
        )}
      </Stack>
    )
  }

  const renderCategoryContent = () => {
    if (activeCategory === 'numbers') {
      return renderNumbersContent()
    }

    const category = grammarCategories.find(c => c.id === activeCategory)
    
    return (
      <Stack gap="md">
        <Title order={3}>{category?.label}</Title>
        <Text c="dimmed">
          Learn about {category?.label.toLowerCase()} in the Chuukese language.
        </Text>
        <Card shadow="sm" p="lg" radius="md" withBorder>
          <Stack gap="md">
            <Text>
              Content for <strong>{category?.label}</strong> will be displayed here.
            </Text>
            <Text size="sm" c="dimmed">
              This section will include grammar rules, examples, and practice exercises for {category?.label.toLowerCase()}.
            </Text>
          </Stack>
        </Card>
      </Stack>
    )
  }

  if (loading) {
    return (
      <Stack align="center" justify="center" h={300}>
        <Loader size="lg" />
        <Text>Loading grammar data...</Text>
      </Stack>
    )
  }

  return (
    <Stack gap="lg">
      <Title order={2}>Chuukese Grammar Reference</Title>
      
      <Text c="dimmed">
        Explore the different grammatical categories in the Chuukese language. 
        Each category includes examples from the dictionary.
      </Text>

      {error && (
        <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
          {error}
        </Alert>
      )}

      {/* Grammar Teaching Section with Left Nav */}
      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, sm: 4, md: 3 }}>
          <Paper shadow="sm" p="md" radius="md" withBorder style={{ overflow: 'hidden' }}>
            {/* Show Grammar Topics OR Sentence Patterns based on activeCategory */}
            {activeCategory === null ? (
              <>
                <Title order={5} mb="sm">Grammar Topics</Title>
                <Stack gap={4}>
                  {grammarCategories.map((category) => {
                    const Icon = category.icon
                    return (
                      <NavLink
                        key={category.id}
                        label={category.label}
                        leftSection={<Icon size="1rem" />}
                        rightSection={<IconChevronRight size="0.8rem" stroke={1.5} />}
                        onClick={() => setActiveCategory(category.id)}
                        variant="light"
                        style={{ borderRadius: '8px' }}
                      />
                    )
                  })}
                </Stack>
              </>
            ) : activeCategory === 'numbers' ? (
              <>
                <Group justify="space-between" align="center" mb="sm">
                  <Button 
                    variant="subtle" 
                    size="xs" 
                    leftSection={<IconChevronRight size={14} style={{ transform: 'rotate(180deg)' }} />}
                    onClick={() => setActiveCategory(null)}
                    px="xs"
                  >
                    Back
                  </Button>
                  <Title order={5}>Numbers</Title>
                  <Box w={50} /> {/* Spacer for centering */}
                </Group>
                <Divider mb="md" />
                <Stack gap={4}>
                  {sentences.map((sentence) => (
                    <Button
                      key={sentence.id}
                      variant={activeSentence === sentence.id ? 'filled' : 'subtle'}
                      color={activeSentence === sentence.id ? 'violet' : 'gray'}
                      size="xs"
                      fullWidth
                      justify="flex-start"
                      onClick={() => {
                        setActiveSentence(sentence.id)
                        resetBuildMode()
                      }}
                      styles={{
                        root: {
                          borderRadius: '8px',
                          fontWeight: activeSentence === sentence.id ? 500 : 400,
                          fontSize: '0.75rem',
                          padding: '8px 10px',
                        }
                      }}
                    >
                      {sentence.example.chuukese}
                    </Button>
                  ))}
                </Stack>
              </>
            ) : (
              <>
                <Group justify="space-between" align="center" mb="sm">
                  <Button 
                    variant="subtle" 
                    size="xs" 
                    leftSection={<IconChevronRight size={14} style={{ transform: 'rotate(180deg)' }} />}
                    onClick={() => setActiveCategory(null)}
                    px="xs"
                  >
                    Back
                  </Button>
                  <Title order={5}>{grammarCategories.find(c => c.id === activeCategory)?.label}</Title>
                  <Box w={50} /> {/* Spacer for centering */}
                </Group>
                <Divider mb="md" />
                <Text c="dimmed" size="sm">Coming soon...</Text>
              </>
            )}
          </Paper>
        </Grid.Col>
        
        <Grid.Col span={{ base: 12, sm: 8, md: 9 }}>
          <Paper shadow="sm" p="lg" radius="md" withBorder style={{ minHeight: '400px' }}>
            {activeCategory === null ? (
              <Stack align="center" justify="center" h={300}>
                <IconBook size={48} color="#adb5bd" />
                <Text c="dimmed" ta="center">Select a grammar topic from the left to start learning</Text>
              </Stack>
            ) : (
              renderCategoryContent()
            )}
          </Paper>
        </Grid.Col>
      </Grid>

      <Divider my="md" />

      <Accordion variant="separated" defaultValue={null}>
        <Accordion.Item value="overview">
          <Accordion.Control>
            <Group>
              <Title order={4}>Grammar Types Overview</Title>
              <Badge variant="light" color="gray">{grammarTypes.length} types</Badge>
            </Group>
          </Accordion.Control>
          <Accordion.Panel>
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Type</Table.Th>
                  <Table.Th>Description</Table.Th>
                  <Table.Th>Word Count</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {grammarTypes.map((type) => (
                  <Table.Tr key={type.grammar}>
                    <Table.Td>
                      <Badge variant="light" color="blue">{type.grammar || 'Unknown'}</Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">
                        {grammarDescriptions[type.grammar] || 'Grammar type'}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge variant="outline">{type.count}</Badge>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>

      <Accordion variant="separated" defaultValue={null}>
        <Accordion.Item value="examples">
          <Accordion.Control>
            <Group>
              <Title order={4}>Examples by Grammar Type</Title>
              <Badge variant="light" color="gray">{grammarTypes.reduce((sum, t) => sum + t.count, 0)} total words</Badge>
            </Group>
          </Accordion.Control>
          <Accordion.Panel>
            <Accordion variant="separated">
              {grammarTypes.map((type) => (
                <Accordion.Item key={type.grammar} value={type.grammar || 'unknown'}>
                  <Accordion.Control>
                    <Group>
                      <Badge variant="filled" color="blue">{type.grammar || 'Unknown'}</Badge>
                      <Text fw={500}>
                        {grammarDescriptions[type.grammar]?.split(' - ')[0] || 'Grammar Type'}
                      </Text>
                      <Badge variant="light" color="gray">{type.count} words</Badge>
                    </Group>
                  </Accordion.Control>
                  <Accordion.Panel>
                    <Text size="sm" c="dimmed" mb="md">
                      {grammarDescriptions[type.grammar] || 'Words in this grammatical category'}
                    </Text>
                    <Grid>
                      {type.examples.slice(0, 12).map((example, idx) => (
                        <Grid.Col key={idx} span={{ base: 12, sm: 6, md: 4 }}>
                          <Card shadow="xs" p="sm" radius="sm" withBorder>
                            <Text fw={600} c="blue">{example.chuukese_word}</Text>
                            <Text size="sm" c="dimmed">{example.english_translation}</Text>
                          </Card>
                        </Grid.Col>
                      ))}
                    </Grid>
                  </Accordion.Panel>
                </Accordion.Item>
              ))}
            </Accordion>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>

      {grammarTypes.length === 0 && !error && (
        <Card shadow="sm" p="xl" radius="md" withBorder>
          <Stack align="center" gap="md">
            <IconBook size={48} color="gray" />
            <Text c="dimmed">No grammar data available yet.</Text>
          </Stack>
        </Card>
      )}
    </Stack>
  )
}

export default Grammar
