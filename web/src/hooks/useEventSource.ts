import { useEffect, useRef, useState } from 'react'
import { getBaseUrl } from '../api/client'

export function useEventSource<T = any>(path: string) {
  const [events, setEvents] = useState<T[]>([])
  const [status, setStatus] = useState<'connecting' | 'open' | 'error'>('connecting')
  const srcRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const url = getBaseUrl() + path
    const es = new EventSource(url)
    srcRef.current = es
    es.onopen = () => setStatus('open')
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        setEvents((prev) => [...prev, data])
      } catch {}
    }
    es.onerror = () => {
      setStatus('error')
      // Let the browser retry automatically
    }
    return () => {
      es.close()
      srcRef.current = null
    }
  }, [path])

  return { events, status }
}
