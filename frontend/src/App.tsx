import { Routes, Route, Link, useLocation, Navigate } from 'react-router-dom'
import { AppShell, NavLink, Title, Group, MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { IconHome, IconSearch, IconBooks, IconPlus, IconDatabase, IconLanguage } from '@tabler/icons-react'
import Home from './pages/Home'
import Lookup from './pages/Lookup'
import Publications from './pages/Publications'
import NewPublication from './pages/NewPublication'
import PublicationDetail from './pages/PublicationDetail'
import Database from './pages/Database'
import Translate from './pages/Translate'
import { chuukTheme } from './theme'
import './App.css'

function App() {
  const location = useLocation()
  
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
        classNames={{
          header: 'app-header',
          navbar: 'app-navbar'
        }}
      >
        <AppShell.Navbar p="md">
          <AppShell.Section grow>
            <Title order={4} mb="md" className="nav-title">Navigation</Title>
            <NavLink 
              label="Home" 
              leftSection={<IconHome size="1.2rem" />} 
              component={Link}
              to="/"
              active={location.pathname === '/'}
              className="nav-link"
            />
            <NavLink 
              label="Word Lookup" 
              leftSection={<IconSearch size="1.2rem" />} 
              component={Link}
              to="/lookup"
              active={location.pathname === '/lookup'}
              className="nav-link"
            />
            <NavLink 
              label="AI Translation" 
              leftSection={<IconLanguage size="1.2rem" />} 
              component={Link}
              to="/translate"
              active={location.pathname === '/translate'}
              className="nav-link"
            />
            <NavLink 
              label="Database" 
              leftSection={<IconDatabase size="1.2rem" />} 
              component={Link}
              to="/database"
              active={location.pathname === '/database'}
              className="nav-link"
            />
            <NavLink 
              label="Publications" 
              leftSection={<IconBooks size="1.2rem" />} 
              component={Link}
              to="/publications"
              active={location.pathname === '/publications'}
              className="nav-link"
            />
            <NavLink 
              label="New Publication" 
              leftSection={<IconPlus size="1.2rem" />} 
              component={Link}
              to="/publications/new"
              active={location.pathname === '/publications/new'}
              className="nav-link"
            />
          </AppShell.Section>
        </AppShell.Navbar>

        <AppShell.Header p="md">
          <Group justify="space-between" h="100%">
            <Title order={1} className="app-title">🏝️ Chuuk Dictionary AI Copilot</Title>
            <Group gap="sm">
              <Title order={6} className="header-subtitle">
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
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AppShell.Main>
      </AppShell>
    </MantineProvider>
  )
}

export default App
