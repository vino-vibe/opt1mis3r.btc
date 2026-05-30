import { useEffect, useRef } from 'react'

interface Props {
  lines: string[]
}

type LineColor = 'green' | 'red' | 'gray' | 'yellow' | 'blue' | 'orange' | 'white'

function classifyLine(line: string): LineColor {
  const t = line.trimStart()
  if (t.startsWith('[+]')) return 'green'
  if (t.startsWith('[!]') || t.startsWith('[X]')) return 'red'
  if (t.startsWith('[?]')) return 'yellow'
  if (t.startsWith('[i]')) return 'blue'
  if (t.startsWith('[~]')) return 'orange'
  if (t.startsWith('[ ]') || t.startsWith('[DRY')) return 'gray'
  if (t.startsWith('===') || t.startsWith('---')) return 'white'
  if (t === '[DONE]') return 'green'
  return 'white'
}

const COLOR: Record<LineColor, string> = {
  green:  'text-green-400',
  red:    'text-red-400',
  gray:   'text-gray-500',
  yellow: 'text-yellow-300',
  blue:   'text-blue-400',
  orange: 'text-orange-400',
  white:  'text-gray-200',
}

export function Terminal({ lines }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines.length])

  return (
    <div className="bg-gray-950 rounded-lg p-4 font-mono text-sm h-96 overflow-y-auto border border-gray-800">
      {lines.length === 0 && (
        <span className="text-gray-600">Output will appear here...</span>
      )}
      {lines.map((line, i) => (
        <div
          key={i}
          className={`leading-5 whitespace-pre-wrap break-all ${COLOR[classifyLine(line)]}`}
        >
          {line || ' '}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
