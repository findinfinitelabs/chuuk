import { useState, useEffect, useRef } from 'react'
import {
  Card,
  Title,
  Text,
  Button,
  Group,
  Stack,
  Badge,
  Progress,
  SimpleGrid,
  Textarea,
  Select,
  Alert,
  Loader,
  Divider,
  Box,
  Table,
  ScrollArea,
  Timeline,
  ThemeIcon,
  Code,
  Tooltip,
  ActionIcon,
} from '@mantine/core'
import {
  IconBrain,
  IconBolt,
  IconCheck,
  IconX,
  IconAlertCircle,
  IconRefresh,
  IconPlayerPlay,
  IconArrowsLeftRight,
  IconDatabase,
  IconClock,
  IconActivity,
  IconMerge,
} from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import axios from 'axios'
import styles from './AITraining.module.css'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface TrainingRun {
  run_id: string
  trigger: string
  started_at: string
  finished_at: string | null
  status: 'running' | 'completed' | 'failed'
  mode: string
  pairs_used: number
  chk_to_en_loss: number | null
  en_to_chk_loss: number | null
  lora_updates: number
  message: string
  logs: string[]
}

interface TrainingStatus {
  is_training: boolean
  current_run: TrainingRun | null
  lora_update_count: number
  lora_merge_threshold: number
  scheduler_interval_minutes: number
  scheduler_min_new_pairs: number
  recent_runs: TrainingRun[]
  ollama_enabled: boolean
}

interface DataSources {
  dictionary_entries: number
  phrase_pairs: number
  paragraph_pairs: number
  article_sentences: number
  total_pairs: number
  lora_update_count: number
}

// ---------------------------------------------------------------------------
// Helper utilities
// ---------------------------------------------------------------------------
function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
}

function relativeDuration(iso: string | null | undefined): string {
  if (!iso) return ''
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

function statusColor(status: string): string {
  if (status === 'completed') return 'green'
  if (status === 'failed') return 'red'
  if (status === 'running') return 'blue'
  return 'gray'
}

function triggerLabel(trigger: string): string {
  const map: Record<string, string> = {
    manual: 'Manual',
    scheduled: 'Scheduled',
    lora_merge: 'LoRA Merge',
    correction: 'Correction',
  }
  return map[trigger] ?? trigger
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function AITraining() {
  const [status, setStatus] = useState<TrainingStatus | null>(null)
  const [sources, setSources] = useState<DataSources | null>(null)
  const [history, setHistory] = useState<TrainingRun[]>([])
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [merging, setMerging] = useState(false)
  const [loraTeaching, setLoraTeaching] = useState(false)
  const [loraChuukese, setLoraChuukese] = useState('')
  const [loraEnglish, setLoraEnglish] = useState('')
  const [loraDirection, setLoraDirection] = useState<string>('both')
  const [liveLog, setLiveLog] = useState<string[]>([])
  const logEndRef = useRef<HTMLDivElement>(null)
  const sseRef = useRef<EventSource | null>(null)

  // ── Data fetching ────────────────────────────────────────────────────────
  const fetchAll = async () => {
    try {
      const [statusRes, sourcesRes, historyRes] = await Promise.all([
        axios.get('/api/ai-training/status'),
        axios.get('/api/ai-training/sources'),
        axios.get('/api/ai-training/history?limit=10'),
      ])
      setStatus(statusRes.data)
      setSources(sourcesRes.data)
      setHistory(historyRes.data.runs ?? [])
    } catch {
      // silent — will retry on next poll
    } finally {
      setLoading(false)
    }
  }

  // ── SSE stream for live progress ─────────────────────────────────────────
  useEffect(() => {
    fetchAll()

    const es = new EventSource('/api/ai-training/stream')
    sseRef.current = es

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'status') {
          setStatus(data)
        } else if (data.message) {
          setLiveLog((prev) => {
            const next = [...prev, `[${new Date().toLocaleTimeString()}] ${data.message}`]
            return next.slice(-200)
          })
          // Refresh status when a run completes
          if (data.type === 'training_progress' || data.type === 'lora_progress') {
            if (data.progress === 100 || data.status === 'completed' || data.status === 'failed') {
              fetchAll()
            }
          }
        }
      } catch {/* ignore parse errors */}
    }

    // Refresh status every 30s as fallback
    const interval = setInterval(fetchAll, 30_000)

    return () => {
      es.close()
      clearInterval(interval)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Auto-scroll live log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [liveLog])

  // ── Actions ──────────────────────────────────────────────────────────────
  const handleStartTraining = async () => {
    setStarting(true)
    try {
      const res = await axios.post('/api/ai-training/start', { num_epochs: 3, batch_size: 2 })
      if (res.data.success) {
        notifications.show({
          title: 'Training started',
          message: `Run ID: ${res.data.run_id?.slice(0, 8)}…`,
          color: 'blue',
          icon: <IconBrain size={16} />,
        })
        setLiveLog([])
      } else {
        notifications.show({
          title: 'Could not start training',
          message: res.data.message,
          color: 'orange',
        })
      }
    } catch (e: any) {
      notifications.show({ title: 'Error', message: e?.message, color: 'red' })
    } finally {
      setStarting(false)
    }
  }

  const handleMergeLora = async () => {
    setMerging(true)
    try {
      const res = await axios.post('/api/ai-training/merge-lora')
      notifications.show({
        title: res.data.success ? 'Merge triggered' : 'Merge failed',
        message: res.data.message,
        color: res.data.success ? 'teal' : 'red',
      })
    } catch (e: any) {
      notifications.show({ title: 'Error', message: e?.message, color: 'red' })
    } finally {
      setMerging(false)
    }
  }

  const handleLoraTeach = async () => {
    if (!loraChuukese.trim() || !loraEnglish.trim()) {
      notifications.show({ title: 'Missing input', message: 'Enter both Chuukese and English text.', color: 'orange' })
      return
    }
    setLoraTeaching(true)
    try {
      const res = await axios.post('/api/ai-training/lora-teach', {
        chuukese: loraChuukese.trim(),
        english: loraEnglish.trim(),
        direction: loraDirection,
      })
      if (res.data.success) {
        notifications.show({
          title: 'LoRA teach queued',
          message: res.data.message,
          color: 'teal',
          icon: <IconBolt size={16} />,
        })
        setLoraChuukese('')
        setLoraEnglish('')
      } else {
        notifications.show({ title: 'LoRA failed', message: res.data.message, color: 'red' })
      }
    } catch (e: any) {
      notifications.show({ title: 'Error', message: e?.message, color: 'red' })
    } finally {
      setLoraTeaching(false)
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <Stack align="center" justify="center" h={300}>
        <Loader size="lg" />
        <Text c="dimmed">Loading AI Training engine…</Text>
      </Stack>
    )
  }

  const currentRun = status?.current_run
  const loraPercent = status
    ? Math.min(100, Math.round((status.lora_update_count / status.lora_merge_threshold) * 100))
    : 0

  return (
    <div className={styles.container}>
      <Group justify="space-between" mb="lg" wrap="nowrap">
        <Group gap="sm">
          <ThemeIcon size="xl" variant="gradient" gradient={{ from: 'blue', to: 'violet' }}>
            <IconBrain size={22} />
          </ThemeIcon>
          <div>
            <Title order={2} className={styles.pageTitle}>AI Training</Title>
            <Text size="sm" c="dimmed">Continuous Helsinki-NLP fine-tuning with LoRA quick-teach</Text>
          </div>
        </Group>
        <Tooltip label="Refresh status">
          <ActionIcon variant="subtle" onClick={fetchAll} size="lg">
            <IconRefresh size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>

      {/* ── Engine Status Cards ─────────────────────────────────────────── */}
      <SimpleGrid cols={{ base: 1, sm: 3 }} mb="md">
        <Card withBorder className={styles.engineCard}>
          <Group gap="xs" mb={4}>
            <IconArrowsLeftRight size={16} color="var(--mantine-color-blue-6)" />
            <Text fw={600} size="sm">Helsinki CHK→EN</Text>
          </Group>
          <Badge color="green" variant="light">Active</Badge>
          <Text size="xs" c="dimmed" mt={4}>Fine-tuned Marian MT</Text>
        </Card>

        <Card withBorder className={styles.engineCard}>
          <Group gap="xs" mb={4}>
            <IconArrowsLeftRight size={16} color="var(--mantine-color-violet-6)" />
            <Text fw={600} size="sm">Helsinki EN→CHK</Text>
          </Group>
          <Badge color="green" variant="light">Active</Badge>
          <Text size="xs" c="dimmed" mt={4}>Fine-tuned Marian MT</Text>
        </Card>

        <Card withBorder className={styles.engineCard}>
          <Group gap="xs" mb={4}>
            <IconBrain size={16} color="var(--mantine-color-gray-5)" />
            <Text fw={600} size="sm">Ollama LLM</Text>
          </Group>
          <Badge color="gray" variant="light">
            {status?.ollama_enabled ? 'Active' : 'Disabled'}
          </Badge>
          <Text size="xs" c="dimmed" mt={4}>
            {status?.ollama_enabled ? 'chuukese-translator model' : 'Set OLLAMA_ENABLED=true to enable'}
          </Text>
        </Card>
      </SimpleGrid>

      {/* ── Current Training Progress ───────────────────────────────────── */}
      {currentRun && (
        <Alert
          icon={<Loader size="xs" />}
          title={`Training in progress — ${currentRun.trigger} run`}
          color="blue"
          mb="md"
        >
          <Stack gap={4}>
            <Text size="sm">{currentRun.message || 'Initialising…'}</Text>
            <Progress value={undefined} animated size="sm" />
            <Text size="xs" c="dimmed">Run ID: {currentRun.run_id.slice(0, 8)}… · Started: {formatTime(currentRun.started_at)}</Text>
          </Stack>
        </Alert>
      )}

      <SimpleGrid cols={{ base: 1, lg: 2 }} mb="md">
        {/* ── Scheduler Status ─────────────────────────────────────────── */}
        <Card withBorder>
          <Title order={5} mb="sm">
            <Group gap="xs"><IconClock size={16} />Scheduler</Group>
          </Title>
          <Stack gap={6}>
            <Group justify="space-between">
              <Text size="sm" c="dimmed">Interval</Text>
              <Text size="sm" fw={500}>{status?.scheduler_interval_minutes ?? 30} min</Text>
            </Group>
            <Group justify="space-between">
              <Text size="sm" c="dimmed">Min new pairs to trigger</Text>
              <Text size="sm" fw={500}>{status?.scheduler_min_new_pairs ?? 10} pairs</Text>
            </Group>
            <Group justify="space-between">
              <Text size="sm" c="dimmed">LoRA updates since last merge</Text>
              <Text size="sm" fw={500}>{status?.lora_update_count ?? 0} / {status?.lora_merge_threshold ?? 50}</Text>
            </Group>
            <Progress
              value={loraPercent}
              color={loraPercent >= 100 ? 'orange' : 'teal'}
              size="sm"
              label={`${loraPercent}%`}
              mt={4}
            />
            <Group justify="space-between" mt="xs">
              <Button
                leftSection={<IconPlayerPlay size={14} />}
                onClick={handleStartTraining}
                loading={starting}
                disabled={status?.is_training}
                size="xs"
              >
                Train Now
              </Button>
              <Button
                leftSection={<IconMerge size={14} />}
                variant="light"
                color="orange"
                onClick={handleMergeLora}
                loading={merging}
                disabled={status?.is_training || (status?.lora_update_count ?? 0) === 0}
                size="xs"
              >
                Merge LoRA
              </Button>
            </Group>
          </Stack>
        </Card>

        {/* ── Data Sources ─────────────────────────────────────────────── */}
        <Card withBorder>
          <Title order={5} mb="sm">
            <Group gap="xs"><IconDatabase size={16} />Training Data Sources</Group>
          </Title>
          {sources ? (
            <Stack gap={4}>
              {[
                { label: 'Dictionary entries', value: sources.dictionary_entries },
                { label: 'Phrase pairs', value: sources.phrase_pairs },
                { label: 'Paragraph pairs', value: sources.paragraph_pairs },
                { label: 'Article sentence pairs', value: sources.article_sentences },
              ].map(({ label, value }) => (
                <Group key={label} justify="space-between">
                  <Text size="sm" c="dimmed">{label}</Text>
                  <Badge variant="outline" size="sm">{value.toLocaleString()}</Badge>
                </Group>
              ))}
              <Divider my={4} />
              <Group justify="space-between">
                <Text size="sm" fw={600}>Total pairs</Text>
                <Badge color="blue" size="sm">{sources.total_pairs.toLocaleString()}</Badge>
              </Group>
            </Stack>
          ) : (
            <Loader size="sm" />
          )}
        </Card>
      </SimpleGrid>

      {/* ── LoRA Quick Teach ────────────────────────────────────────────── */}
      <Card withBorder mb="md">
        <Title order={5} mb="sm">
          <Group gap="xs"><IconBolt size={16} />Teach This Pair Now (LoRA)</Group>
        </Title>
        <Text size="xs" c="dimmed" mb="sm">
          Instantly updates the model with a single translation pair via LoRA — no full retrain needed.
        </Text>
        <SimpleGrid cols={{ base: 1, sm: 2 }} mb="sm">
          <Textarea
            label="Chuukese"
            placeholder="e.g. Iei meinisin me fis…"
            value={loraChuukese}
            onChange={(e) => setLoraChuukese(e.currentTarget.value)}
            autosize
            minRows={2}
            maxRows={4}
          />
          <Textarea
            label="English"
            placeholder="e.g. This is everything that…"
            value={loraEnglish}
            onChange={(e) => setLoraEnglish(e.currentTarget.value)}
            autosize
            minRows={2}
            maxRows={4}
          />
        </SimpleGrid>
        <Group>
          <Select
            label="Direction"
            value={loraDirection}
            onChange={(v) => setLoraDirection(v ?? 'both')}
            data={[
              { value: 'both', label: 'Both directions' },
              { value: 'chk_to_en', label: 'CHK → EN only' },
              { value: 'en_to_chk', label: 'EN → CHK only' },
            ]}
            size="sm"
            w={180}
          />
          <Button
            leftSection={<IconBolt size={14} />}
            onClick={handleLoraTeach}
            loading={loraTeaching}
            mt="xl"
            color="teal"
            size="sm"
          >
            Teach Now
          </Button>
        </Group>
      </Card>

      {/* ── Live Training Log ────────────────────────────────────────────── */}
      <Card withBorder mb="md">
        <Group justify="space-between" mb="xs">
          <Title order={5}>
            <Group gap="xs"><IconActivity size={16} />Live Training Log</Group>
          </Title>
          <Button size="xs" variant="subtle" onClick={() => setLiveLog([])}>Clear</Button>
        </Group>
        <ScrollArea h={200} className={styles.logBox}>
          {liveLog.length === 0 ? (
            <Text size="xs" c="dimmed" ta="center" mt="xl">
              Waiting for training events… Start a training run or teach a pair.
            </Text>
          ) : (
            <Stack gap={2}>
              {liveLog.map((line, i) => (
                <Code key={i} block className={styles.logLine}>{line}</Code>
              ))}
              <div ref={logEndRef} />
            </Stack>
          )}
        </ScrollArea>
      </Card>

      {/* ── Run History ─────────────────────────────────────────────────── */}
      <Card withBorder>
        <Title order={5} mb="sm">
          <Group gap="xs"><IconClock size={16} />Recent Training Runs</Group>
        </Title>
        {history.length === 0 ? (
          <Text size="sm" c="dimmed" ta="center" py="md">No training runs yet.</Text>
        ) : (
          <ScrollArea>
            <Table striped highlightOnHover withTableBorder>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>ID</Table.Th>
                  <Table.Th>Trigger</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Mode</Table.Th>
                  <Table.Th>Pairs</Table.Th>
                  <Table.Th>Loss (CHK→EN)</Table.Th>
                  <Table.Th>Started</Table.Th>
                  <Table.Th>Message</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {history.map((run) => (
                  <Table.Tr key={run.run_id}>
                    <Table.Td>
                      <Text size="xs" ff="monospace">{run.run_id.slice(0, 8)}…</Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge size="xs" variant="light">{triggerLabel(run.trigger)}</Badge>
                    </Table.Td>
                    <Table.Td>
                      <Badge size="xs" color={statusColor(run.status)}>
                        {run.status}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs">{run.mode}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs">{run.pairs_used}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs">
                        {run.chk_to_en_loss != null ? run.chk_to_en_loss.toFixed(4) : '—'}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Tooltip label={formatTime(run.started_at)}>
                        <Text size="xs" c="dimmed">{relativeDuration(run.started_at)}</Text>
                      </Tooltip>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" lineClamp={1} maw={200}>{run.message}</Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        )}
      </Card>
    </div>
  )
}
