/**
 * Verbs.tsx
 * Purpose: Verb configurator for building semantically valid Chuukese verb phrases
 * 
 * Chuukese Verb Phrase Structure:
 * 1. Subject + Tense Marker (Required) - Pronoun already contains tense
 * 2. Verb Root (Required) - Base verb form, doesn't change
 * 3. Reduplication (Optional) - Repeats part of verb for ongoing/intense/mutual action
 * 4. Directional Suffix (Optional) - Only compatible ones shown based on verb category
 * 5. Prepositional Phrase (Optional) - Only compatible ones shown based on verb category
 * 6. Object with Article (Optional) - Only compatible object types shown based on verb category
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { 
  Stack, 
  Title, 
  Text, 
  Card, 
  Grid,
  SimpleGrid,
  Button,
  Box,
  Group,
  Loader,
  Alert,
  Paper,
  Modal,
  Table,
  Switch,
  Badge,
  Divider,
  Select
} from '@mantine/core'
import { IconAlertCircle, IconInfoCircle, IconSearch } from '@tabler/icons-react'
import axios from 'axios'
import styles from './Verbs.module.css'

// Types for grammar data
interface Pronoun {
  chuukese: string
  english: string
  pastPresent: string
  future: string
  indefinite: string
  simpleNegative: string
  emphaticNegative: string
}

interface PronounTense {
  id: string
  label: string
}

interface VerbInCategory {
  chuukese: string
  english: string
  simpleEnglish: string
}

interface ExampleSentence {
  chuukese: string
  english: string
}

interface VerbCategory {
  id: string
  label: string
  verbs: VerbInCategory[]
  compatibleDirectionals: string[]
  compatiblePrepositions: string[]
  compatibleObjectCategories: string[]
  exampleSentences: ExampleSentence[]
}

interface DirectionalSuffix {
  id: string
  chuukese: string
  english: string
  notes: string
}

interface PrepositionalPhrase {
  id: string
  chuukese: string
  english: string
  notes: string
}

interface Article {
  category: string
  chuukese: string
  meaning: string
  notes: string
  isPlural: boolean
}

interface ObjectItem {
  chuukese: string
  english: string
}

interface ObjectCategory {
  label: string
  objects: ObjectItem[]
}

interface ReduplicationExample {
  base: string
  reduplicated: string
  baseEnglish: string
  reduplicatedEnglish: string
}

interface LookupResult {
  chuukese: string
  english: string
  source: string
  matchType: 'phrase' | 'verb'
}

type TenseKey = 'pastPresent' | 'future' | 'indefinite' | 'simpleNegative' | 'emphaticNegative'

function Verbs() {
  // Data state
  const [pronouns, setPronouns] = useState<Pronoun[]>([])
  const [pronounTenses, setPronounTenses] = useState<PronounTense[]>([])
  const [verbCategories, setVerbCategories] = useState<VerbCategory[]>([])
  const [directionalSuffixes, setDirectionalSuffixes] = useState<DirectionalSuffix[]>([])
  const [prepositionalPhrases, setPrepositionalPhrases] = useState<PrepositionalPhrase[]>([])
  const [articles, setArticles] = useState<Article[]>([])
  const [objectCategories, setObjectCategories] = useState<Record<string, ObjectCategory>>({})
  const [reduplicationExamples, setReduplicationExamples] = useState<ReduplicationExample[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Selection state for required parts
  const [selectedPronoun, setSelectedPronoun] = useState(0)
  const [selectedTense, setSelectedTense] = useState<TenseKey>('pastPresent')
  const [selectedCategoryIdx, setSelectedCategoryIdx] = useState(0)
  const [selectedVerbIdx, setSelectedVerbIdx] = useState(0)

  // Optional parts - can be enabled/disabled
  const [useReduplication, setUseReduplication] = useState(false)
  const [useDirectional, setUseDirectional] = useState(false)
  const [selectedDirectionalId, setSelectedDirectionalId] = useState<string | null>(null)
  const [usePrepositional, setUsePrepositional] = useState(false)
  const [selectedPrepositionalId, setSelectedPrepositionalId] = useState<string | null>(null)
  const [useObject, setUseObject] = useState(false)
  const [selectedObjectCategoryId, setSelectedObjectCategoryId] = useState<string | null>(null)
  const [selectedObjectIdx, setSelectedObjectIdx] = useState(0)
  const [selectedArticle, setSelectedArticle] = useState(0)

  // Modal state
  const [verbModalOpen, setVerbModalOpen] = useState(false)
  const [reduplicationModalOpen, setReduplicationModalOpen] = useState(false)
  const [examplesModalOpen, setExamplesModalOpen] = useState(false)
  const [lookupModalOpen, setLookupModalOpen] = useState(false)
  const [lookupResults, setLookupResults] = useState<LookupResult[]>([])
  const [lookupLoading, setLookupLoading] = useState(false)
  const [lookupSearchedPhrase, setLookupSearchedPhrase] = useState('')
  const [lookupSearchedVerb, setLookupSearchedVerb] = useState('')

  // Load grammar data
  useEffect(() => {
    const loadData = async () => {
      try {
        const response = await import('../data/grammarData.json')
        setPronouns(response.pronouns || [])
        setPronounTenses(response.pronounTenses || [])
        setVerbCategories(response.verbCategories || [])
        setDirectionalSuffixes(response.directionalSuffixes || [])
        setPrepositionalPhrases(response.prepositionalPhrases || [])
        setArticles(response.articles || [])
        setObjectCategories(response.objectCategories || {})
        setReduplicationExamples(response.reduplicationExamples || [])
        
        setLoading(false)
      } catch (err) {
        console.error('Error loading grammar data:', err)
        setError('Failed to load grammar data')
        setLoading(false)
      }
    }
    loadData()
  }, [])

  // Get current verb category
  const currentCategory = verbCategories[selectedCategoryIdx]
  
  // Get current verb from category
  const currentVerb = currentCategory?.verbs[selectedVerbIdx]

  // Get compatible directionals for current verb category
  const compatibleDirectionals = useMemo(() => {
    if (!currentCategory) return []
    return directionalSuffixes.filter(d => 
      currentCategory.compatibleDirectionals.includes(d.id)
    )
  }, [currentCategory, directionalSuffixes])

  // Get compatible prepositions for current verb category
  const compatiblePrepositions = useMemo(() => {
    if (!currentCategory) return []
    return prepositionalPhrases.filter(p => 
      currentCategory.compatiblePrepositions.includes(p.id)
    )
  }, [currentCategory, prepositionalPhrases])

  // Get compatible object categories for current verb
  const compatibleObjectCats = useMemo(() => {
    if (!currentCategory) return []
    return currentCategory.compatibleObjectCategories
      .map(catId => ({ id: catId, ...objectCategories[catId] }))
      .filter(cat => cat.label)
  }, [currentCategory, objectCategories])

  // Reset optional selections when category changes
  useEffect(() => {
    setSelectedVerbIdx(0)
    setUseDirectional(false)
    setSelectedDirectionalId(null)
    setUsePrepositional(false)
    setSelectedPrepositionalId(null)
    setUseObject(false)
    setSelectedObjectCategoryId(null)
    setSelectedObjectIdx(0)
  }, [selectedCategoryIdx])

  // Set initial directional when toggled on
  useEffect(() => {
    if (useDirectional && !selectedDirectionalId && compatibleDirectionals.length > 0) {
      setSelectedDirectionalId(compatibleDirectionals[0].id)
    }
  }, [useDirectional, selectedDirectionalId, compatibleDirectionals])

  // Set initial prepositional when toggled on
  useEffect(() => {
    if (usePrepositional && !selectedPrepositionalId && compatiblePrepositions.length > 0) {
      setSelectedPrepositionalId(compatiblePrepositions[0].id)
    }
  }, [usePrepositional, selectedPrepositionalId, compatiblePrepositions])

  // Set initial object category when toggled on
  useEffect(() => {
    if (useObject && !selectedObjectCategoryId && compatibleObjectCats.length > 0) {
      setSelectedObjectCategoryId(compatibleObjectCats[0].id)
      setSelectedObjectIdx(0)
    }
  }, [useObject, selectedObjectCategoryId, compatibleObjectCats])

  // Get current selections
  const currentPronoun = pronouns[selectedPronoun]
  const currentDirectional = directionalSuffixes.find(d => d.id === selectedDirectionalId)
  const currentPreposition = prepositionalPhrases.find(p => p.id === selectedPrepositionalId)
  const currentObjectCat = selectedObjectCategoryId ? objectCategories[selectedObjectCategoryId] : null
  const currentObject = currentObjectCat?.objects[selectedObjectIdx]

  // Get English verb phrase based on pronoun and tense
  const getEnglishVerbPhrase = useCallback((pronounEnglish: string, tense: TenseKey): string => {
    if (!currentVerb) return ''
    
    const isThirdPersonSingular = pronounEnglish === 'he/she/it'
    const verb = currentVerb.simpleEnglish
    
    const getThirdPersonVerb = (v: string): string => {
      if (v === 'have') return 'has'
      if (v === 'be' || v === 'be happy' || v === 'be angry') return 'is'
      if (v === 'do') return 'does'
      if (v === 'go') return 'goes'
      if (v === 'can') return 'can'
      if (v.startsWith('be ')) return 'is ' + v.substring(3)
      if (v.endsWith('y') && !['a', 'e', 'i', 'o', 'u'].includes(v.charAt(v.length - 2))) {
        return v.slice(0, -1) + 'ies'
      }
      if (v.endsWith('s') || v.endsWith('sh') || v.endsWith('ch') || v.endsWith('x') || v.endsWith('z')) {
        return v + 'es'
      }
      return v + 's'
    }

    const reduplicationSuffix = useReduplication ? ' (repeatedly)' : ''
    
    switch (tense) {
      case 'pastPresent':
        return (isThirdPersonSingular ? getThirdPersonVerb(verb) : verb) + reduplicationSuffix
      case 'future':
        return `will ${verb}` + reduplicationSuffix
      case 'indefinite':
        return verb + reduplicationSuffix
      case 'simpleNegative':
        if (verb === 'have') {
          return (isThirdPersonSingular ? "doesn't have" : "don't have") + reduplicationSuffix
        }
        return (isThirdPersonSingular ? `doesn't ${verb}` : `don't ${verb}`) + reduplicationSuffix
      case 'emphaticNegative':
        if (verb === 'have') {
          return (isThirdPersonSingular ? "doesn't have at all" : "don't have at all") + reduplicationSuffix
        }
        return (isThirdPersonSingular ? `doesn't ${verb} at all` : `don't ${verb} at all`) + reduplicationSuffix
      default:
        return verb + reduplicationSuffix
    }
  }, [currentVerb, useReduplication])

  // Build the complete Chuukese phrase
  const buildChuukesePhrase = useCallback((): string => {
    const parts: string[] = []
    
    // 1. Subject + Tense (required)
    if (currentPronoun) {
      parts.push(currentPronoun[selectedTense])
    }
    
    // 2. Verb Root (required) with directional attached
    if (currentVerb) {
      let verbWord = currentVerb.chuukese
      
      // 4. Directional Suffix attaches to verb
      if (useDirectional && currentDirectional) {
        verbWord += currentDirectional.chuukese.replace('-', '')
      }
      
      parts.push(verbWord)
    }
    
    // 5. Prepositional Phrase (optional)
    if (usePrepositional && currentPreposition) {
      parts.push(currentPreposition.chuukese)
    }
    
    // 6. Object with Article (optional)
    if (useObject && currentObject && articles[selectedArticle]) {
      parts.push(articles[selectedArticle].chuukese)
      parts.push(currentObject.chuukese)
    }
    
    return parts.join(' ')
  }, [currentPronoun, selectedTense, currentVerb, useDirectional, currentDirectional,
      usePrepositional, currentPreposition, useObject, currentObject, articles, selectedArticle])

  // Build the English translation
  const buildEnglishPhrase = useCallback((): string => {
    const parts: string[] = []
    
    // Subject + Verb
    if (currentPronoun) {
      parts.push(currentPronoun.english)
      parts.push(getEnglishVerbPhrase(currentPronoun.english, selectedTense))
    }
    
    // Directional
    if (useDirectional && currentDirectional) {
      parts.push(currentDirectional.english.split('/')[0].trim())
    }
    
    // Prepositional phrase
    if (usePrepositional && currentPreposition) {
      parts.push(currentPreposition.english.split('/')[0].trim())
    }
    
    // Object with article
    if (useObject && currentObject && articles[selectedArticle]) {
      parts.push(articles[selectedArticle].meaning)
      parts.push(currentObject.english)
    }
    
    return parts.join(' ')
  }, [currentPronoun, selectedTense, getEnglishVerbPhrase, useDirectional, currentDirectional,
      usePrepositional, currentPreposition, useObject, currentObject, articles, selectedArticle])

  // Handle verb category/verb selection
  const handleVerbSelect = useCallback((catIdx: number, verbIdx: number) => {
    setSelectedCategoryIdx(catIdx)
    setSelectedVerbIdx(verbIdx)
    setVerbModalOpen(false)
  }, [])

  // Handle lookup examples from database
  const handleLookupExamples = useCallback(async () => {
    if (!currentVerb) return
    
    const phrase = buildChuukesePhrase()
    const verb = currentVerb.chuukese
    
    setLookupSearchedPhrase(phrase)
    setLookupSearchedVerb(verb)
    setLookupLoading(true)
    setLookupModalOpen(true)
    setLookupResults([])
    
    try {
      const response = await axios.post('/api/verbs/lookup-examples', {
        phrase,
        verb
      })
      setLookupResults(response.data.results || [])
    } catch (err) {
      console.error('Lookup failed:', err)
      setLookupResults([])
    } finally {
      setLookupLoading(false)
    }
  }, [currentVerb, buildChuukesePhrase])

  if (loading) {
    return (
      <Stack align="center" justify="center" h={300}>
        <Loader size="lg" />
        <Text>Loading verb data...</Text>
      </Stack>
    )
  }

  return (
    <Stack gap="lg" className={styles.pageContainer}>
      <Title order={2}>Chuukese Verb Phrase Builder</Title>
      
      <Text c="dimmed">
        Build semantically correct Chuukese verb phrases. Select a verb category to see 
        only compatible directionals, prepositions, and objects.
      </Text>

      {error && (
        <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
          {error}
        </Alert>
      )}

      {/* Phrase Structure Reference */}
      <Card shadow="xs" p="md" radius="md" withBorder>
        <Text size="sm" fw={600} mb="sm">Verb Phrase Structure:</Text>
        <Group gap="xs" wrap="wrap">
          <Badge color="violet" variant="filled">1. Subject+Tense</Badge>
          <Text c="dimmed">+</Text>
          <Badge color="teal" variant="filled">2. Verb Root</Badge>
          <Text c="dimmed">+</Text>
          <Badge color="orange" variant="light">3. Reduplication?</Badge>
          <Text c="dimmed">+</Text>
          <Badge color="yellow" variant="light">4. Directional?</Badge>
          <Text c="dimmed">+</Text>
          <Badge color="pink" variant="light">5. Prepositional?</Badge>
          <Text c="dimmed">+</Text>
          <Badge color="blue" variant="light">6. Object?</Badge>
        </Group>
      </Card>

      {/* Main Verb Display */}
      <Card shadow="sm" p="lg" radius="md" withBorder>
        <Box className={styles.verbDisplay}>
          {/* 1. Subject + Tense */}
          <Box className={`${styles.verbPart} ${styles.verbPartSubject}`}>
            <Text className={styles.verbPartText}>
              {currentPronoun?.[selectedTense] || '—'}
            </Text>
            <Text className={styles.verbPartLabel}>Subject+Tense</Text>
          </Box>

          {/* 2. Verb Root (+ directional if attached) */}
          <Box 
            className={`${styles.verbPart} ${styles.verbPartVerb}`}
            onClick={() => setVerbModalOpen(true)}
            style={{ cursor: 'pointer' }}
          >
            <Text className={styles.verbPartText}>
              {currentVerb?.chuukese || '—'}
              {useDirectional && currentDirectional && (
                <Text component="span" c="yellow.7" fw={700}>
                  {currentDirectional.chuukese.replace('-', '')}
                </Text>
              )}
            </Text>
            <Text className={styles.verbPartLabel}>
              Verb{useDirectional ? ' + Dir.' : ''}
            </Text>
          </Box>

          {/* 5. Prepositional Phrase (optional) */}
          {usePrepositional && currentPreposition && (
            <Box className={`${styles.verbPart} ${styles.verbPartPrepositional}`}>
              <Text className={styles.verbPartText}>
                {currentPreposition.chuukese}
              </Text>
              <Text className={styles.verbPartLabel}>Prep.</Text>
            </Box>
          )}

          {/* 6. Object with Article (optional) */}
          {useObject && currentObject && (
            <Box className={`${styles.verbPart} ${styles.verbPartObject}`}>
              <Text className={styles.verbPartText}>
                {articles[selectedArticle]?.chuukese} {currentObject.chuukese}
              </Text>
              <Text className={styles.verbPartLabel}>Article + Object</Text>
            </Box>
          )}
        </Box>

        {/* Complete Translation Display */}
        <Divider my="md" />
        <Box className={styles.translationDisplay}>
          <Text className={styles.translationChuukese}>
            {buildChuukesePhrase()}
          </Text>
          <Text className={styles.translationEnglish}>
            {buildEnglishPhrase()}
          </Text>
        </Box>

        {/* Example sentences link */}
        <Group mt="sm" gap="sm">
          {currentCategory?.exampleSentences && currentCategory.exampleSentences.length > 0 && (
            <Button 
              variant="subtle" 
              size="xs"
              onClick={() => setExamplesModalOpen(true)}
              leftSection={<IconInfoCircle size={14} />}
            >
              See {currentCategory.exampleSentences.length} example sentences for "{currentCategory.label}"
            </Button>
          )}
          <Button 
            variant="light" 
            size="xs"
            onClick={handleLookupExamples}
            leftSection={<IconSearch size={14} />}
            loading={lookupLoading}
          >
            Lookup Examples
          </Button>
        </Group>
      </Card>

      {/* Selector Cards */}
      <Grid gutter="md">
        {/* Row 1: Required Parts */}
        <Grid.Col span={12}>
          <Text size="sm" fw={700} c="dimmed" mb="xs">REQUIRED PARTS:</Text>
        </Grid.Col>
        
        {/* Pronouns Selector */}
        <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
          <Paper shadow="xs" p="md" radius="md" withBorder h="100%">
            <Text size="sm" fw={600} c="violet" mb="sm">1. Subject (Pronoun):</Text>
            <SimpleGrid cols={2} spacing={6}>
              {pronouns.map((pronoun, idx) => {
                const isSelected = selectedPronoun === idx
                return (
                  <Button
                    key={`pronoun-${idx}`}
                    variant="subtle"
                    color="violet"
                    size="xs"
                    onClick={() => setSelectedPronoun(idx)}
                    styles={{
                      root: {
                        backgroundColor: isSelected ? 'rgba(121, 80, 242, 0.15)' : 'rgba(0, 0, 0, 0.04)',
                        color: isSelected ? '#7950f2' : 'inherit',
                        border: 'none',
                      }
                    }}
                  >
                    {pronoun.english}
                  </Button>
                )
              })}
            </SimpleGrid>
          </Paper>
        </Grid.Col>

        {/* Tense Selector */}
        <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
          <Paper shadow="xs" p="md" radius="md" withBorder h="100%">
            <Text size="sm" fw={600} c="grape" mb="sm">Tense:</Text>
            <Stack gap={4}>
              {pronounTenses.map((tense) => {
                const isSelected = selectedTense === tense.id
                return (
                  <Button
                    key={`tense-${tense.id}`}
                    variant="subtle"
                    color="grape"
                    size="xs"
                    onClick={() => setSelectedTense(tense.id as TenseKey)}
                    styles={{
                      root: {
                        backgroundColor: isSelected ? 'rgba(190, 75, 219, 0.15)' : 'rgba(0, 0, 0, 0.04)',
                        color: isSelected ? '#be4bdb' : 'inherit',
                        border: 'none',
                        justifyContent: 'flex-start',
                      }
                    }}
                  >
                    {tense.label}
                  </Button>
                )
              })}
            </Stack>
          </Paper>
        </Grid.Col>

        {/* Verb Category + Verb Selector */}
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Paper shadow="xs" p="md" radius="md" withBorder h="100%">
            <Group justify="space-between" mb="sm">
              <Text size="sm" fw={600} c="teal">2. Verb Category & Root:</Text>
              <Button variant="subtle" size="xs" color="teal" onClick={() => setVerbModalOpen(true)}>
                All verbs
              </Button>
            </Group>
            
            {/* Category selector */}
            <Select
              size="xs"
              mb="sm"
              placeholder="Select verb category"
              value={selectedCategoryIdx.toString()}
              onChange={(val) => val && setSelectedCategoryIdx(parseInt(val))}
              data={verbCategories.map((cat, idx) => ({
                value: idx.toString(),
                label: cat.label
              }))}
            />
            
            {/* Verbs in selected category */}
            {currentCategory && (
              <SimpleGrid cols={3} spacing={4}>
                {currentCategory.verbs.map((verb, idx) => {
                  const isSelected = selectedVerbIdx === idx
                  return (
                    <Button
                      key={`verb-${idx}`}
                      variant="subtle"
                      color="teal"
                      size="xs"
                      onClick={() => setSelectedVerbIdx(idx)}
                      styles={{
                        root: {
                          backgroundColor: isSelected ? 'rgba(18, 184, 134, 0.15)' : 'rgba(0, 0, 0, 0.04)',
                          color: isSelected ? '#12b886' : 'inherit',
                          border: 'none',
                        }
                      }}
                    >
                      {verb.chuukese}
                    </Button>
                  )
                })}
              </SimpleGrid>
            )}
          </Paper>
        </Grid.Col>

        {/* Row 2: Optional Parts */}
        <Grid.Col span={12}>
          <Divider my="xs" />
          <Text size="sm" fw={700} c="dimmed" mb="xs">
            OPTIONAL PARTS (showing only compatible options for "{currentCategory?.label || 'selected verb'}"):
          </Text>
        </Grid.Col>

        {/* 3. Reduplication Toggle */}
        <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
          <Paper shadow="xs" p="md" radius="md" withBorder h="100%">
            <Group justify="space-between" mb="sm">
              <Text size="sm" fw={600} c="orange">3. Reduplication:</Text>
              <Switch 
                checked={useReduplication} 
                onChange={(e) => setUseReduplication(e.currentTarget.checked)}
                color="orange"
                size="sm"
              />
            </Group>
            {useReduplication ? (
              <Stack gap="xs">
                <Text size="xs" c="dimmed">
                  Shows ongoing, intense, or mutual action.
                </Text>
                <Button 
                  variant="subtle" 
                  size="xs" 
                  color="orange"
                  onClick={() => setReduplicationModalOpen(true)}
                >
                  See examples
                </Button>
              </Stack>
            ) : (
              <Text size="xs" c="dimmed">Toggle to add repeated action meaning</Text>
            )}
          </Paper>
        </Grid.Col>

        {/* 4. Directional Suffix */}
        <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
          <Paper shadow="xs" p="md" radius="md" withBorder h="100%">
            <Group justify="space-between" mb="sm">
              <Text size="sm" fw={600} c="yellow.7">4. Directional:</Text>
              <Switch 
                checked={useDirectional} 
                onChange={(e) => setUseDirectional(e.currentTarget.checked)}
                color="yellow"
                size="sm"
                disabled={compatibleDirectionals.length === 0}
              />
            </Group>
            {compatibleDirectionals.length === 0 ? (
              <Text size="xs" c="dimmed" fs="italic">
                No directionals for this verb type
              </Text>
            ) : useDirectional ? (
              <Stack gap={4}>
                {compatibleDirectionals.map((suffix) => {
                  const isSelected = selectedDirectionalId === suffix.id
                  return (
                    <Button
                      key={`dir-${suffix.id}`}
                      variant="subtle"
                      color="yellow"
                      size="xs"
                      onClick={() => setSelectedDirectionalId(suffix.id)}
                      styles={{
                        root: {
                          backgroundColor: isSelected ? 'rgba(255, 212, 59, 0.25)' : 'rgba(0, 0, 0, 0.04)',
                          color: isSelected ? '#e67700' : 'inherit',
                          border: 'none',
                          justifyContent: 'flex-start',
                        }
                      }}
                    >
                      <Group gap="xs">
                        <Text fw={600}>{suffix.chuukese}</Text>
                        <Text size="xs" c="dimmed">({suffix.english})</Text>
                      </Group>
                    </Button>
                  )
                })}
              </Stack>
            ) : (
              <Text size="xs" c="dimmed">
                {compatibleDirectionals.length} options available
              </Text>
            )}
          </Paper>
        </Grid.Col>

        {/* 5. Prepositional Phrase */}
        <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
          <Paper shadow="xs" p="md" radius="md" withBorder h="100%">
            <Group justify="space-between" mb="sm">
              <Text size="sm" fw={600} c="pink">5. Prepositional:</Text>
              <Switch 
                checked={usePrepositional} 
                onChange={(e) => setUsePrepositional(e.currentTarget.checked)}
                color="pink"
                size="sm"
                disabled={compatiblePrepositions.length === 0}
              />
            </Group>
            {compatiblePrepositions.length === 0 ? (
              <Text size="xs" c="dimmed" fs="italic">
                No prepositions for this verb type
              </Text>
            ) : usePrepositional ? (
              <Stack gap={4}>
                {compatiblePrepositions.map((prep) => {
                  const isSelected = selectedPrepositionalId === prep.id
                  return (
                    <Button
                      key={`prep-${prep.id}`}
                      variant="subtle"
                      color="pink"
                      size="xs"
                      onClick={() => setSelectedPrepositionalId(prep.id)}
                      styles={{
                        root: {
                          backgroundColor: isSelected ? 'rgba(230, 73, 128, 0.15)' : 'rgba(0, 0, 0, 0.04)',
                          color: isSelected ? '#e64980' : 'inherit',
                          border: 'none',
                          justifyContent: 'flex-start',
                        }
                      }}
                    >
                      <Group gap="xs">
                        <Text fw={600}>{prep.chuukese}</Text>
                        <Text size="xs" c="dimmed">({prep.english})</Text>
                      </Group>
                    </Button>
                  )
                })}
              </Stack>
            ) : (
              <Text size="xs" c="dimmed">
                {compatiblePrepositions.length} options available
              </Text>
            )}
          </Paper>
        </Grid.Col>

        {/* 6. Object with Article */}
        <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
          <Paper shadow="xs" p="md" radius="md" withBorder h="100%">
            <Group justify="space-between" mb="sm">
              <Text size="sm" fw={600} c="blue">6. Object:</Text>
              <Switch 
                checked={useObject} 
                onChange={(e) => setUseObject(e.currentTarget.checked)}
                color="blue"
                size="sm"
                disabled={compatibleObjectCats.length === 0}
              />
            </Group>
            {compatibleObjectCats.length === 0 ? (
              <Text size="xs" c="dimmed" fs="italic">
                No objects for this verb type
              </Text>
            ) : useObject ? (
              <Stack gap="xs">
                {/* Object category selector */}
                <Select
                  size="xs"
                  placeholder="Object type"
                  value={selectedObjectCategoryId}
                  onChange={(val) => {
                    setSelectedObjectCategoryId(val)
                    setSelectedObjectIdx(0)
                  }}
                  data={compatibleObjectCats.map(cat => ({
                    value: cat.id,
                    label: cat.label
                  }))}
                />
                
                {/* Article selector */}
                <Text size="xs" fw={500}>Article:</Text>
                <SimpleGrid cols={2} spacing={4}>
                  {articles.slice(0, 4).map((art, idx) => {
                    const isSelected = selectedArticle === idx
                    return (
                      <Button
                        key={`art-${idx}`}
                        variant="subtle"
                        color="blue"
                        size="xs"
                        onClick={() => setSelectedArticle(idx)}
                        styles={{
                          root: {
                            backgroundColor: isSelected ? 'rgba(34, 139, 230, 0.15)' : 'rgba(0, 0, 0, 0.04)',
                            color: isSelected ? '#228be6' : 'inherit',
                            border: 'none',
                          }
                        }}
                      >
                        {art.chuukese}
                      </Button>
                    )
                  })}
                </SimpleGrid>
                
                {/* Object selector */}
                {currentObjectCat && (
                  <>
                    <Text size="xs" fw={500}>Object:</Text>
                    <SimpleGrid cols={2} spacing={4}>
                      {currentObjectCat.objects.map((obj, idx) => {
                        const isSelected = selectedObjectIdx === idx
                        return (
                          <Button
                            key={`obj-${idx}`}
                            variant="subtle"
                            color="blue"
                            size="xs"
                            onClick={() => setSelectedObjectIdx(idx)}
                            styles={{
                              root: {
                                backgroundColor: isSelected ? 'rgba(34, 139, 230, 0.15)' : 'rgba(0, 0, 0, 0.04)',
                                color: isSelected ? '#228be6' : 'inherit',
                                border: 'none',
                              }
                            }}
                          >
                            {obj.chuukese}
                          </Button>
                        )
                      })}
                    </SimpleGrid>
                  </>
                )}
              </Stack>
            ) : (
              <Text size="xs" c="dimmed">
                {compatibleObjectCats.length} object types available
              </Text>
            )}
          </Paper>
        </Grid.Col>
      </Grid>

      {/* Verb Modal - All categories */}
      <Modal 
        opened={verbModalOpen} 
        onClose={() => setVerbModalOpen(false)} 
        title="Chuukese Verbs by Category"
        size="xl"
        centered
      >
        <Stack gap="md">
          {verbCategories.map((cat, catIdx) => (
            <Card key={cat.id} shadow="xs" p="sm" withBorder>
              <Text size="sm" fw={600} c="teal" mb="xs">{cat.label}</Text>
              <Table striped highlightOnHover withTableBorder>
                <Table.Tbody>
                  {cat.verbs.map((verb, verbIdx) => {
                    const isSelected = selectedCategoryIdx === catIdx && selectedVerbIdx === verbIdx
                    return (
                      <Table.Tr 
                        key={`${cat.id}-${verbIdx}`}
                        className={isSelected ? styles.tableRowSelected : styles.tableRow}
                        onClick={() => handleVerbSelect(catIdx, verbIdx)}
                      >
                        <Table.Td 
                          className={isSelected ? styles.tableCellSelected : styles.tableCell}
                          w={100}
                        >
                          {verb.chuukese}
                        </Table.Td>
                        <Table.Td>{verb.english}</Table.Td>
                      </Table.Tr>
                    )
                  })}
                </Table.Tbody>
              </Table>
            </Card>
          ))}
        </Stack>
      </Modal>

      {/* Reduplication Examples Modal */}
      <Modal 
        opened={reduplicationModalOpen} 
        onClose={() => setReduplicationModalOpen(false)} 
        title="Reduplication Examples"
        size="lg"
        centered
      >
        <Text size="sm" c="dimmed" mb="md">
          Reduplication repeats part of the verb root to indicate ongoing, intense, or reciprocal action.
        </Text>
        <Table striped highlightOnHover withTableBorder withColumnBorders>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Base Verb</Table.Th>
              <Table.Th>Reduplicated</Table.Th>
              <Table.Th>Base Meaning</Table.Th>
              <Table.Th>Reduplicated Meaning</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {reduplicationExamples.map((ex, idx) => (
              <Table.Tr key={`redup-${idx}`}>
                <Table.Td fw={600}>{ex.base}</Table.Td>
                <Table.Td fw={600} c="orange">{ex.reduplicated}</Table.Td>
                <Table.Td>{ex.baseEnglish}</Table.Td>
                <Table.Td>{ex.reduplicatedEnglish}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Modal>

      {/* Example Sentences Modal */}
      <Modal 
        opened={examplesModalOpen} 
        onClose={() => setExamplesModalOpen(false)} 
        title={`Example Sentences: ${currentCategory?.label || ''}`}
        size="lg"
        centered
      >
        <Text size="sm" c="dimmed" mb="md">
          These are correct example sentences for {currentCategory?.label?.toLowerCase() || 'this verb type'}.
        </Text>
        <Table striped highlightOnHover withTableBorder withColumnBorders>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Chuukese</Table.Th>
              <Table.Th>English</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {currentCategory?.exampleSentences.map((ex, idx) => (
              <Table.Tr key={`ex-${idx}`}>
                <Table.Td fw={600} c="teal">{ex.chuukese}</Table.Td>
                <Table.Td>{ex.english}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Modal>

      {/* Lookup Examples Modal */}
      <Modal 
        opened={lookupModalOpen} 
        onClose={() => setLookupModalOpen(false)} 
        title="Lookup Examples"
        size="xl"
        centered
      >
        <Stack gap="md">
          <Box>
            <Text size="sm" fw={600}>Searched phrase:</Text>
            <Text size="lg" c="teal" fw={700}>{lookupSearchedPhrase}</Text>
          </Box>
          
          {lookupLoading ? (
            <Stack align="center" py="xl">
              <Loader size="md" />
              <Text c="dimmed">Searching for examples...</Text>
            </Stack>
          ) : lookupResults.length === 0 ? (
            <Alert icon={<IconInfoCircle size={16} />} color="blue">
              No examples found for "{lookupSearchedPhrase}" or "{lookupSearchedVerb}". 
              Try a different verb or phrase combination.
            </Alert>
          ) : (
            <>
              <Text size="sm" c="dimmed">
                Found {lookupResults.length} example{lookupResults.length !== 1 ? 's' : ''} 
                {lookupResults.some(r => r.matchType === 'phrase') && lookupResults.some(r => r.matchType === 'verb') 
                  ? ` (matching phrase and verb "${lookupSearchedVerb}")`
                  : lookupResults.every(r => r.matchType === 'verb')
                    ? ` (matching verb "${lookupSearchedVerb}")`
                    : ' (matching phrase)'}
              </Text>
              <Stack gap="sm">
                {lookupResults.map((result, idx) => (
                  <Card key={idx} shadow="xs" p="sm" radius="md" withBorder>
                    <Group justify="space-between" mb="xs">
                      <Badge 
                        size="xs" 
                        color={result.matchType === 'phrase' ? 'green' : 'blue'}
                      >
                        {result.matchType === 'phrase' ? 'Phrase match' : 'Verb match'}
                      </Badge>
                      <Text size="xs" c="dimmed">{result.source}</Text>
                    </Group>
                    <Text size="sm" fw={600} c="teal" mb="xs">
                      {result.chuukese}
                    </Text>
                    <Text size="sm" c="dimmed">
                      {result.english}
                    </Text>
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

export default Verbs
