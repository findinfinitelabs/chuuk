import { Box, Text, Group, Anchor, Modal } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { useState, useRef } from 'react'
import { Stack, ScrollArea, Divider, Checkbox, Button, Title } from '@mantine/core'

export default function Footer() {
  const [termsOpened, { open: openTerms, close: closeTerms }] = useDisclosure(false)
  const [hasScrolledToBottom, setHasScrolledToBottom] = useState(false)
  const viewport = useRef<HTMLDivElement>(null)

  const handleScroll = () => {
    if (viewport.current) {
      const { scrollTop, scrollHeight, clientHeight } = viewport.current
      if (scrollHeight - scrollTop - clientHeight < 20) {
        setHasScrolledToBottom(true)
      }
    }
  }

  return (
    <>
      <Box mt="xl" py="lg" ta="center" style={{ borderTop: '1px solid #e0e0e0' }}>
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

      {/* Terms and Conditions Modal */}
      <Modal
        opened={termsOpened}
        onClose={closeTerms}
        title={<Text size="xl" fw={700}>Terms and Conditions</Text>}
        size="lg"
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
            </Stack>
          </ScrollArea>

          <Group justify="flex-end">
            <Button onClick={closeTerms}>
              Close
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}
