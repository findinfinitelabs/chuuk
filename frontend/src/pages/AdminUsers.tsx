import { useState, useEffect } from 'react'
import { Container, Title, Paper, Table, Button, Group, TextInput, Select, Modal, Text, Badge, CopyButton, ActionIcon, Tooltip, Alert, Stack, Code } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconPlus, IconTrash, IconCopy, IconCheck, IconAlertCircle } from '@tabler/icons-react'
import axios from 'axios'

interface User {
  email: string
  name: string
  role: string
  terms_accepted?: boolean
  created_at?: string
}

interface NewUserResponse {
  success: boolean
  user: User
  access_code: string
}

export default function AdminUsers() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [userToDelete, setUserToDelete] = useState<string | null>(null)
  const [newUserEmail, setNewUserEmail] = useState('')
  const [newUserName, setNewUserName] = useState('')
  const [newUserRole, setNewUserRole] = useState<string | null>('user')
  const [creating, setCreating] = useState(false)
  const [newAccessCode, setNewAccessCode] = useState<string | null>(null)
  const [createdUserEmail, setCreatedUserEmail] = useState<string | null>(null)

  useEffect(() => {
    loadUsers()
  }, [])

  const loadUsers = async () => {
    try {
      const response = await axios.get('/api/admin/users')
      setUsers(response.data.users)
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to load users',
        color: 'red'
      })
    } finally {
      setLoading(false)
    }
  }

  const handleCreateUser = async () => {
    if (!newUserEmail.trim()) {
      notifications.show({
        title: 'Error',
        message: 'Email is required',
        color: 'red'
      })
      return
    }

    setCreating(true)
    try {
      const response = await axios.post<NewUserResponse>('/api/admin/users', {
        email: newUserEmail.trim(),
        name: newUserName.trim(),
        role: newUserRole || 'user'
      })

      // Store the access code to show to admin
      setNewAccessCode(response.data.access_code)
      setCreatedUserEmail(response.data.user.email)
      
      // Reload users list
      await loadUsers()
      
      // Clear form but keep modal open to show access code
      setNewUserEmail('')
      setNewUserName('')
      setNewUserRole('user')

      notifications.show({
        title: 'Success',
        message: `User ${response.data.user.email} created`,
        color: 'green'
      })
    } catch (error: unknown) {
      const err = error as { response?: { data?: { error?: string } } }
      notifications.show({
        title: 'Error',
        message: err.response?.data?.error || 'Failed to create user',
        color: 'red'
      })
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteUser = async () => {
    if (!userToDelete) return

    try {
      await axios.delete(`/api/admin/users/${encodeURIComponent(userToDelete)}`)
      
      notifications.show({
        title: 'Success',
        message: 'User deleted',
        color: 'green'
      })
      
      await loadUsers()
      setDeleteModalOpen(false)
      setUserToDelete(null)
    } catch (error: unknown) {
      const err = error as { response?: { data?: { error?: string } } }
      notifications.show({
        title: 'Error',
        message: err.response?.data?.error || 'Failed to delete user',
        color: 'red'
      })
    }
  }

  const closeCreateModal = () => {
    setCreateModalOpen(false)
    setNewAccessCode(null)
    setCreatedUserEmail(null)
    setNewUserEmail('')
    setNewUserName('')
    setNewUserRole('user')
  }

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case 'admin': return 'red'
      case 'translator': return 'blue'
      default: return 'gray'
    }
  }

  return (
    <Container size="lg" py="xl">
      <Group justify="space-between" mb="lg">
        <Title order={2}>User Management</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setCreateModalOpen(true)}>
          Add User
        </Button>
      </Group>

      <Paper shadow="sm" p="md" withBorder>
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Email</Table.Th>
              <Table.Th>Name</Table.Th>
              <Table.Th>Role</Table.Th>
              <Table.Th>Terms Accepted</Table.Th>
              <Table.Th>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {loading ? (
              <Table.Tr>
                <Table.Td colSpan={5}>Loading...</Table.Td>
              </Table.Tr>
            ) : users.length === 0 ? (
              <Table.Tr>
                <Table.Td colSpan={5}>No users found</Table.Td>
              </Table.Tr>
            ) : (
              users.map((user) => (
                <Table.Tr key={user.email}>
                  <Table.Td>{user.email}</Table.Td>
                  <Table.Td>{user.name}</Table.Td>
                  <Table.Td>
                    <Badge color={getRoleBadgeColor(user.role)}>{user.role}</Badge>
                  </Table.Td>
                  <Table.Td>
                    {user.terms_accepted ? (
                      <Badge color="green">Yes</Badge>
                    ) : (
                      <Badge color="gray">No</Badge>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Tooltip label="Delete user">
                      <ActionIcon
                        color="red"
                        variant="subtle"
                        onClick={() => {
                          setUserToDelete(user.email)
                          setDeleteModalOpen(true)
                        }}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Tooltip>
                  </Table.Td>
                </Table.Tr>
              ))
            )}
          </Table.Tbody>
        </Table>
      </Paper>

      {/* Create User Modal */}
      <Modal
        opened={createModalOpen}
        onClose={closeCreateModal}
        title="Add New User"
        size="md"
      >
        {newAccessCode ? (
          <Stack>
            <Alert icon={<IconCheck size={16} />} title="User Created!" color="green">
              Share the access code below with <strong>{createdUserEmail}</strong>. 
              This is the only time it will be shown.
            </Alert>
            
            <Text size="sm" fw={500}>Access Code:</Text>
            <Group>
              <Code style={{ flex: 1, padding: '10px', fontSize: '14px' }}>
                {newAccessCode}
              </Code>
              <CopyButton value={newAccessCode}>
                {({ copied, copy }) => (
                  <Tooltip label={copied ? 'Copied!' : 'Copy'}>
                    <ActionIcon color={copied ? 'green' : 'blue'} onClick={copy} size="lg">
                      {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                    </ActionIcon>
                  </Tooltip>
                )}
              </CopyButton>
            </Group>
            
            <Button onClick={closeCreateModal} mt="md">
              Done
            </Button>
          </Stack>
        ) : (
          <Stack>
            <TextInput
              label="Email"
              placeholder="user@example.com"
              value={newUserEmail}
              onChange={(e) => setNewUserEmail(e.currentTarget.value)}
              required
            />
            <TextInput
              label="Name"
              placeholder="John Doe"
              value={newUserName}
              onChange={(e) => setNewUserName(e.currentTarget.value)}
            />
            <Select
              label="Role"
              data={[
                { value: 'user', label: 'User - Basic access' },
                { value: 'translator', label: 'Translator - Database & game access' },
                { value: 'admin', label: 'Admin - Full access' }
              ]}
              value={newUserRole}
              onChange={setNewUserRole}
            />
            <Text size="xs" c="dimmed">
              An access code will be generated automatically.
            </Text>
            <Group justify="flex-end" mt="md">
              <Button variant="subtle" onClick={closeCreateModal}>
                Cancel
              </Button>
              <Button onClick={handleCreateUser} loading={creating}>
                Create User
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        opened={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false)
          setUserToDelete(null)
        }}
        title="Confirm Delete"
        size="sm"
      >
        <Stack>
          <Alert icon={<IconAlertCircle size={16} />} color="red">
            Are you sure you want to delete <strong>{userToDelete}</strong>? This action cannot be undone.
          </Alert>
          <Group justify="flex-end">
            <Button variant="subtle" onClick={() => setDeleteModalOpen(false)}>
              Cancel
            </Button>
            <Button color="red" onClick={handleDeleteUser}>
              Delete User
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  )
}
