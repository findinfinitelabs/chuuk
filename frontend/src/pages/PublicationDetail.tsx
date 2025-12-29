import { useEffect, useState, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Title, Text, Button, Group, Stack, Grid, Badge, Loader, Alert, Select, Checkbox, Progress, Modal, ScrollArea, Slider } from '@mantine/core'
import { IconUpload, IconFileText, IconAlertCircle, IconEye, IconCheck, IconLoader } from '@tabler/icons-react'
import { Dropzone, MIME_TYPES } from '@mantine/dropzone'
import { notifications } from '@mantine/notifications'
import axios from 'axios'
import './PublicationDetail.css'

interface Page {
  id: string
  filename: string
  ocr_text?: string // AI-extracted text
  processed: boolean
  upload_date?: string
  entries_count?: number
  processing_error?: string
}

interface Publication {
  id: string
  title: string
  description?: string
  created_date: string
  pages: Page[]
}

interface UploadProgress {
  filename: string
  progress: number
  status: 'uploading' | 'processing' | 'complete' | 'error'
  sessionId?: string
}

interface ProcessingLog {
  timestamp: string
  level: string
  message: string
  data?: Record<string, unknown>
}

interface ProcessingStatus {
  filename: string
  status: string
  logs: ProcessingLog[]
  stats: {
    pages_processed: number
    words_indexed: number
    entries_created: number
    ocr_method: string | null
    errors: number
    total_pages?: number
  }
  current_page: number
  total_pages: number
}

function PublicationDetail() {
  const { id } = useParams<{ id: string }>()
  const [publication, setPublication] = useState<Publication | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<UploadProgress[]>([])
  const [aiEnabled, setAiEnabled] = useState(true)
  const [aiLanguage, setAiLanguage] = useState('eng+chk')
  const [indexDictionary, setIndexDictionary] = useState(true)
  const [importConfidenceScore, setImportConfidenceScore] = useState(100)
  
  // Update confidence modal
  const [showUpdateConfidenceModal, setShowUpdateConfidenceModal] = useState(false)
  const [updateConfidenceScore, setUpdateConfidenceScore] = useState(100)
  const [updatingConfidence, setUpdatingConfidence] = useState(false)
  
  // Processing status modal
  const [showProcessingModal, setShowProcessingModal] = useState(false)
  const [processingStatus, setProcessingStatus] = useState<ProcessingStatus | null>(null)
  const logScrollRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (id) {
      loadPublication()
    }
  }, [id])

  const loadPublication = () => {
    axios.get(`/api/publications/${id}`)
      .then(response => {
        setPublication(response.data)
        setLoading(false)
      })
      .catch(() => {
        setError('Failed to load publication')
        setLoading(false)
      })
  }

  const updatePublicationConfidence = async () => {
    if (!id) return
    
    setUpdatingConfidence(true)
    try {
      const response = await axios.post(`/api/publications/${id}/update-confidence`, {
        confidence_score: updateConfidenceScore
      })
      
      notifications.show({
        title: 'Confidence Updated',
        message: response.data.message,
        color: 'green'
      })
      
      setShowUpdateConfidenceModal(false)
    } catch (err: any) {
      notifications.show({
        title: 'Update Failed',
        message: err.response?.data?.error || 'Failed to update confidence scores',
        color: 'red'
      })
    } finally {
      setUpdatingConfidence(false)
    }
  }

  // Connect to processing status stream
  const connectToProcessingStream = (sessionId: string, filename: string) => {
    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    setShowProcessingModal(true)
    setProcessingStatus({
      filename,
      status: 'started',
      logs: [],
      stats: { pages_processed: 0, words_indexed: 0, entries_created: 0, ocr_method: null, errors: 0 },
      current_page: 0,
      total_pages: 1
    })

    const eventSource = new EventSource(`/api/processing/stream/${sessionId}`)
    eventSourceRef.current = eventSource

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        
        if (data.error) {
          console.error('Processing error:', data.error)
          eventSource.close()
          return
        }

        setProcessingStatus({
          filename: data.filename || filename,
          status: data.status || 'processing',
          logs: data.logs || [],
          stats: data.stats || { pages_processed: 0, words_indexed: 0, entries_created: 0, ocr_method: null, errors: 0 },
          current_page: data.current_page || 0,
          total_pages: data.total_pages || 1
        })

        // Auto-scroll to bottom of logs
        if (logScrollRef.current) {
          logScrollRef.current.scrollTop = logScrollRef.current.scrollHeight
        }

        // Close connection when complete
        if (data.status === 'completed' || data.status === 'failed') {
          setTimeout(() => {
            eventSource.close()
            loadPublication() // Refresh publication data
          }, 1000)
        }
      } catch (e) {
        console.error('Error parsing SSE data:', e)
      }
    }

    eventSource.onerror = () => {
      console.error('SSE connection error')
      eventSource.close()
    }
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  const handleUpload = async (files: File[]) => {
    if (!id || files.length === 0) return

    setUploading(true)
    const progressMap: UploadProgress[] = files.map(f => ({
      filename: f.name,
      progress: 0,
      status: 'uploading'
    }))
    setUploadProgress(progressMap)

    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      const formData = new FormData()
      formData.append('file', file)
      
      // Check if this is a CSV file - use different endpoint
      const isCSV = file.name.toLowerCase().endsWith('.csv') || file.name.toLowerCase().endsWith('.tsv')
      
      if (!isCSV) {
        formData.append('ocr', aiEnabled.toString())
        formData.append('lang', aiLanguage)
        formData.append('index_dictionary', indexDictionary.toString())
      } else {
        // For CSV imports, include confidence score
        formData.append('confidence_score', importConfidenceScore.toString())
      }

      try {
        progressMap[i].status = 'uploading'
        setUploadProgress([...progressMap])

        const endpoint = isCSV ? `/api/publications/${id}/upload_csv` : `/api/publications/${id}/upload`
        const response = await axios.post(endpoint, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (progressEvent) => {
            const percentCompleted = progressEvent.total
              ? Math.round((progressEvent.loaded * 100) / progressEvent.total)
              : 0
            progressMap[i].progress = percentCompleted
            setUploadProgress([...progressMap])
          }
        })

        // Check for session_id to show processing status
        const sessionId = response.data?.session_id
        if (sessionId && (aiEnabled || isCSV)) {
          progressMap[i].status = 'processing'
          progressMap[i].sessionId = sessionId
          setUploadProgress([...progressMap])
          
          // Connect to processing stream to show real-time status
          connectToProcessingStream(sessionId, file.name)
        } else {
          progressMap[i].status = 'complete'
          progressMap[i].progress = 100
          setUploadProgress([...progressMap])
        }

        notifications.show({
          title: 'Success',
          message: `${file.name} uploaded successfully`,
          color: 'green'
        })
      } catch (err: any) {
        progressMap[i].status = 'error'
        setUploadProgress([...progressMap])
        
        // Extract error message from response
        const errorMessage = err.response?.data?.error || err.message || 'Unknown error'
        console.error('Upload error details:', {
          status: err.response?.status,
          error: errorMessage,
          fullResponse: err.response?.data
        })
        
        notifications.show({
          title: 'Upload Failed',
          message: `${file.name}: ${errorMessage}`,
          color: 'red'
        })
      }
    }

    setUploading(false)
    setTimeout(() => {
      setUploadProgress([])
      loadPublication()
    }, 2000)
  }

  const reprocessAI = async (pageFilename: string) => {
    try {
      const formData = new FormData()
      formData.append('pub_id', id || '')
      formData.append('filename', pageFilename)
      formData.append('page_number', '1')
      
      const response = await axios.post(`/api/ocr/reprocess`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      
      const data = response.data
      
      if (data.success) {
        const stats = data.stats
        notifications.show({
          title: 'Reprocessing Complete',
          message: `✓ ${stats.new_entries || 0} new, ${stats.updated_entries || 0} updated`,
          color: 'green'
        })
        
        // Update page locally with new count
        if (publication) {
          const totalEntries = (stats.new_entries || 0) + (stats.updated_entries || 0)
          setPublication({
            ...publication,
            pages: publication.pages.map(p => 
              p.filename === pageFilename
                ? { ...p, entries_count: totalEntries > 0 ? totalEntries : p.entries_count, processing_error: undefined }
                : p
            )
          })
        }
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.error || err.response?.data?.message || 'Reprocessing failed'
      notifications.show({
        title: 'Reprocessing Error',
        message: errorMsg,
        color: 'red'
      })
    }
  }

  const processAI = async (pageFilename: string) => {
    try {
      const formData = new FormData()
      formData.append('pub_id', id || '')
      formData.append('filename', pageFilename)
      formData.append('lang', aiLanguage)
      formData.append('index_dictionary', indexDictionary.toString())
      
      const response = await axios.post(`/api/ocr/process`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      
      const data = response.data
      
      if (data.success) {
        notifications.show({
          title: 'AI Processing Complete',
          message: data.indexed 
            ? `✓ ${data.entries_count} dictionary entries added to database` 
            : 'OCR text extracted',
          color: data.indexed ? 'green' : 'blue'
        })
        
        // Update page locally
        if (publication) {
          setPublication({
            ...publication,
            pages: publication.pages.map(p => 
              p.filename === pageFilename
                ? { ...p, processed: true, entries_count: data.entries_count, ocr_text: data.ocr_text, processing_error: undefined }
                : p
            )
          })
        }
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.error || err.response?.data?.message || 'AI processing failed'
      notifications.show({
        title: 'Processing Error',
        message: errorMsg,
        color: 'red'
      })
      
      // Update page with error
      if (publication) {
        setPublication({
          ...publication,
          pages: publication.pages.map(p => 
            p.filename === pageFilename
              ? { ...p, processing_error: errorMsg }
              : p
          )
        })
      }
    }
  }

  if (loading) {
    return <Loader />
  }

  if (error || !publication) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
        {error || 'Publication not found'}
      </Alert>
    )
  }

  return (
    <Stack gap="lg">
      <Card withBorder>
        <Group justify="space-between" align="flex-start">
          <div>
            <Title order={2} mb="sm">{publication.title}</Title>
            {publication.description && <Text color="dimmed">{publication.description}</Text>}
            <Group mt="md">
              <Badge size="lg" variant="light">
                {publication.pages.length} pages
              </Badge>
              <Text size="sm" color="dimmed">
                Created: {new Date(publication.created_date).toLocaleDateString()}
              </Text>
            </Group>
          </div>
          <Button
            variant="light"
            color="blue"
            onClick={() => setShowUpdateConfidenceModal(true)}
          >
            Update Confidence
          </Button>
        </Group>
      </Card>

      {/* Upload Section */}
      <Card withBorder>
        <Title order={3} mb="md">Upload Dictionary Pages</Title>
        
        <Stack gap="md" mb="md">
          <Group grow>
            <Select
              label="AI Language Detection"
              value={aiLanguage}
              onChange={(val) => setAiLanguage(val || 'eng+chk')}
              data={[
                { value: 'eng+chk', label: 'English + Chuukese' },
                { value: 'eng', label: 'English Only' },
                { value: 'chk', label: 'Chuukese Only' }
              ]}
            />
          </Group>
          
          <Group>
            <Checkbox
              label="Enable AI Text Processing"
              checked={aiEnabled}
              onChange={(e) => setAiEnabled(e.currentTarget.checked)}
            />
            <Checkbox
              label="Index Dictionary Entries"
              checked={indexDictionary}
              onChange={(e) => setIndexDictionary(e.currentTarget.checked)}
            />
          </Group>
          
          <Stack gap="lg" className="confidence-slider-container">
            <Text size="sm" fw={500}>
              Import Confidence Level: {importConfidenceScore}%
            </Text>
            <Slider
              value={importConfidenceScore}
              onChange={setImportConfidenceScore}
              min={0}
              max={100}
              step={5}
              marks={[
                { value: 0, label: '0%' },
                { value: 50, label: '50%' },
                { value: 100, label: '100%' }
              ]}
              color={
                importConfidenceScore >= 90 ? 'blue' :
                importConfidenceScore >= 70 ? 'green' :
                importConfidenceScore >= 40 ? 'yellow' : 'red'
              }
              className="confidence-slider"
            />
            <Text size="xs" c="dimmed">
              Set confidence level for CSV/TSV dictionary imports
            </Text>
          </Stack>
        </Stack>

        <Dropzone
          onDrop={handleUpload}
          accept={[MIME_TYPES.png, MIME_TYPES.jpeg, MIME_TYPES.pdf, MIME_TYPES.docx, MIME_TYPES.csv, 'image/*', 'text/csv', 'text/tab-separated-values']}
          loading={uploading}
          multiple
        >
          <Group justify="center" gap="xl" className="dropzone-content">
            <Dropzone.Accept>
              <IconUpload size={50} color="var(--mantine-color-blue-6)" />
            </Dropzone.Accept>
            <Dropzone.Reject>
              <IconAlertCircle size={50} color="var(--mantine-color-red-6)" />
            </Dropzone.Reject>
            <Dropzone.Idle>
              <IconUpload size={50} color="var(--mantine-color-gray-5)" />
            </Dropzone.Idle>

            <div>
              <Text size="xl" inline>
                Drag images or CSV files here or click to select files
              </Text>
              <Text size="sm" color="dimmed" inline mt={7}>
                Attach as many files as you like (PNG, JPG, PDF, DOCX, CSV, TSV supported)
              </Text>
            </div>
          </Group>
        </Dropzone>

        {uploadProgress.length > 0 && (
          <Stack gap="sm" mt="md">
            {uploadProgress.map((file, index) => (
              <div key={index}>
                <Group justify="space-between" mb={4}>
                  <Text size="sm">{file.filename}</Text>
                  <Badge
                    color={
                      file.status === 'complete' ? 'green' :
                      file.status === 'error' ? 'red' :
                      'blue'
                    }
                  >
                    {file.status}
                  </Badge>
                </Group>
                <Progress value={file.progress} color={file.status === 'error' ? 'red' : 'blue'} />
              </div>
            ))}
          </Stack>
        )}
      </Card>

      {/* Pages Grid */}
      <Card withBorder>
        <Title order={3} mb="md">Uploaded Pages ({publication.pages.length})</Title>

        {publication.pages.length === 0 ? (
          <Text color="dimmed" ta="center" py="xl">
            No pages uploaded yet. Use the upload section above to add dictionary pages.
          </Text>
        ) : (
          <Grid>
            {publication.pages.map((page, index) => (
              <Grid.Col key={`${page.filename}-${index}`} span={{ base: 12, sm: 6, md: 4 }}>
                <Card withBorder p="md">
                  <Group justify="space-between" mb="xs">
                    <IconFileText size={24} color="var(--mantine-color-blue-6)" />
                    <Badge color={page.processing_error ? 'red' : page.processed ? 'green' : 'yellow'} variant="light">
                      {page.processing_error ? (
                        <Group gap={4}>
                          <IconAlertCircle size={12} />
                          <span>Error</span>
                        </Group>
                      ) : page.processed ? (
                        <Group gap={4}>
                          <IconCheck size={12} />
                          <span>Processed</span>
                        </Group>
                      ) : 'Pending'}
                    </Badge>
                  </Group>
                  
                  <Text fw={500} size="sm" mb="xs" lineClamp={1}>
                    {page.filename}
                  </Text>
                  
                  {page.entries_count !== undefined && page.entries_count > 0 && (
                    <Badge color="teal" variant="light" size="sm" mb="xs">
                      {page.entries_count} entries indexed
                    </Badge>
                  )}
                  
                  {page.processing_error && (
                    <Alert color="red" variant="light" p="xs" mb="xs">
                      <Text size="xs">{page.processing_error}</Text>
                    </Alert>
                  )}
                  
                  {page.ocr_text && (
                    <Text size="xs" color="dimmed" lineClamp={3} mb="xs">
                      {page.ocr_text.substring(0, 150)}...
                    </Text>
                  )}
                  
                  <Group gap="xs">
                    {!page.processed && (
                      <Button
                        size="xs"
                        variant="outline"
                        fullWidth
                        leftSection={<IconEye size={14} />}
                        onClick={() => processAI(page.filename)}
                      >
                        Process with AI
                      </Button>
                    )}
                    
                    {page.processed && (
                      <Button
                        size="xs"
                        variant="light"
                        fullWidth
                        color="orange"
                        onClick={() => reprocessAI(page.filename)}
                      >
                        Reload & Update
                      </Button>
                    )}
                  </Group>
                </Card>
              </Grid.Col>
            ))}
          </Grid>
        )}
      </Card>

      {/* Processing Status Modal */}
      <Modal
        opened={showProcessingModal}
        onClose={() => setShowProcessingModal(false)}
        title={
          <Group>
            {processingStatus?.status === 'completed' ? (
              <IconCheck size={20} color="green" />
            ) : processingStatus?.status === 'failed' ? (
              <IconAlertCircle size={20} color="red" />
            ) : (
              <IconLoader size={20} className="spinning-icon" />
            )}
            <Text fw={600}>Processing: {processingStatus?.filename}</Text>
          </Group>
        }
        size="lg"
      >
        <Stack gap="md">
          {/* Status Badge */}
          <Group>
            <Badge 
              color={
                processingStatus?.status === 'completed' ? 'green' : 
                processingStatus?.status === 'failed' ? 'red' : 
                'blue'
              }
              size="lg"
            >
              {processingStatus?.status?.toUpperCase() || 'PROCESSING'}
            </Badge>
            {processingStatus?.stats?.ocr_method && (
              <Badge variant="outline" color="gray">
                {processingStatus.stats.ocr_method}
              </Badge>
            )}
          </Group>

          {/* Progress Bar */}
          {processingStatus && processingStatus.total_pages > 0 && (
            <div>
              <Group justify="space-between" mb={4}>
                <Text size="sm">Page Progress</Text>
                <Text size="sm" color="dimmed">
                  {processingStatus.current_page} / {processingStatus.total_pages}
                </Text>
              </Group>
              <Progress 
                value={(processingStatus.current_page / processingStatus.total_pages) * 100} 
                color="blue" 
                size="lg"
                animated={processingStatus.status !== 'completed' && processingStatus.status !== 'failed'}
              />
            </div>
          )}

          {/* Stats */}
          {processingStatus?.stats && (
            <Group gap="lg">
              <div>
                <Text size="xs" color="dimmed">Pages Processed</Text>
                <Text size="lg" fw={600}>{processingStatus.stats.pages_processed}</Text>
              </div>
              <div>
                <Text size="xs" color="dimmed">Words Indexed</Text>
                <Text size="lg" fw={600}>{processingStatus.stats.words_indexed}</Text>
              </div>
              <div>
                <Text size="xs" color="dimmed">Entries Created</Text>
                <Text size="lg" fw={600} c="green">{processingStatus.stats.entries_created}</Text>
              </div>
              {processingStatus.stats.errors > 0 && (
                <div>
                  <Text size="xs" color="dimmed">Errors</Text>
                  <Text size="lg" fw={600} c="red">{processingStatus.stats.errors}</Text>
                </div>
              )}
            </Group>
          )}

          {/* Log Output */}
          <div>
            <Text size="sm" fw={500} mb="xs">Processing Log</Text>
            <ScrollArea h={250} viewportRef={logScrollRef} style={{ backgroundColor: '#1e1e1e', borderRadius: 8 }}>
              <Stack gap={2} p="sm">
                {processingStatus?.logs?.map((log, idx) => (
                  <Group key={idx} gap="xs" wrap="nowrap" align="flex-start">
                    <Text size="xs" c="dimmed" style={{ fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </Text>
                    <Text 
                      size="xs" 
                      c={log.level === 'error' ? 'red' : log.level === 'warning' ? 'yellow' : 'gray.4'}
                      style={{ fontFamily: 'monospace' }}
                    >
                      {log.message}
                    </Text>
                  </Group>
                )) || (
                  <Text size="xs" c="dimmed" style={{ fontFamily: 'monospace' }}>
                    Waiting for processing to start...
                  </Text>
                )}
              </Stack>
            </ScrollArea>
          </div>

          {/* Close Button */}
          {(processingStatus?.status === 'completed' || processingStatus?.status === 'failed') && (
            <Button onClick={() => setShowProcessingModal(false)} fullWidth>
              Close
            </Button>
          )}
        </Stack>
      </Modal>

      {/* Update Confidence Modal */}
      <Modal
        opened={showUpdateConfidenceModal}
        onClose={() => setShowUpdateConfidenceModal(false)}
        title="Update Confidence Score"
        size="md"
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Update the confidence score for all dictionary entries imported from this publication.
          </Text>
          
          <div>
            <Text size="sm" fw={500} mb="xs">
              Confidence Level: {updateConfidenceScore}%
            </Text>
            <Slider
              value={updateConfidenceScore}
              onChange={setUpdateConfidenceScore}
              min={0}
              max={100}
              step={5}
              marks={[
                { value: 0, label: '0%' },
                { value: 50, label: '50%' },
                { value: 100, label: '100%' }
              ]}
              color={
                updateConfidenceScore >= 90 ? 'blue' :
                updateConfidenceScore >= 70 ? 'green' :
                updateConfidenceScore >= 40 ? 'yellow' : 'red'
              }
            />
            <Text size="xs" c="dimmed" mt="md">
              {updateConfidenceScore >= 90 ? '🔥 Verified - Professionally confirmed' :
               updateConfidenceScore >= 70 ? '✅ High - Very confident' :
               updateConfidenceScore >= 40 ? '👍 Medium - Reasonably confident' :
               '⚠️ Low - Needs verification'}
            </Text>
          </div>
          
          <Group justify="flex-end" mt="md">
            <Button variant="outline" onClick={() => setShowUpdateConfidenceModal(false)}>
              Cancel
            </Button>
            <Button 
              onClick={updatePublicationConfidence}
              loading={updatingConfidence}
            >
              Update All Entries
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}

export default PublicationDetail