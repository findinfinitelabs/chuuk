import { Routes, Route, Link, useLocation, Navigate, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { AppShell, NavLink, Title, Group, MantineProvider, Burger, TextInput } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { Notifications } from '@mantine/notifications'
import { IconHome, IconSearch, IconBooks, IconPlus, IconDatabase, IconLanguage, IconPuzzle } from '@tabler/icons-react'
import Home from './pages/Home'
import Lookup from './pages/Lookup'
import Publications from './pages/Publications'
import NewPublication from './pages/NewPublication'
import PublicationDetail from './pages/PublicationDetail'
import Database from './pages/Database'
import Translate from './pages/Translate'
import TranslationGame from './pages/TranslationGame'
import { chuukTheme } from './theme'
import './App.css'

function App() {
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileOpened, { toggle: toggleMobile }] = useDisclosure()
  const [globalSearch, setGlobalSearch] = useState('')
  
  const handleGlobalSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && globalSearch.trim()) {
      navigate(`/lookup?q=${encodeURIComponent(globalSearch.trim())}`)
      setGlobalSearch('')
    }
  }
  
  return (
    <MantineProvider theme={chuukTheme}>
      <Notifications />
      <AppShell
        padding="md"
        navbar={{
          width: 300,
          breakpoint: 'sm',
          collapsed: { mobile: !mobileOpened },
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
              onClick={toggleMobile}
            />
            <NavLink 
              label="Word Lookup" 
              leftSection={<IconSearch size="1.2rem" />} 
              component={Link}
              to="/lookup"
              active={location.pathname === '/lookup'}
              className="nav-link"
              onClick={toggleMobile}
            />
            <NavLink 
              label="AI Translation" 
              leftSection={<IconLanguage size="1.2rem" />} 
              component={Link}
              to="/translate"
              active={location.pathname === '/translate'}
              className="nav-link"
              onClick={toggleMobile}
            />
            <NavLink 
              label="Translation Game" 
              leftSection={<IconPuzzle size="1.2rem" />} 
              component={Link}
              to="/game"
              active={location.pathname === '/game'}
              className="nav-link"
              onClick={toggleMobile}
            />
            <NavLink 
              label="Publications" 
              leftSection={<IconBooks size="1.2rem" />} 
              component={Link}
              to="/publications"
              active={location.pathname === '/publications'}
              className="nav-link"
              onClick={toggleMobile}
            />
            <NavLink 
              label="New Publication" 
              leftSection={<IconPlus size="1.2rem" />} 
              component={Link}
              to="/publications/new"
              active={location.pathname === '/publications/new'}
              className="nav-link"
              onClick={toggleMobile}
            />
            <NavLink 
              label="Database" 
              leftSection={<IconDatabase size="1.2rem" />} 
              component={Link}
              to="/database"
              active={location.pathname === '/database'}
              className="nav-link"
              onClick={toggleMobile}
            />
          </AppShell.Section>
        </AppShell.Navbar>

        <AppShell.Header p="md">
          <Group justify="space-between" h="100%">
            <Group>
              <Burger
                opened={mobileOpened}
                onClick={toggleMobile}
                hiddenFrom="sm"
                size="sm"
                color="white"
              />
              <Title order={1} className="app-title">Chuuk Dictionary AI Copilot</Title>
            </Group>
            <TextInput
              placeholder="Search site..."
              leftSection={<IconSearch size={16} />}
              value={globalSearch}
              onChange={(e) => setGlobalSearch(e.target.value)}
              onKeyDown={handleGlobalSearch}
              style={{ width: '250px' }}
              styles={{
                input: {
                  backgroundColor: 'rgba(255, 255, 255, 0.1)',
                  color: 'white',
                  borderColor: 'rgba(255, 255, 255, 0.3)',
                  '&::placeholder': {
                    color: 'rgba(255, 255, 255, 0.6)'
                  }
                }
              }}
            />
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
            <Route path="/game" element={<TranslationGame />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AppShell.Main>
      </AppShell>
    </MantineProvider>
  )
}

export default App
