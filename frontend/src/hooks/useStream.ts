import { useRef, useState, useCallback, useEffect } from 'react'

export function useStream(onLine: (line: string) => void) {
  const esRef = useRef<EventSource | null>(null)
  const [running, setRunning] = useState(false)
  const onLineRef = useRef(onLine)

  useEffect(() => {
    onLineRef.current = onLine
  })

  const start = useCallback((url: string) => {
    esRef.current?.close()
    setRunning(true)

    const es = new EventSource(url)
    esRef.current = es

    es.onmessage = (event: MessageEvent) => {
      if (event.data === '[DONE]') {
        es.close()
        esRef.current = null
        setRunning(false)
        return
      }
      onLineRef.current(event.data)
    }

    es.onerror = () => {
      es.close()
      esRef.current = null
      setRunning(false)
      onLineRef.current('[!] Connection error — stream closed')
    }
  }, [])

  const cancel = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    setRunning(false)
  }, [])

  useEffect(() => {
    return () => {
      esRef.current?.close()
    }
  }, [])

  return { start, cancel, running }
}
