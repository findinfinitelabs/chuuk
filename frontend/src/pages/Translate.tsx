import { useState, useEffect } from 'react'
import { Card, Title, Text, Textarea, Button, Group, Stack, Radio, Alert, Badge, Paper, LoadingOverlay, Progress } from '@mantine/core'
import { IconLanguage, IconArrowsExchange, IconCheck, IconAlertCircle, IconRobot, IconRefresh, IconBrandGoogle, IconDeviceFloppy, IconBrain } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import axios from 'axios'

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

function Translate() {
  const [text, setText] = useState('')
  const [translations, setTranslations] = useState<TranslationResults>({})
  const [correction, setCorrection] = useState('')
  const [direction, setDirection] = useState<'auto' | 'chk_to_en' | 'en_to_chk'>('auto')
  const [loading, setLoading] = useState(false)
  const [savingCorrection, setSavingCorrection] = useState(false)
  const [error, setError] = useState('')
  const [modelStatus, setModelStatus] = useState<'available' | 'unavailable' | 'checking'>('checking')
  const [trainingStatus, setTrainingStatus] = useState<TrainingStatus | null>(null)

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

  const handleTranslate = async () => {
    if (!text.trim()) return

    setLoading(true)
    setError('')
    setTranslations({})
    setCorrection('') // Clear previous correction

    try {
      const response = await axios.post('/api/translate', {
        text: text.trim(),
        direction
      })

      if (response.data.success) {
        setTranslations(response.data.translations)
      } else {
        setError(response.data.error || 'Translation failed')
      }
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
            <Radio value="auto" label="🔮 Auto-Detect Language" />
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
          <Textarea
            placeholder="Enter text to translate..."
            value={text}
            onChange={(e) => setText(e.target.value)}
            minRows={6}
            maxRows={10}
            styles={{
              input: {
                fontFamily: '"Noto Sans", "Arial Unicode MS", system-ui, sans-serif'
              }
            }}
          />
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
