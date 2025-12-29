import { useState } from 'react'
import {
  Container,
  Paper,
  Title,
  TextInput,
  PasswordInput,
  Button,
  Stack,
  Text,
  Alert,
  Center,
  Box,
  Divider
} from '@mantine/core'
import { IconAlertCircle, IconBook, IconMail, IconCheck } from '@tabler/icons-react'
import axios from 'axios'

interface LoginProps {
  onLoginSuccess: () => void
}

export default function Login({ onLoginSuccess }: LoginProps) {
  const [email, setEmail] = useState('')
  const [accessCode, setAccessCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [magicLinkLoading, setMagicLinkLoading] = useState(false)
  const [error, setError] = useState('')
  const [magicLinkSent, setMagicLinkSent] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const response = await axios.post('/api/auth/login', {
        email,
        access_code: accessCode
      })

      if (response.data.success) {
        onLoginSuccess()
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Login failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleMagicLink = async () => {
    if (!email.trim()) {
      setError('Please enter your email address first')
      return
    }
    
    setMagicLinkLoading(true)
    setError('')
    setMagicLinkSent(false)

    try {
      const response = await axios.post('/api/auth/request-magic-link', { email })
      if (response.data.success) {
        setMagicLinkSent(true)
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to send login link. Please try again.')
    } finally {
      setMagicLinkLoading(false)
    }
  }

  return (
    <Box
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #1a1b1e 0%, #25262b 100%)'
      }}
    >
      <Container size={420}>
        <Center mb="xl">
          <IconBook size={48} color="#228be6" />
        </Center>
        
        <Title ta="center" mb="xs" c="white">
          Chuuk Dictionary
        </Title>
        
        <Text c="dimmed" size="sm" ta="center" mb="xl">
          Enter your credentials to access the application
        </Text>

        <Paper withBorder shadow="md" p={30} radius="md" bg="dark.6">
          <form onSubmit={handleSubmit}>
            <Stack>
              {error && (
                <Alert 
                  icon={<IconAlertCircle size={16} />} 
                  color="red" 
                  variant="filled"
                >
                  {error}
                </Alert>
              )}
              
              {magicLinkSent && (
                <Alert 
                  icon={<IconCheck size={16} />} 
                  color="green" 
                  variant="filled"
                >
                  Login link sent! Check your email.
                </Alert>
              )}

              <TextInput
                label="Email"
                placeholder="your@email.com"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                size="md"
                styles={{ label: { color: 'white' } }}
              />

              <PasswordInput
                label="Access Code"
                placeholder="Enter your access code"
                required
                value={accessCode}
                onChange={(e) => setAccessCode(e.target.value)}
                size="md"
                styles={{ label: { color: 'white' } }}
              />

              <Button 
                type="submit" 
                fullWidth 
                mt="md" 
                size="md"
                loading={loading}
              >
                Sign In
              </Button>
              
              <Divider label={<Text size="xs" c="dimmed">or</Text>} labelPosition="center" my="sm" />
              
              <Button 
                variant="outline"
                fullWidth 
                size="md"
                loading={magicLinkLoading}
                onClick={handleMagicLink}
                leftSection={<IconMail size={16} />}
              >
                Send Login Link to Email
              </Button>
            </Stack>
          </form>
        </Paper>

        <Text c="dimmed" size="xs" ta="center" mt="xl">
          Contact your administrator if you need access
        </Text>
      </Container>
    </Box>
  )
}
