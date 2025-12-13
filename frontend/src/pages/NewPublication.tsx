import { useState } from 'react'
import { Card, Title, Text, TextInput, Textarea, Button, Group, Stack } from '@mantine/core'
import { IconPlus, IconX } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { notifications } from '@mantine/notifications'

function NewPublication() {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return

    setLoading(true)
    try {
      const response = await axios.post('/api/publications', { title, description })
      notifications.show({
        title: 'Success',
        message: 'Publication created successfully',
        color: 'green',
      })
      navigate(`/publications/${response.data.id}`)
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to create publication',
        color: 'red',
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card withBorder>
      <Title order={2} mb="md">
        <IconPlus size={24} style={{ marginRight: 8 }} />
        Create New Publication
      </Title>
      <Text color="dimmed" mb="lg">
        Create a new publication to organize your dictionary pages. You can upload up to 400+ pages per publication.
      </Text>

      <form onSubmit={handleSubmit}>
        <Stack gap="md">
          <TextInput
            label="Publication Title"
            placeholder="e.g., Chuuk-English Dictionary"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            withAsterisk
          />

          <Textarea
            label="Description (Optional)"
            placeholder="Enter a description of this publication..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            minRows={3}
          />

          <Group>
            <Button type="submit" loading={loading} leftSection={<IconPlus size={16} />}>
              Create Publication
            </Button>
            <Button variant="outline" leftSection={<IconX size={16} />} onClick={() => navigate('/')}>
              Cancel
            </Button>
          </Group>
        </Stack>
      </form>
    </Card>
  )
}

export default NewPublication