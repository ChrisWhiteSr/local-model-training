import { useEffect, useState } from 'react'
import { AppShell, Button, Container, Group, Loader, Space, Tabs, Text, TextInput, Title, ScrollArea, Code } from '@mantine/core'
import { useQuery, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { apiGet, apiPost, getBaseUrl, setBaseUrl } from './api/client'
import { useEventSource } from './hooks/useEventSource'

const qc = new QueryClient()

function Health() {
  const { data, isLoading, refetch } = useQuery({ queryKey: ['health'], queryFn: () => apiGet<any>('/health') })
  return (
    <Container>
      <Group justify="space-between">
        <Title order={3}>Health</Title>
        <Button onClick={() => refetch()}>Refresh</Button>
      </Group>
      {isLoading ? <Loader /> : <pre>{JSON.stringify(data, null, 2)}</pre>}
    </Container>
  )
}

function Documents() {
  const { data, isLoading, refetch } = useQuery({ queryKey: ['documents'], queryFn: () => apiGet<any>('/documents') })
  const [lastIngest, setLastIngest] = useState<any>(null)
  const [isIngesting, setIsIngesting] = useState(false)
  const [polledLogs, setPolledLogs] = useState<any[]>([])
  const { events, status } = useEventSource<any>('/events/ingest')

  // Fallback polling: poll /logs/ingest every 2s while ingesting
  useEffect(() => {
    if (!isIngesting) return
    const interval = setInterval(async () => {
      try {
        const logs = await apiGet<any>('/logs/ingest?limit=50')
        setPolledLogs(logs.items || [])
      } catch {}
    }, 2000)
    return () => clearInterval(interval)
  }, [isIngesting])
  // Derive simple activity summary from events
  const summary = (() => {
    const state: any = { running: false, totalFiles: 0, processedFiles: 0, current: new Set<string>(), done: [] as any[] }
    for (const ev of events) {
      switch (ev.event) {
        case 'ingest_run_start':
          state.running = true
          state.totalFiles = ev.count_files || 0
          state.processedFiles = 0
          state.current = new Set<string>()
          state.done = []
          break
        case 'ingest_file_start':
          if (ev.file) state.current.add(ev.file)
          break
        case 'ingest_file_done':
          if (ev.file) state.current.delete(ev.file)
          state.processedFiles += 1
          state.done.push({ file: ev.file, chunks: ev.chunks, pages: ev.pages, embed_latency_ms: ev.embed_latency_ms })
          break
        case 'ingest_file_skipped':
        case 'ingest_file_error':
          state.processedFiles += 1
          if (ev.file) state.current.delete(ev.file)
          break
        case 'ingest_run_done':
          state.running = false
          break
      }
    }
    return {
      running: state.running,
      totalFiles: state.totalFiles,
      processedFiles: state.processedFiles,
      current: Array.from(state.current),
      done: state.done.slice(-10), // last 10
    }
  })()
  return (
    <Container>
      <Group justify="space-between">
        <Title order={3}>Documents</Title>
        <Group>
          <Button variant="light" onClick={() => refetch()}>Refresh</Button>
          <Button onClick={async () => {
            setIsIngesting(true)
            const result = await apiPost('/ingest', {})
            setLastIngest(result)
            setIsIngesting(false)
            await refetch()
          }}>Ingest</Button>
          <Button color="orange" onClick={async () => {
            setIsIngesting(true)
            const result = await apiPost('/ingest?force=true', {})
            setLastIngest(result)
            setIsIngesting(false)
            await refetch()
          }}>Force Re-Ingest</Button>
        </Group>
      </Group>
      {isLoading ? <Loader /> : <pre>{JSON.stringify(data, null, 2)}</pre>}
      <Space h="md" />
      {lastIngest && (
        <>
          <Title order={4}>Last Ingest Summary</Title>
          <Group gap="md">
            <Text>Found: <b>{lastIngest.files_found}</b></Text>
            <Text>Processed: <b>{lastIngest.files_processed}</b></Text>
            <Text>Skipped: <b>{lastIngest.files_skipped}</b></Text>
            <Text>Chunks: <b>{lastIngest.chunks_upserted}</b></Text>
            <Text>Errors: <b>{lastIngest.errors?.length || 0}</b></Text>
          </Group>
          {lastIngest.processed_list?.length > 0 && (
            <div>
              <Text size="sm" fw={600}>Processed Files:</Text>
              <ul>{lastIngest.processed_list.map((f: string) => <li key={f}><Code size="xs">{f}</Code></li>)}</ul>
            </div>
          )}
          {lastIngest.skipped_list?.length > 0 && (
            <div>
              <Text size="sm" fw={600}>Skipped Files (unchanged):</Text>
              <ul>{lastIngest.skipped_list.map((f: string) => <li key={f}><Code size="xs">{f}</Code></li>)}</ul>
            </div>
          )}
          <Space h="md" />
        </>
      )}
      <Space h="md" />
      <Title order={4}>Ingest Activity</Title>
      <Text size="sm" c="dimmed">Live events from /events/ingest {isIngesting && status !== 'open' && '(using fallback polling)'}</Text>
      <Group gap="lg">
        <Text>Running: <b>{summary.running || isIngesting ? 'Yes' : 'No'}</b></Text>
        <Text>Files: <b>{summary.processedFiles}/{summary.totalFiles}</b></Text>
        <Text>SSE Status: <b>{status}</b></Text>
        {isIngesting && status !== 'open' && <Text c="orange">Fallback: <b>Polling</b></Text>}
      </Group>
      <Space h="xs" />
      <Group align="flex-start" grow>
        <div>
          <Text fw={600}>Current</Text>
          {summary.current.length === 0 ? <Text size="sm" c="dimmed">None</Text> : (
            <ul>{summary.current.map((f) => <li key={f}><Code>{f}</Code></li>)}</ul>
          )}
        </div>
        <div>
          <Text fw={600}>Recently Completed</Text>
          {summary.done.length === 0 ? <Text size="sm" c="dimmed">None</Text> : (
            <ul>{summary.done.map((d,i) => <li key={i}><Code>{d.file}</Code> — chunks: {d.chunks}, pages: {d.pages}</li>)}</ul>
          )}
        </div>
      </Group>
      <ScrollArea h={260} scrollbarSize={8}>
        {events.map((e, i) => (
          <Code key={i} block>{JSON.stringify(e)}</Code>
        ))}
      </ScrollArea>
    </Container>
  )
}

function QueryView() {
  const [q, setQ] = useState('What is the main claim of Scientific Advertising?')
  const [res, setRes] = useState<any>(null)
  const [busy, setBusy] = useState(false)

  const run = async () => {
    setBusy(true)
    try {
      const out = await apiPost<any>('/query', { query: q })
      setRes(out)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Container>
      <Title order={3}>Query</Title>
      <Group>
        <TextInput style={{ flex: 1 }} value={q} onChange={(e) => setQ(e.currentTarget.value)} placeholder="Ask a question"/>
        <Button loading={busy} onClick={run}>Ask</Button>
      </Group>
      <Space h="md" />
      {busy ? <Loader /> : res ? (
        <>
          <Text fw={600}>Answer</Text>
          <Text>{res.answer}</Text>
          <Space h="sm" />
          <Text fw={600}>Citations</Text>
          <pre>{JSON.stringify(res.citations, null, 2)}</pre>
        </>
      ) : null}
    </Container>
  )
}

function Logs() {
  const { data, isLoading, refetch } = useQuery({ queryKey: ['ingestLogs'], queryFn: () => apiGet<any>('/logs/ingest?limit=200') })
  const { data: qlogs, isLoading: lqLoading, refetch: rq } = useQuery({ queryKey: ['queryLogs'], queryFn: () => apiGet<any>('/logs/query?limit=200') })
  return (
    <Container>
      <Group justify="space-between">
        <Title order={3}>Logs</Title>
        <Group>
          <Button variant="light" onClick={() => { refetch(); rq(); }}>Refresh</Button>
        </Group>
      </Group>
      <Title order={5}>Ingest</Title>
      {isLoading ? <Loader /> : <pre>{JSON.stringify(data, null, 2)}</pre>}
      <Title order={5}>Query</Title>
      {lqLoading ? <Loader /> : <pre>{JSON.stringify(qlogs, null, 2)}</pre>}
    </Container>
  )
}

function Settings() {
  const [base, setBase] = useState(getBaseUrl())
  useEffect(() => setBase(getBaseUrl()), [])
  return (
    <Container>
      <Title order={3}>Settings</Title>
      <Text size="sm" c="dimmed">Backend API Base URL</Text>
      <Group>
        <TextInput style={{ width: 420 }} value={base} onChange={(e) => setBase(e.currentTarget.value)} />
        <Button onClick={() => setBaseUrl(base)}>Save</Button>
      </Group>
      <Text size="xs" c="dimmed">Current: {getBaseUrl()}</Text>
    </Container>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <AppShell header={{ height: 56 }} padding="md">
        <AppShell.Header>
          <Group justify="space-between" px="md" h="100%">
            <Title order={4}>Local RAG UI</Title>
            <Text size="sm" c="dimmed">API: {getBaseUrl()}</Text>
          </Group>
        </AppShell.Header>
        <AppShell.Main>
          <Tabs defaultValue="dashboard">
            <Tabs.List>
              <Tabs.Tab value="dashboard">Dashboard</Tabs.Tab>
              <Tabs.Tab value="documents">Documents</Tabs.Tab>
              <Tabs.Tab value="queries">Queries</Tabs.Tab>
              <Tabs.Tab value="logs">Logs</Tabs.Tab>
              <Tabs.Tab value="settings">Settings</Tabs.Tab>
            </Tabs.List>
            <Tabs.Panel value="dashboard" pt="md"><Health /></Tabs.Panel>
            <Tabs.Panel value="documents" pt="md"><Documents /></Tabs.Panel>
            <Tabs.Panel value="queries" pt="md"><QueryView /></Tabs.Panel>
            <Tabs.Panel value="logs" pt="md"><Logs /></Tabs.Panel>
            <Tabs.Panel value="settings" pt="md"><Settings /></Tabs.Panel>
          </Tabs>
        </AppShell.Main>
      </AppShell>
    </QueryClientProvider>
  )
}
