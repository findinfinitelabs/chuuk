import { Routes, Route } from 'react-router-dom'
import { AppShell, NavLink, Title, Group, createTheme, MantineProvider } from '@mantine/core'
import { IconHome, IconSearch, IconBooks, IconPlus } from '@tabler/icons-react'
import Home from './pages/Home'
import Lookup from './pages/Lookup'
import Publications from './pages/Publications'
import NewPublication from './pages/NewPublication'
import PublicationDetail from './pages/PublicationDetail'
import './App.css'

// Chuukese-themed color scheme
const chuukTheme = createTheme({
  primaryColor: 'ocean',
  colors: {
    ocean: [
      '#e6f6ff',
      '#b3e5ff',
      '#80d4ff',
      '#4dc3ff',
      '#1ab2ff',
      '#00a1ff',
      '#0090e6',
      '#0080cc',
      '#006fb3',
      '#005e99'
    ],
    coral: [
      '#fff0e6',
      '#ffe0cc',
      '#ffcfb3',
      '#ffbf99',
      '#ffaf80',
      '#ff9f66',
      '#e68f5c',
      '#cc7f52',
      '#b36f47',
      '#995f3d'
    ]
  },
  fontFamily: '"Noto Sans", "Arial Unicode MS", system-ui, sans-serif',
})

function App() {
  return (
    <MantineProvider theme={chuukTheme}>
      <AppShell
        padding="md"
        navbar={{
          width: 300,
          breakpoint: 'sm',
        }}
        header={{
          height: 60,
        }}
        styles={{
          header: {
            backgroundColor: 'var(--mantine-color-ocean-6)',
            color: 'white'
          },
          navbar: {
            backgroundColor: 'var(--mantine-color-gray-0)'
          }
        }}
      >
        <AppShell.Navbar p="md">
          <AppShell.Section grow>
            <Title order={4} mb="md" c="ocean.7">Navigation</Title>
            <NavLink 
              label="Home" 
              leftSection={<IconHome size="1.2rem" />} 
              component="a" 
              href="/"
              styles={{ label: { fontWeight: 500 } }}
            />
            <NavLink 
              label="Word Lookup" 
              leftSection={<IconSearch size="1.2rem" />} 
              component="a" 
              href="/lookup"
              styles={{ label: { fontWeight: 500 } }}
            />
            <NavLink 
              label="Publications" 
              leftSection={<IconBooks size="1.2rem" />} 
              component="a" 
              href="/publications"
              styles={{ label: { fontWeight: 500 } }}
            />
            <NavLink 
              label="New Publication" 
              leftSection={<IconPlus size="1.2rem" />} 
              component="a" 
              href="/publications/new"
              styles={{ label: { fontWeight: 500 } }}
            />
          </AppShell.Section>
        </AppShell.Navbar>

        <AppShell.Header p="md">
          <Group justify="space-between" h="100%">
            <Title order={2} c="white">🏝️ Chuuk Dictionary OCR</Title>
            <Group gap="sm">
              <Title order={6} c="white" style={{ opacity: 0.9 }}>
                Chuukese Language Tools
              </Title>
            </Group>
          </Group>
        </AppShell.Header>

        <AppShell.Main bg="gray.0">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/lookup" element={<Lookup />} />
            <Route path="/publications" element={<Publications />} />
            <Route path="/publications/new" element={<NewPublication />} />
            <Route path="/publications/:id" element={<PublicationDetail />} />
          </Routes>
        </AppShell.Main>
      </AppShell>
    </MantineProvider>
  )
}

export default App
