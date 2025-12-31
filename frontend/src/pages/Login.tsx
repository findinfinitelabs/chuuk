import { useState, useRef } from 'react'
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
  Divider,
  Modal,
  Checkbox,
  ScrollArea,
  Anchor,
  Group
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { IconAlertCircle, IconLanguage, IconCheck } from '@tabler/icons-react'
import axios from 'axios'
import './Login.css'

interface LoginProps {
  onLoginSuccess: () => void
}

export default function Login({ onLoginSuccess }: LoginProps) {
  const [email, setEmail] = useState('')
  const [accessCode, setAccessCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [termsOpened, { open: openTerms, close: closeTerms }] = useDisclosure(false)
  const [hasScrolledToBottom, setHasScrolledToBottom] = useState(false)
  const [agreedToTerms, setAgreedToTerms] = useState(false)
  const [agreedToPrivacy, setAgreedToPrivacy] = useState(false)
  const [agreedToAI, setAgreedToAI] = useState(false)
  const [hasAcceptedTerms, setHasAcceptedTerms] = useState(false)
  const viewport = useRef<HTMLDivElement>(null)

  const handleScroll = () => {
    if (viewport.current) {
      const { scrollTop, scrollHeight, clientHeight } = viewport.current
      // Check if user scrolled to within 20px of bottom
      if (scrollHeight - scrollTop - clientHeight < 20) {
        setHasScrolledToBottom(true)
      }
    }
  }

  const handleAcceptTerms = () => {
    if (!agreedToTerms || !agreedToPrivacy || !agreedToAI) {
      return
    }
    closeTerms()
  }

  const allAgreed = agreedToTerms && agreedToPrivacy && agreedToAI

  const checkIfUserAcceptedTerms = async (userEmail: string) => {
    if (!userEmail.trim()) return
    
    try {
      const response = await axios.post('/api/auth/check-terms', { email: userEmail })
      if (response.data.has_accepted) {
        setHasAcceptedTerms(true)
        setAgreedToTerms(true)
        setAgreedToPrivacy(true)
        setAgreedToAI(true)
      } else {
        setHasAcceptedTerms(false)
      }
    } catch (err) {
      console.error('Failed to check terms acceptance:', err)
      setHasAcceptedTerms(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const response = await axios.post('/api/auth/login', {
        email,
        access_code: accessCode,
        terms_accepted: true,
        terms_accepted_at: new Date().toISOString()
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

  return (
    <Box className="login-container">
      <Container size={420}>
        <Center mb="xl">
          <IconLanguage size={64} color="#0277bd" />
        </Center>
        
        <Title ta="center" mb="xs" size="2rem" fw={700} c="blue.9">
          Learn Chuukese
        </Title>
        
        <Text c="gray.6" size="md" ta="center" mb="xl">
          Welcome! Sign in to continue
        </Text>

        <Paper withBorder shadow="xl" p={40} radius="lg" bg="white">
          <form onSubmit={handleSubmit}>
            <Stack gap="lg">
              {error && (
                <Alert 
                  icon={<IconAlertCircle size={16} />} 
                  color="red" 
                  variant="light"
                  radius="md"
                >
                  {error}
                </Alert>
              )}

              <TextInput
                label="Email"
                placeholder="your@email.com"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onBlur={(e) => checkIfUserAcceptedTerms(e.target.value)}
                size="md"
                radius="md"
              />

              <PasswordInput
                label="Access Code"
                placeholder="Enter your access code"
                required
                value={accessCode}
                onChange={(e) => setAccessCode(e.target.value)}
                size="md"
                radius="md"
              />

              {!hasAcceptedTerms && (
                <Stack gap="sm">
                  <Checkbox
                    label={
                      <Text size="sm">
                        I agree to the{' '}
                        <Anchor component="button" type="button" onClick={openTerms}>
                          Terms of Use
                        </Anchor>
                      </Text>
                    }
                    checked={agreedToTerms}
                    onChange={(e) => setAgreedToTerms(e.currentTarget.checked)}
                    required
                  />
                  <Checkbox
                    label={
                      <Text size="sm">
                        I agree to the{' '}
                        <Anchor component="button" type="button" onClick={openTerms}>
                          Privacy Policy
                        </Anchor>
                      </Text>
                    }
                    checked={agreedToPrivacy}
                    onChange={(e) => setAgreedToPrivacy(e.currentTarget.checked)}
                    required
                  />
                  <Checkbox
                    label={
                      <Text size="sm">
                        I agree to the{' '}
                        <Anchor component="button" type="button" onClick={openTerms}>
                          AI Ethical Use Agreement
                        </Anchor>
                      </Text>
                    }
                    checked={agreedToAI}
                    onChange={(e) => setAgreedToAI(e.currentTarget.checked)}
                    required
                  />
                </Stack>
              )}

              <Button 
                type="submit" 
                fullWidth 
                mt="md" 
                size="lg"
                radius="md"
                loading={loading}
                disabled={!allAgreed}
              >
                Sign In
              </Button>
            </Stack>
          </form>
        </Paper>

        <Box mt="xl" ta="center">
          <Text size="xs" c="black">
            © {new Date().getFullYear()} FindInfinite Labs. All rights reserved.
          </Text>
          <Group justify="center" gap="xs" mt="xs">
            <Anchor size="xs" c="black" component="button" type="button" onClick={openTerms}>
              Terms of Use
            </Anchor>
            <Text size="xs" c="black">•</Text>
            <Anchor size="xs" c="black" component="button" type="button" onClick={openTerms}>
              Privacy Policy
            </Anchor>
            <Text size="xs" c="black">•</Text>
            <Anchor size="xs" c="black" component="button" type="button" onClick={openTerms}>
              AI Ethical Use
            </Anchor>
          </Group>
        </Box>
      </Container>

      {/* Terms and Conditions Modal */}
      <Modal
        opened={termsOpened}
        onClose={() => {
          if (allAgreed) {
            closeTerms()
          }
        }}
        title={<Text size="xl" fw={700}>Terms and Conditions</Text>}
        size="lg"
        closeOnClickOutside={false}
        closeOnEscape={false}
      >
        <Stack gap="md">
          <ScrollArea h={400} viewportRef={viewport} onScrollPositionChange={handleScroll}>
            <Stack gap="lg" pr="md">
              {/* Terms of Use */}
              <div>
                <Title order={3} mb="sm">Terms of Use</Title>
                <Text size="sm" mb="xs">
                  <strong>Effective Date:</strong> {new Date().toLocaleDateString()}
                </Text>
                <Text size="sm" mb="sm">
                  Welcome to Learn Chuukese. By accessing and using this platform, you agree to be bound by these Terms of Use.
                </Text>
                
                <Title order={4} size="md" mt="md" mb="xs">1. Access and Authentication</Title>
                <Text size="sm" mb="sm">
                  • Access to this platform requires a unique access key provided by FindInfinite Labs.<br />
                  • Your access key is personal and non-transferable. You may not share your access credentials with any other person or entity.<br />
                  • Unauthorized sharing of access keys will result in immediate termination of access without refund or notice.
                </Text>

                <Title order={4} size="md" mt="md" mb="xs">2. Data Usage and Protection</Title>
                <Text size="sm" mb="sm">
                  • All data, translations, dictionary entries, and content on this platform are proprietary to FindInfinite Labs.<br />
                  • You may not extract, scrape, download, or otherwise copy any data from this platform for use outside of the platform.<br />
                  • You may not use automated tools, bots, or scripts to access, extract, or interact with this platform.<br />
                  • You may not connect this platform to external services, APIs, or databases without explicit written permission.
                </Text>

                <Title order={4} size="md" mt="md" mb="xs">3. Permitted Use</Title>
                <Text size="sm" mb="sm">
                  • This platform is intended for personal language learning and cultural education purposes only.<br />
                  • You may use the translation tools, dictionary, and learning resources for your individual study.<br />
                  • Commercial use, redistribution, or republication of any content is strictly prohibited.
                </Text>

                <Title order={4} size="md" mt="md" mb="xs">4. Prohibited Activities</Title>
                <Text size="sm" mb="sm">
                  • Reverse engineering, decompiling, or attempting to derive the source code of the platform.<br />
                  • Interfering with or disrupting the platform's servers, networks, or security measures.<br />
                  • Attempting to gain unauthorized access to any systems or data.<br />
                  • Using the platform for any illegal or unauthorized purpose.
                </Text>

                <Title order={4} size="md" mt="md" mb="xs">5. Termination</Title>
                <Text size="sm" mb="sm">
                  FindInfinite Labs reserves the right to terminate or suspend your access immediately, without prior notice or liability, for any breach of these Terms.
                </Text>
              </div>

              {/* Privacy Policy */}
              <Divider />
              <div>
                <Title order={3} mb="sm">Privacy Policy</Title>
                <Text size="sm" mb="xs">
                  <strong>Effective Date:</strong> {new Date().toLocaleDateString()}
                </Text>
                
                <Title order={4} size="md" mt="md" mb="xs">1. Information We Collect</Title>
                <Text size="sm" mb="sm">
                  • Email address for authentication purposes<br />
                  • Usage data including translations, searches, and learning progress<br />
                  • Browser and device information for security and optimization<br />
                  • IP address and access logs for security monitoring
                </Text>

                <Title order={4} size="md" mt="md" mb="xs">2. How We Use Your Information</Title>
                <Text size="sm" mb="sm">
                  • To provide and maintain the platform services<br />
                  • To authenticate your identity and manage your access<br />
                  • To improve the translation algorithms and learning tools<br />
                  • To monitor and prevent unauthorized access or misuse<br />
                  • To communicate important updates about the service
                </Text>

                <Title order={4} size="md" mt="md" mb="xs">3. Data Security</Title>
                <Text size="sm" mb="sm">
                  We implement appropriate technical and organizational security measures to protect your personal information. However, no method of transmission over the Internet is 100% secure.
                </Text>

                <Title order={4} size="md" mt="md" mb="xs">4. Data Retention</Title>
                <Text size="sm" mb="sm">
                  We retain your personal information for as long as your account is active or as needed to provide services. We may retain certain information as required by law or for legitimate business purposes.
                </Text>

                <Title order={4} size="md" mt="md" mb="xs">5. Your Rights</Title>
                <Text size="sm" mb="sm">
                  You have the right to access, correct, or delete your personal information. Contact us to exercise these rights.
                </Text>

                <Title order={4} size="md" mt="md" mb="xs">6. Third-Party Services</Title>
                <Text size="sm" mb="sm">
                  This platform may use third-party services (Azure, cloud storage) to provide functionality. These services have their own privacy policies.
                </Text>
              </div>

              {/* AI Ethical and Responsible Use */}
              <Divider />
              <div>
                <Title order={3} mb="sm">AI Ethical and Responsible Use Agreement</Title>
                <Text size="sm" mb="xs">
                  <strong>Effective Date:</strong> {new Date().toLocaleDateString()}
                </Text>
                
                <Title order={4} size="md" mt="md" mb="xs">1. AI-Assisted Translations</Title>
                <Text size="sm" mb="sm">
                  • This platform uses AI and machine learning models to assist with translations between Chuukese and English.<br />
                  • AI-generated translations are provided as learning aids and may not always be perfectly accurate.<br />
                  • Users should verify important translations with native speakers or cultural experts.<br />
                  • Translation confidence scores are provided as guidance only.
                </Text>

                <Title order={4} size="md" mt="md" mb="xs">2. Cultural Sensitivity</Title>
                <Text size="sm" mb="sm">
                  • The Chuukese language and culture are precious and deserving of respect.<br />
                  • This platform aims to support language preservation and cultural understanding.<br />
                  • Users should approach the language and culture with humility and respect.<br />
                  • Sacred or culturally sensitive content should be treated with appropriate reverence.
                </Text>

                <Title order={4} size="md" mt="md" mb="xs">3. Responsible Use of AI Tools</Title>
                <Text size="sm" mb="sm">
                  • Do not rely solely on AI translations for official documents, legal matters, or critical communications.<br />
                  • Do not use this platform to generate misleading, harmful, or culturally inappropriate content.<br />
                  • Report any inappropriate or offensive AI-generated content immediately.<br />
                  • Understand that AI models have limitations and biases that we continually work to address.
                </Text>

                <Title order={4} size="md" mt="md" mb="xs">4. Community Contributions</Title>
                <Text size="sm" mb="sm">
                  • User corrections and verifications help improve the platform for everyone.<br />
                  • By contributing corrections, you grant FindInfinite Labs a license to use these improvements.<br />
                  • We acknowledge and appreciate community members who help refine translations and content.
                </Text>

                <Title order={4} size="md" mt="md" mb="xs">5. Continuous Improvement</Title>
                <Text size="sm" mb="sm">
                  • We are committed to improving translation accuracy and cultural appropriateness.<br />
                  • AI models are regularly updated based on user feedback and new data.<br />
                  • We welcome constructive feedback to make this platform better serve the Chuukese community.
                </Text>

                <Title order={4} size="md" mt="md" mb="xs">6. Accountability</Title>
                <Text size="sm" mb="sm">
                  FindInfinite Labs takes responsibility for maintaining ethical AI practices and will address concerns about AI-generated content promptly and transparently.
                </Text>
              </div>

              <Divider />
              <Text size="sm" fw={500} c="blue.7" ta="center">
                Please scroll to the bottom to accept these terms
              </Text>
            </Stack>
          </ScrollArea>

          <Checkbox
            label="I have read and agree to all the terms and conditions above"
            checked={agreedToTerms && agreedToPrivacy && agreedToAI}
            onChange={(e) => {
              const checked = e.currentTarget.checked
              setAgreedToTerms(checked)
              setAgreedToPrivacy(checked)
              setAgreedToAI(checked)
            }}
            disabled={!hasScrolledToBottom}
          />

          <Group justify="flex-end">
            <Button
              onClick={handleAcceptTerms}
              disabled={!allAgreed || !hasScrolledToBottom}
            >
              Accept and Continue
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Box>
  )
}
