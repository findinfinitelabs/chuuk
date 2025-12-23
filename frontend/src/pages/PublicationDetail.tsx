import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Title, Text, Button, Group, Stack, Grid, Badge, Loader, Alert, Select, Checkbox, Progress } from '@mantine/core'
import { IconUpload, IconFileText, IconAlertCircle, IconEye, IconCheck } from '@tabler/icons-react'
import { Dropzone, MIME_TYPES } from '@mantine/dropzone'
import { notifications } from '@mantine/notifications'
import axios from 'axios'

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
      formData.append('ocr', aiEnabled.toString())
      formData.append('lang', aiLanguage)
      formData.append('index_dictionary', indexDictionary.toString())

      try {
        progressMap[i].status = 'uploading'
        setUploadProgress([...progressMap])

        await axios.post(`/api/publications/${id}/upload`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (progressEvent) => {
            const percentCompleted = progressEvent.total
              ? Math.round((progressEvent.loaded * 100) / progressEvent.total)
              : 0
            progressMap[i].progress = percentCompleted
            setUploadProgress([...progressMap])
          }
        })

        progressMap[i].status = 'complete'
        progressMap[i].progress = 100
        setUploadProgress([...progressMap])

        notifications.show({
          title: 'Success',
          message: `${file.name} uploaded successfully`,
          color: 'green'
        })
      } catch (err) {
        progressMap[i].status = 'error'
        setUploadProgress([...progressMap])
        notifications.show({
          title: 'Upload Failed',
          message: `Failed to upload ${file.name}`,
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
        </Stack>

        <Dropzone
          onDrop={handleUpload}
          accept={[MIME_TYPES.png, MIME_TYPES.jpeg, MIME_TYPES.pdf, MIME_TYPES.docx, 'image/*']}
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
                Drag images here or click to select files
              </Text>
              <Text size="sm" color="dimmed" inline mt={7}>
                Attach as many files as you like (PNG, JPG, PDF, DOCX supported)
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
    </Stack>
  )
}

export default PublicationDetail