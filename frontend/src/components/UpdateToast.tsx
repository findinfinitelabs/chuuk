/**
 * UpdateToast.tsx
 * Purpose: notice when the server has been deployed with a newer version than
 * the one this page was built from, and offer a refresh that saves the
 * person's unsaved work first and reloads to the same place. The session is
 * kept on the server, so no new login is needed.
 */

import { useEffect, useRef } from 'react'
import { Anchor, Button, Group, Text } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconRefresh } from '@tabler/icons-react'
import { Link } from 'react-router-dom'
import axios from 'axios'
import { CURRENT_VERSION } from '../pages/ReleaseNotes'
import { saveAndReload } from '../refresh'

const TOAST_ID = 'new-version'
const POLL_MS = 60_000

interface Version { version: string; title?: string; date?: string }

export default function UpdateToast() {
  const shown = useRef(false)

  useEffect(() => {
    let cancelled = false
    const check = async () => {
      try {
        const { data } = await axios.get<Version>('/api/version', { params: { t: Date.now() } })
        if (cancelled || !data.version || data.version === CURRENT_VERSION || shown.current) return
        shown.current = true
        notifications.show({
          id: TOAST_ID,
          title: `Version ${data.version} is ready`,
          color: 'violet',
          autoClose: false,
          withCloseButton: true,
          message: (
            <div>
              <Text size="sm">{data.title || 'The site has been updated.'} Refresh to use it. Your unsaved work is saved first and you stay signed in.</Text>
              <Group gap="xs" mt="xs">
                <Button size="xs" leftSection={<IconRefresh size={14} />} onClick={() => { notifications.update({ id: TOAST_ID, loading: true, message: 'Saving your work…', withCloseButton: false }); saveAndReload() }}>Save and refresh</Button>
                <Anchor size="xs" component={Link} to="/release-notes">What changed</Anchor>
              </Group>
            </div>
          ),
        })
      } catch { /* offline or restarting: try again later */ }
    }
    check()
    const timer = window.setInterval(check, POLL_MS)
    const onFocus = () => { if (document.visibilityState === 'visible') check() }
    document.addEventListener('visibilitychange', onFocus)
    window.addEventListener('focus', onFocus)
    return () => { cancelled = true; window.clearInterval(timer); document.removeEventListener('visibilitychange', onFocus); window.removeEventListener('focus', onFocus) }
  }, [])

  return null
}
