import { Routes, Route } from 'react-router-dom'
import { AppShell, NavLink, Title, Group } from '@mantine/core'
import { IconHome, IconSearch, IconBooks, IconPlus } from '@tabler/icons-react'
import Home from './pages/Home'
import Lookup from './pages/Lookup'
import Publications from './pages/Publications'
import NewPublication from './pages/NewPublication'
import PublicationDetail from './pages/PublicationDetail'

function App() {
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
          <NavLink label="Home" leftSection={<IconHome size="1rem" />} component="a" href="/" />
          <NavLink label="Word Lookup" leftSection={<IconSearch size="1rem" />} component="a" href="/lookup" />
          <NavLink label="Publications" leftSection={<IconBooks size="1rem" />} component="a" href="/publications" />
          <NavLink label="New Publication" leftSection={<IconPlus size="1rem" />} component="a" href="/publications/new" />
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Header p="xs">
        <Group justify="space-between" h="100%">
          <Title order={3}>Chuuk Dictionary OCR</Title>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/lookup" element={<Lookup />} />
          <Route path="/publications" element={<Publications />} />
          <Route path="/publications/new" element={<NewPublication />} />
          <Route path="/publications/:id" element={<PublicationDetail />} />
        </Routes>
      </AppShell.Main>
    </AppShell>
  )
}

export default App
