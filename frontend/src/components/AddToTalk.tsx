/**
 * AddToTalk.tsx
 * Purpose: the "Add to talk" button dropped into pages where good sentences
 * turn up (Watchtower Library, Article and Sentence Analysis, Conversation
 * Builder). Opens a small popover: pick one of your talks and the outline
 * point the line belongs under; the line is appended with its source.
 */

import { useEffect, useState } from 'react'
import { ActionIcon, Button, Group, Loader, Popover, Select, Stack, Text, Tooltip } from '@mantine/core'
import { IconCheck, IconPresentation } from '@tabler/icons-react'
import axios from 'axios'

interface TalkMeta { id: string; title: string }
interface OutlinePoint { id: string; label: string; text: string; children?: OutlinePoint[] }

export interface AddToTalkProps {
  chk: string
  en?: string
  source: string
  /** Where it came from, shown on the talk (citation, URL, article title). */
  reference?: string
  size?: 'xs' | 'sm' | 'md'
  variant?: 'icon' | 'button'
}

let talksCache: TalkMeta[] | null = null
let lastTalk: string | null = null

export default function AddToTalk({ chk, en = '', source, reference = '', size = 'sm', variant = 'icon' }: AddToTalkProps) {
  const [opened, setOpened] = useState(false)
  const [talks, setTalks] = useState<TalkMeta[] | null>(talksCache)
  const [talkId, setTalkId] = useState<string | null>(lastTalk)
  const [points, setPoints] = useState<{ value: string; label: string }[]>([])
  const [pointId, setPointId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (!opened || talks) return
    axios.get<TalkMeta[]>('/api/talks').then((r) => { talksCache = r.data; setTalks(r.data); if (!talkId && r.data[0]) setTalkId(r.data[0].id) }).catch(() => setTalks([]))
  }, [opened, talks, talkId])

  useEffect(() => {
    if (!talkId) return
    lastTalk = talkId
    axios.get(`/api/talks/${talkId}`).then((r) => {
      const rows: { value: string; label: string }[] = [{ value: 'unsorted', label: '— Unsorted (decide later)' }]
      for (const p of (r.data.outline?.points || []) as OutlinePoint[]) {
        rows.push({ value: p.id, label: `${p.label ? p.label + '. ' : ''}${p.text}`.slice(0, 80) })
        for (const c of p.children || []) rows.push({ value: c.id, label: `    ${c.label ? c.label + '. ' : '· '}${c.text}`.slice(0, 80) })
      }
      setPoints(rows)
      setPointId((cur) => (cur && rows.some((x) => x.value === cur) ? cur : 'unsorted'))
    }).catch(() => setPoints([]))
  }, [talkId])

  const add = async () => {
    if (!talkId) return
    setBusy(true)
    try {
      await axios.post(`/api/talks/${talkId}/lines`, { point_id: pointId || 'unsorted', chk, en, source, ref: reference })
      setDone(true)
      setTimeout(() => { setDone(false); setOpened(false) }, 900)
    } finally {
      setBusy(false)
    }
  }

  const trigger = variant === 'button'
    ? <Button size={size} variant="light" color="violet" leftSection={<IconPresentation size={16} />} onClick={() => setOpened((o) => !o)}>Add to talk</Button>
    : <Tooltip label="Add to a talk"><ActionIcon size={size} variant="subtle" color="violet" onClick={(e) => { e.stopPropagation(); setOpened((o) => !o) }}><IconPresentation size={16} /></ActionIcon></Tooltip>

  return (
    <Popover opened={opened} onChange={setOpened} width={340} position="bottom-end" shadow="md" withArrow>
      <Popover.Target>{trigger}</Popover.Target>
      <Popover.Dropdown onClick={(e) => e.stopPropagation()}>
        <Stack gap="xs">
          <Text size="sm" fw={600} lineClamp={2}>{chk || en}</Text>
          {talks === null ? <Loader size="sm" /> : talks.length === 0 ? (
            <Text size="sm" c="dimmed">No talks yet. Create one on the Talk Builder page first.</Text>
          ) : (
            <>
              <Select label="Talk" data={talks.map((t) => ({ value: t.id, label: t.title }))} value={talkId} onChange={setTalkId} allowDeselect={false} searchable />
              <Select label="Under point" data={points} value={pointId} onChange={setPointId} allowDeselect={false} searchable />
              <Group justify="flex-end">
                <Button size="xs" onClick={add} loading={busy} color={done ? 'green' : 'violet'} leftSection={done ? <IconCheck size={14} /> : undefined}>{done ? 'Added' : 'Add'}</Button>
              </Group>
            </>
          )}
        </Stack>
      </Popover.Dropdown>
    </Popover>
  )
}

/** Call after creating or deleting a talk so the popover's list refreshes. */
export function invalidateTalks() { talksCache = null }
