import { Routes, Route, Link, useLocation, Navigate, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { AppShell, NavLink, Title, Group, MantineProvider, Burger, TextInput, Menu, Button, Avatar, Text, Container, Alert, Divider } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { Notifications } from '@mantine/notifications'
import { IconHome, IconSearch, IconBooks, IconDatabase, IconLanguage, IconPuzzle, IconLogout, IconUser, IconLock, IconAbc } from '@tabler/icons-react'
import axios from 'axios'
import Home from './pages/Home'
import Lookup from './pages/Lookup'
import Publications from './pages/Publications'
import NewPublication from './pages/NewPublication'
import PublicationDetail from './pages/PublicationDetail'
import Database from './pages/Database'
import Translate from './pages/Translate'
import TranslationGame from './pages/TranslationGame'
import Grammar from './pages/Grammar'
import Login from './pages/Login'
import Footer from './components/Footer'
import { chuukTheme } from './theme'
import { UserContext } from './contexts/UserContext'
import './App.css'

interface User {
  email: string
  name: string
  role: string
}

// Access denied component
function AccessDenied() {
  return (
    <Container size="sm" py="xl">
      <Alert icon={<IconLock size={16} />} title="Access Denied" color="red">
        You don't have permission to access this page. Please contact an administrator if you believe this is an error.
      </Alert>
    </Container>
  )
}

function App() {
  const location = useLocation()
  const navigate = useNavigate()
  const [navOpened, { toggle: toggleNav }] = useDisclosure()
  const [globalSearch, setGlobalSearch] = useState('')
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [permissions, setPermissions] = useState<string[]>([])
  const [showHighlights, setShowHighlights] = useState(false)
  
  // Show highlights on home page, hide after interaction
  useEffect(() => {
    if (location.pathname === '/') {
      setShowHighlights(true)
      // Auto-hide after 5 seconds
      const timer = setTimeout(() => setShowHighlights(false), 5000)
      return () => clearTimeout(timer)
    } else {
      setShowHighlights(false)
    }
  }, [location.pathname])
  
  // Check authentication status on mount
  useEffect(() => {
    checkAuthStatus()
    
    // Check for error params from magic link
    const params = new URLSearchParams(window.location.search)
    const error = params.get('error')
    if (error) {
      // Could show notification here
      console.log('Auth error:', error)
      navigate('/', { replace: true })
    }
  }, [])
  
  const checkAuthStatus = async () => {
    try {
      const response = await axios.get('/api/auth/status')
      if (response.data.authenticated) {
        setIsAuthenticated(true)
        setUser(response.data.user)
        setPermissions(response.data.permissions || [])
      } else {
        setIsAuthenticated(false)
        setUser(null)
        setPermissions([])
        // Check if session was invalidated (logged in elsewhere)
        if (response.data.error) {
          console.log('Session invalidated:', response.data.error)
        }
      }
    } catch {
      setIsAuthenticated(false)
      setUser(null)
      setPermissions([])
    }
  }
  
  const hasPermission = (permission: string) => permissions.includes(permission)
  
  const handleLoginSuccess = () => {
    checkAuthStatus()
    navigate('/')
  }
  
  const handleLogout = async () => {
    try {
      await axios.post('/api/auth/logout')
      setIsAuthenticated(false)
      setUser(null)
    } catch (error) {
      console.error('Logout failed:', error)
    }
  }
  
  const handleGlobalSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && globalSearch.trim()) {
      navigate(`/lookup?q=${encodeURIComponent(globalSearch.trim())}`)
      setGlobalSearch('')
    }
  }
  
  // Show loading while checking auth
  if (isAuthenticated === null) {
    return (
      <MantineProvider theme={chuukTheme}>
        <div style={{ 
          minHeight: '100vh', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          background: '#1a1b1e'
        }}>
          <Text c="white">Loading...</Text>
        </div>
      </MantineProvider>
    )
  }
  
  // Show login page if not authenticated
  if (!isAuthenticated) {
    return (
      <MantineProvider theme={chuukTheme}>
        <Notifications />
        <Login onLoginSuccess={handleLoginSuccess} />
      </MantineProvider>
    )
  }
  
  return (
    <MantineProvider theme={chuukTheme}>
      <Notifications />
      <AppShell
        padding="md"
        navbar={{
          width: 300,
          breakpoint: 'sm',
          collapsed: { mobile: !navOpened, desktop: !navOpened },
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
            {hasPermission('home') && (
              <NavLink 
                label="Home" 
                leftSection={<IconHome size="1.2rem" />} 
                component={Link}
                to="/"
                active={location.pathname === '/'}
                className="nav-link"
                onClick={() => { toggleNav(); setShowHighlights(false); }}
              />
            )}
            {hasPermission('translate') && (
              <NavLink 
                label="AI Translation" 
                leftSection={<IconLanguage size="1.2rem" />} 
                component={Link}
                to="/translate"
                active={location.pathname === '/translate'}
                className="nav-link"
                onClick={toggleNav}
              />
            )}
            {hasPermission('grammar') && (
              <NavLink 
                label="Grammar" 
                leftSection={<IconAbc size="1.2rem" />} 
                component={Link}
                to="/grammar"
                active={location.pathname === '/grammar'}
                className="nav-link"
                onClick={toggleNav}
              />
            )}
            {hasPermission('lookup') && (
              <NavLink 
                label="Word Lookup" 
                leftSection={<IconSearch size="1.2rem" />} 
                component={Link}
                to="/lookup"
                active={location.pathname === '/lookup'}
                className="nav-link"
                onClick={toggleNav}
              />
            )}
            
            <Divider my="sm" />
            
            {hasPermission('database') && (
              <NavLink 
                label="Database" 
                leftSection={<IconDatabase size="1.2rem" />} 
                component={Link}
                to="/database"
                active={location.pathname === '/database'}
                className="nav-link"
                onClick={toggleNav}
              />
            )}
            {hasPermission('publications') && (
              <NavLink 
                label="Publications" 
                leftSection={<IconBooks size="1.2rem" />} 
                component={Link}
                to="/publications"
                active={location.pathname === '/publications'}
                className="nav-link"
                onClick={toggleNav}
              />
            )}
            {hasPermission('game') && (
              <NavLink 
                label="Translation Game" 
                leftSection={<IconPuzzle size="1.2rem" />} 
                component={Link}
                to="/game"
                active={location.pathname === '/game'}
                className="nav-link"
                onClick={toggleNav}
              />
            )}
          </AppShell.Section>
        </AppShell.Navbar>

        <AppShell.Header p="md">
          <Group justify="space-between" h="100%">
            <Group>
              <Burger
                opened={navOpened}
                onClick={() => { toggleNav(); setShowHighlights(false); }}
                size="sm"
                color="white"
                className={showHighlights ? 'highlight-burger' : ''}
              />
              <Title order={1} className="app-title">Chuuk Dictionary AI Copilot</Title>
            </Group>
            <Group>
              <TextInput
                placeholder="Search site..."
                leftSection={<IconSearch size={16} />}
                value={globalSearch}
                onChange={(e) => setGlobalSearch(e.target.value)}
                onKeyDown={handleGlobalSearch}
                onFocus={() => setShowHighlights(false)}
                style={{ width: '250px' }}
                className={showHighlights ? 'highlight-element' : ''}
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
              <Menu shadow="md" width={200}>
                <Menu.Target>
                  <Button variant="subtle" color="gray" leftSection={<Avatar size="sm" color="blue"><IconUser size={16} /></Avatar>}>
                    <Text size="sm" c="white">{user?.name || 'User'}</Text>
                  </Button>
                </Menu.Target>
                <Menu.Dropdown>
                  <Menu.Label>{user?.email}</Menu.Label>
                  <Menu.Divider />
                  <Menu.Item 
                    leftSection={<IconLogout size={14} />}
                    onClick={handleLogout}
                    color="red"
                  >
                    Logout
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            </Group>
          </Group>
        </AppShell.Header>

        <AppShell.Main bg="gray.0">
          <UserContext.Provider value={{ email: user?.email || null, name: user?.name || null, role: user?.role || null }}>
            <Routes>
              <Route path="/" element={hasPermission('home') ? <Home /> : <AccessDenied />} />
              <Route path="/lookup" element={hasPermission('lookup') ? <Lookup /> : <AccessDenied />} />
              <Route path="/translate" element={hasPermission('translate') ? <Translate /> : <AccessDenied />} />
              <Route path="/database" element={hasPermission('database') ? <Database /> : <AccessDenied />} />
              <Route path="/publications" element={hasPermission('publications') ? <Publications /> : <AccessDenied />} />
              <Route path="/publications/new" element={hasPermission('new_publication') ? <NewPublication /> : <AccessDenied />} />
              <Route path="/publications/:id" element={hasPermission('publications') ? <PublicationDetail /> : <AccessDenied />} />
              <Route path="/game" element={hasPermission('game') ? <TranslationGame /> : <AccessDenied />} />
              <Route path="/grammar" element={hasPermission('grammar') ? <Grammar /> : <AccessDenied />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </UserContext.Provider>
          <Footer />
        </AppShell.Main>
      </AppShell>
    </MantineProvider>
  )
}

export default App
