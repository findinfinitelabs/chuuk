import { useState, useEffect } from 'react'
import { Card, Title, Text, Button, Group, Grid, Modal, Stack, Badge, List, ThemeIcon, Divider } from '@mantine/core'
import { IconBook, IconChevronRight, IconLanguage, IconArrowRight } from '@tabler/icons-react'
import axios from 'axios'

interface GrammarSection {
  title: string
  description: string
  category: string
  details: any
}

function GrammarLearning() {
  const [languageGuide, setLanguageGuide] = useState<any>(null)
  const [selectedSection, setSelectedSection] = useState<GrammarSection | null>(null)
  const [modalOpened, setModalOpened] = useState(false)

  useEffect(() => {
    loadLanguageGuide()
  }, [])

  const loadLanguageGuide = async () => {
    try {
      const response = await axios.get('/data/grammar/language_guide.json')
      setLanguageGuide(response.data.chuukeseSentenceGuide)
    } catch (error) {
      console.error('Failed to load language guide:', error)
    }
  }

  const openSectionModal = (section: GrammarSection) => {
    setSelectedSection(section)
    setModalOpened(true)
  }

  if (!languageGuide) return null

  const sections = languageGuide.sections

  const grammarCards: GrammarSection[] = [
    {
      title: 'Vowel System',
      description: 'Learn the Chuukese vowel sounds and pronunciation with modern diacritics',
      category: 'Pronunciation',
      details: sections.vowelSystem
    },
    {
      title: 'Sentence Structure',
      description: 'Understand Verb-Object-Subject (VOS) order and variations',
      category: 'Syntax',
      details: sections.sentenceStructure
    },
    {
      title: 'Verb Construction',
      description: 'Master tense markers, pronoun suffixes, and directionals',
      category: 'Verbs',
      details: sections.verbConstruction
    },
    {
      title: 'Pronouns',
      description: 'Stand-alone and possessive pronouns for all persons',
      category: 'Pronouns',
      details: sections.pronouns
    },
    {
      title: 'Possession',
      description: 'Learn suffix possession vs stand-alone possessives',
      category: 'Grammar',
      details: sections.possession
    },
    {
      title: 'Reduplication',
      description: 'Repetition patterns for intensity, emphasis, and plurality',
      category: 'Morphology',
      details: sections.reduplication
    },
    {
      title: 'Counting Classifiers',
      description: 'Classifiers for persons, long objects, flat objects, and round objects',
      category: 'Numbers',
      details: sections.countingClassifiers
    },
    {
      title: 'Key Language Rules',
      description: 'Essential rules for speaking and writing Chuukese',
      category: 'Overview',
      details: languageGuide
    }
  ]

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      'Pronunciation': 'blue',
      'Syntax': 'green',
      'Verbs': 'orange',
      'Pronouns': 'grape',
      'Grammar': 'cyan',
      'Morphology': 'pink',
      'Numbers': 'teal',
      'Overview': 'violet'
    }
    return colors[category] || 'gray'
  }

  const renderSectionDetails = (section: GrammarSection) => {
    const { details } = section
    console.log('Rendering section:', section.title, 'Details:', details)

    switch (section.title) {
      case 'Vowel System':
        return (
          <Stack gap="md">
            <div>
              <Text fw={600} mb="xs">Vowel Sounds:</Text>
              <Grid gutter="xs">
                {details.vowels && Object.entries(details.vowels).map(([vowel, sound]: [string, any]) => (
                  <Grid.Col key={vowel} span={6}>
                    <Group gap="xs">
                      <Text fw={700} c="blue" size="xl">{vowel}</Text>
                      <Text c="dimmed" size="sm">→ {sound}</Text>
                    </Group>
                  </Grid.Col>
                ))}
              </Grid>
            </div>
            <Divider />
            <div>
              <Text fw={600} mb="xs">Important Notes:</Text>
              <List spacing="xs" size="sm">
                {details.lookupNotes && details.lookupNotes.map((note: string, i: number) => (
                  <List.Item key={i}>{note}</List.Item>
                ))}
              </List>
            </div>
          </Stack>
        )

      case 'Sentence Structure':
        return (
          <Stack gap="md">
            <div>
              <Text fw={600}>Default Word Order:</Text>
              <Text size="lg" c="blue" fw={700}>{details.defaultOrder}</Text>
            </div>
            <div>
              <Text fw={600} mb="xs">Alternative Orders:</Text>
              <List spacing="xs">
                {details.alternates && details.alternates.map((order: string, i: number) => (
                  <List.Item key={i}>{order}</List.Item>
                ))}
              </List>
            </div>
            <Text size="sm" c="dimmed">{details.notes}</Text>
          </Stack>
        )

      case 'Verb Construction':
        return (
          <Stack gap="md">
            <div>
              <Text fw={600} mb="xs">Formula:</Text>
              <Badge size="lg" variant="light" color="blue">{details.formula}</Badge>
            </div>
            
            <Divider />
            
            <div>
              <Text fw={600} mb="xs">Tense Markers:</Text>
              <Grid gutter="xs">
                {details.tenseMarkers && Object.entries(details.tenseMarkers).map(([marker, meaning]: [string, any]) => (
                  <Grid.Col key={marker} span={6}>
                    <Group gap="xs">
                      <Text fw={700} c="orange">{marker}</Text>
                      <IconArrowRight size={14} />
                      <Text size="sm">{meaning}</Text>
                    </Group>
                  </Grid.Col>
                ))}
              </Grid>
            </div>

            <Divider />

            <div>
              <Text fw={600} mb="xs">Pronoun Suffixes:</Text>
              <Grid gutter="xs">
                {details.pronounSuffixes && Object.entries(details.pronounSuffixes).map(([suffix, meaning]: [string, any]) => (
                  <Grid.Col key={suffix} span={6}>
                    <Group gap="xs">
                      <Text fw={700} c="grape">{suffix}</Text>
                      <IconArrowRight size={14} />
                      <Text size="sm">{meaning}</Text>
                    </Group>
                  </Grid.Col>
                ))}
              </Grid>
            </div>

            <Divider />

            <div>
              <Text fw={600} mb="xs">Directionals:</Text>
              <Grid gutter="xs">
                {details.directionals && Object.entries(details.directionals)
                  .filter(([key]) => key !== 'notes')
                  .map(([dir, meaning]: [string, any]) => (
                    <Grid.Col key={dir} span={6}>
                      <Group gap="xs">
                        <Text fw={700} c="cyan">{dir}</Text>
                        <IconArrowRight size={14} />
                        <Text size="sm">{meaning}</Text>
                      </Group>
                    </Grid.Col>
                  ))}
              </Grid>
              <Text size="sm" c="dimmed" mt="xs">{details.directionals.notes}</Text>
            </div>

            <List spacing="xs" size="sm" mt="md">
              {details.notes && details.notes.map((note: string, i: number) => (
                <List.Item key={i}>{note}</List.Item>
              ))}
            </List>
          </Stack>
        )

      case 'Pronouns':
        return (
          <Stack gap="md">
            <div>
              <Text fw={600} mb="xs">Stand-Alone Pronouns:</Text>
              <Grid gutter="xs">
                {details.standAlone?.list && Object.entries(details.standAlone.list).map(([eng, chk]: [string, any]) => (
                  <Grid.Col key={eng} span={6}>
                    <Group gap="xs">
                      <Text size="sm">{eng.replace(/_/g, ' ')}</Text>
                      <IconArrowRight size={14} />
                      <Text fw={700} c="grape">{chk}</Text>
                    </Group>
                  </Grid.Col>
                ))}
              </Grid>
              <List spacing="xs" size="sm" mt="sm">
                {details.standAlone?.notes && details.standAlone.notes.map((note: string, i: number) => (
                  <List.Item key={i}>{note}</List.Item>
                ))}
              </List>
            </div>

            <Divider />

            <div>
              <Text fw={600} mb="xs">Possessive Pronouns (Inanimate):</Text>
              <Grid gutter="xs">
                {details.standAlonePossessives?.inanimate && Object.entries(details.standAlonePossessives.inanimate).map(([eng, chk]: [string, any]) => (
                  <Grid.Col key={eng} span={6}>
                    <Group gap="xs">
                      <Text size="sm">{eng.replace(/_/g, ' ')}</Text>
                      <IconArrowRight size={14} />
                      <Text fw={700} c="blue">{chk}</Text>
                    </Group>
                  </Grid.Col>
                ))}
              </Grid>
            </div>

            <Divider />

            <div>
              <Text fw={600} mb="xs">Possessive Pronouns (Animate):</Text>
              <Grid gutter="xs">
                {details.standAlonePossessives?.animate && Object.entries(details.standAlonePossessives.animate).map(([eng, chk]: [string, any]) => (
                  <Grid.Col key={eng} span={6}>
                    <Group gap="xs">
                      <Text size="sm">{eng.replace(/_/g, ' ')}</Text>
                      <IconArrowRight size={14} />
                      <Text fw={700} c="green">{chk}</Text>
                    </Group>
                  </Grid.Col>
                ))}
              </Grid>
              <Text size="sm" c="dimmed" mt="xs">{details.standAlonePossessives.rule}</Text>
            </div>

            {details.standAlonePossessives.examples && (
              <>
                <Divider />
                <div>
                  <Text fw={600} mb="xs">Examples:</Text>
                  {details.standAlonePossessives.examples.map((ex: any, i: number) => (
                    <Group key={i} gap="xs" mb="xs">
                      <Text fw={700}>{ex.chuukese}</Text>
                      <IconArrowRight size={14} />
                      <Text>{ex.english}</Text>
                    </Group>
                  ))}
                </div>
              </>
            )}
          </Stack>
        )

      case 'Possession':
        return (
          <Stack gap="md">
            <Text>{details.suffixPossession}</Text>
            <Divider />
            <div>
              <Text fw={600} mb="xs">Example:</Text>
              <Group gap="md">
                <div>
                  <Text size="sm" c="dimmed">Base word:</Text>
                  <Text fw={700} size="lg" c="blue">{details.example.imw}</Text>
                  <Text size="sm">(house)</Text>
                </div>
                <IconArrowRight size={20} />
                <div>
                  <Text size="sm" c="dimmed">With possessive suffix:</Text>
                  <Text fw={700} size="lg" c="green">{details.example.imwei}</Text>
                  <Text size="sm">(my house)</Text>
                </div>
              </Group>
            </div>
          </Stack>
        )

      case 'Reduplication':
        return (
          <Stack gap="md">
            <div>
              <Text fw={600} mb="xs">Functions of Reduplication:</Text>
              <List spacing="xs">
                {details.function && details.function.map((func: string, i: number) => (
                  <List.Item key={i}>{func}</List.Item>
                ))}
              </List>
            </div>
            <Divider />
            <div>
              <Text fw={600} mb="xs">Examples:</Text>
              <Group gap="md">
                {details.examples && details.examples.map((example: string, i: number) => (
                  <Badge key={i} size="lg" variant="light" color="pink">{example}</Badge>
                ))}
              </Group>
            </div>
          </Stack>
        )

      case 'Counting Classifiers':
        const classifierColors: Record<string, string> = {
          'persons_animals': 'violet',
          'longObjects': 'blue',
          'flatObjects': 'orange',
          'roundObjects': 'green',
          'leis_garlands': 'pink',
          'groups': 'cyan',
          'bigBags': 'grape',
          'smallBags': 'indigo',
          'generalObjects': 'teal'
        }
        
        return (
          <Stack gap="md">
            <Text c="dimmed">{details.notes}</Text>
            <Divider />
            <Grid gutter="md">
              {Object.entries(details)
                .filter(([key]) => key !== 'notes')
                .map(([type, data]: [string, any]) => {
                  const color = classifierColors[type] || 'gray'
                  return (
                    <Grid.Col key={type} span={12}>
                      <Card withBorder p="md">
                        <Stack gap="sm">
                          <Group justify="space-between">
                            <div>
                              <Text size="sm" c="dimmed" tt="capitalize">{type.replace(/([A-Z])/g, ' $1').replace(/_/g, ' ').trim()}</Text>
                              <Group gap="xs" align="baseline">
                                <Text fw={700} size="lg" c={color}>{data.classifier}</Text>
                                <Text size="sm" c="dimmed">- {data.description}</Text>
                              </Group>
                            </div>
                          </Group>
                          <Divider />
                          <Grid gutter="xs">
                            {data.numbers && Object.entries(data.numbers).map(([num, word]: [string, any]) => (
                              <Grid.Col key={num} span={6}>
                                <Group gap="xs" wrap="nowrap">
                                  <Badge 
                                    size="lg" 
                                    variant="filled" 
                                    color={color}
                                    style={{ minWidth: '36px', justifyContent: 'center' }}
                                    c="white"
                                  >
                                    {num}
                                  </Badge>
                                  <Text fw={600} size="md">{word}</Text>
                                </Group>
                              </Grid.Col>
                            ))}
                          </Grid>
                        </Stack>
                      </Card>
                    </Grid.Col>
                  )
                })}
            </Grid>
          </Stack>
        )

      case 'Key Language Rules':
        return (
          <List spacing="md" size="sm">
            {details.keyRules && details.keyRules.map((rule: string, i: number) => (
              <List.Item key={i} icon={
                <ThemeIcon color="violet" size={24} radius="xl">
                  <IconBook size={14} />
                </ThemeIcon>
              }>
                {rule}
              </List.Item>
            ))}
          </List>
        )

      default:
        return <Text>Details not available</Text>
    }
  }

  return (
    <>
      <Stack gap="md">
        <Group justify="space-between" align="center">
          <div>
            <Title order={2}>Learn Chuukese</Title>
            <Text c="dimmed">Understand how the language works</Text>
          </div>
          <ThemeIcon size={50} radius="md" color="violet">
            <IconLanguage size={28} />
          </ThemeIcon>
        </Group>

        <Grid>
          {grammarCards.map((card, index) => (
            <Grid.Col key={index} span={{ base: 12, sm: 6, md: 4 }}>
              <Card 
                withBorder 
                radius="md" 
                p="md" 
                h="100%"
                style={{ cursor: 'pointer', transition: 'transform 0.2s' }}
                className="dictionary-card"
              >
                <Stack gap="sm" h="100%" justify="space-between">
                  <div>
                    <Group justify="space-between" mb="xs">
                      <Badge color={getCategoryColor(card.category)} variant="light" size="sm">
                        {card.category}
                      </Badge>
                      <ThemeIcon size={30} radius="md" color={getCategoryColor(card.category)} variant="light">
                        <IconBook size={16} />
                      </ThemeIcon>
                    </Group>
                    <Title order={4} mb="xs">{card.title}</Title>
                    <Text size="sm" c="dimmed">{card.description}</Text>
                  </div>
                  <Button
                    variant="light"
                    size="xs"
                    rightSection={<IconChevronRight size={14} />}
                    onClick={() => openSectionModal(card)}
                    fullWidth
                    color={getCategoryColor(card.category)}
                  >
                    Learn More
                  </Button>
                </Stack>
              </Card>
            </Grid.Col>
          ))}
        </Grid>
      </Stack>

      {/* Detail Modal */}
      <Modal
        opened={modalOpened}
        onClose={() => setModalOpened(false)}
        title={
          <Group>
            <Badge color={selectedSection ? getCategoryColor(selectedSection.category) : 'gray'} variant="light">
              {selectedSection?.category}
            </Badge>
            <Title order={3}>{selectedSection?.title}</Title>
          </Group>
        }
        size="xl"
      >
        {selectedSection && (
          <Stack gap="md">
            <Text c="dimmed">{selectedSection.description}</Text>
            <Divider />
            {renderSectionDetails(selectedSection)}
          </Stack>
        )}
      </Modal>
    </>
  )
}

export default GrammarLearning
