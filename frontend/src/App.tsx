import { Routes, Route } from 'react-router-dom'
import { AppShell, NavLink, Title, Group, createTheme, MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { IconHome, IconSearch, IconBooks, IconPlus, IconDatabase, IconLanguage } from '@tabler/icons-react'
import Home from './pages/Home'
import Lookup from './pages/Lookup'
import Publications from './pages/Publications'
import NewPublication from './pages/NewPublication'
import PublicationDetail from './pages/PublicationDetail'
import Database from './pages/Database'
import Translate from './pages/Translate'
import './App.css'

// Modern violet theme with improved typography (#4F23C0)
const chuukTheme = createTheme({
  primaryColor: 'violet',
  colors: {
    violet: [
      '#f3edff',
      '#e0d7fa',
      '#beabf0',
      '#9a7de6',
      '#7c55de',
      '#693cd9',
      '#5f30d8',
      '#4f23c0',
      '#461eac',
      '#3b1898'
    ],
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
  },
  primaryShade: { light: 6, dark: 8 },
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Sans Emoji"',
  fontFamilyMonospace: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
  headings: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    fontWeight: '700',
    sizes: {
      h1: { fontSize: '2.125rem', lineHeight: '1.3', fontWeight: '700' },
      h2: { fontSize: '1.625rem', lineHeight: '1.35', fontWeight: '700' },
      h3: { fontSize: '1.375rem', lineHeight: '1.4', fontWeight: '600' },
      h4: { fontSize: '1.125rem', lineHeight: '1.45', fontWeight: '600' },
      h5: { fontSize: '1rem', lineHeight: '1.5', fontWeight: '600' },
      h6: { fontSize: '0.875rem', lineHeight: '1.5', fontWeight: '600' },
    },
  },
  defaultRadius: 'md',
  cursorType: 'pointer',
  autoContrast: true,
  luminanceThreshold: 0.3,
})

function App() {
  return (
    <MantineProvider theme={chuukTheme}>
      <Notifications />
      <AppShell
        padding="md"
        navbar={{
          width: 300,
          breakpoint: 'sm',
        }}
        header={{
          height: 70,
        }}
        styles={{
          header: {
            backgroundColor: 'var(--mantine-color-violet-9)',
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
              label="AI Translation" 
              leftSection={<IconLanguage size="1.2rem" />} 
              component="a" 
              href="/translate"
              styles={{ label: { fontWeight: 500 } }}
            />
            <NavLink 
              label="Database" 
              leftSection={<IconDatabase size="1.2rem" />} 
              component="a" 
              href="/database"
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
            <Title order={1} size="h2" fw={900} c="white">🏝️ Chuuk AI Language Dictionary</Title>
            <Group gap="sm">
              <Title order={6} fw={600} c="white" className="header-subtitle">
                Chuukese Language Tools
              </Title>
            </Group>
          </Group>
        </AppShell.Header>

        <AppShell.Main bg="gray.0">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/lookup" element={<Lookup />} />
            <Route path="/translate" element={<Translate />} />
            <Route path="/database" element={<Database />} />
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
