import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { AppShell, NavLink, Title, Group } from '@mantine/core'
import { IconHome, IconSearch, IconBooks, IconPlus, IconDatabase, IconLanguage } from '@tabler/icons-react'
import Home from './pages/Home'
import Lookup from './pages/Lookup'
import Publications from './pages/Publications'
import NewPublication from './pages/NewPublication'
import PublicationDetail from './pages/PublicationDetail'
import Database from './pages/Database'
import Translate from './pages/Translate'

function App() {
  const location = useLocation()

  return (
    <AppShell
      padding="md"
      navbar={{
        width: 300,
        breakpoint: 'sm',
      }}
      header={{
        height: 60,
      }}
    >
      <AppShell.Navbar p="xs">
        <AppShell.Section grow>
          <NavLink label="Home" leftSection={<IconHome size="1rem" />} component={Link} to="/" active={location.pathname === '/'} />
          <NavLink label="Word Lookup" leftSection={<IconSearch size="1rem" />} component={Link} to="/lookup" active={location.pathname === '/lookup'} />
          <NavLink label="Database" leftSection={<IconDatabase size="1rem" />} component={Link} to="/database" active={location.pathname === '/database'} />
          <NavLink label="Translate" leftSection={<IconLanguage size="1rem" />} component={Link} to="/translate" active={location.pathname === '/translate'} />
          <NavLink label="Publications" leftSection={<IconBooks size="1rem" />} component={Link} to="/publications" active={location.pathname === '/publications'} />
          <NavLink label="New Publication" leftSection={<IconPlus size="1rem" />} component={Link} to="/publications/new" active={location.pathname === '/publications/new'} />
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Header p="xs">
        <Group justify="space-between" h="100%">
          <Title order={3}>Chuuk Dictionary AI Copilot</Title>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/lookup" element={<Lookup />} />
          <Route path="/database" element={<Database />} />
          <Route path="/translate" element={<Translate />} />
          <Route path="/publications" element={<Publications />} />
          <Route path="/publications/new" element={<NewPublication />} />
          <Route path="/publications/:id" element={<PublicationDetail />} />
        </Routes>
      </AppShell.Main>
    </AppShell>
  )
}

export default App
