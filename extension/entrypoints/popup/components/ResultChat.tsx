import { useState, useEffect, useRef } from 'react'

interface Message {
  role: 'user' | 'ai'
  content: string
  products?: Product[]
}

interface Product {
  name: string
  price: number
  url: string
  thumbnail: string
  reason: string
}

interface Props {
  query: string
  platform: 'kurly' | 'danawa'
  onBack: () => void
}

export default function ResultChat({ query, platform, onBack }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // 첫 진입 시 자동으로 검색 실행
  useEffect(() => {
    setMessages([{ role: 'user', content: query }])
    fetchResult(query)
  }, [])

  // 새 메시지 오면 스크롤 아래로
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const fetchResult = async (q: string) => {
    setLoading(true)
    try {
      const res = await fetch('http://localhost:8000/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, platform })
      })
      const data = await res.json()
      setMessages(prev => [...prev, {
        role: 'ai',
        content: data.recommendation,
        products: data.products
      }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'ai',
        content: '오류가 발생했어요. 다시 시도해주세요.'
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleSend = () => {
    if (!input.trim() || loading) return
    const q = input
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: q }])
    fetchResult(q)
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      height: '100vh', background: '#0f1117'
    }}>

      {/* 헤더 */}
      <div style={{
        padding: '16px', borderBottom: '1px solid #222',
        display: 'flex', alignItems: 'center', gap: '12px'
      }}>
        <button onClick={onBack} style={{
          background: 'none', border: 'none',
          color: '#888', cursor: 'pointer', fontSize: '18px'
        }}>←</button>
        <span style={{ fontSize: '16px', fontWeight: 'bold', color: 'white' }}>
          {platform === 'kurly' ? '🟣 마켓컬리' : '🔵 다나와'} 검색 결과
        </span>
      </div>

      {/* 메시지 영역 */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
        {messages.map((msg, i) => (
          <div key={i} style={{
            display: 'flex', flexDirection: 'column',
            alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
            marginBottom: '16px'
          }}>
            {/* 말풍선 */}
            <div style={{
              maxWidth: '80%', padding: '10px 14px',
              borderRadius: msg.role === 'user'
                ? '18px 18px 4px 18px'
                : '18px 18px 18px 4px',
              background: msg.role === 'user' ? '#5f0080' : '#1e2130',
              color: 'white', fontSize: '13px', lineHeight: '1.5'
            }}>
              {msg.content}
            </div>

            {/* 상품 카드 */}
            {msg.products && msg.products.map((product, j) => (
              <div key={j} style={{
                width: '100%', marginTop: '8px',
                background: '#1e2130', borderRadius: '12px',
                padding: '12px', display: 'flex', gap: '12px',
                border: '1px solid #333'
              }}>
                <img src={product.thumbnail}
                  style={{ width: '60px', height: '60px', borderRadius: '8px', objectFit: 'cover' }}
                  onError={(e) => { (e.target as HTMLImageElement).src = '🛒' }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '13px', fontWeight: 'bold', color: 'white' }}>
                    {product.name}
                  </div>
                  <div style={{ fontSize: '13px', color: '#00c471', fontWeight: 'bold' }}>
                    {product.price?.toLocaleString()}원
                  </div>
                  {product.reason && (
                    <div style={{ fontSize: '11px', color: '#888', marginTop: '4px' }}>
                      ✓ {product.reason}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => chrome.tabs.create({ url: product.url })}
                  style={{
                    padding: '6px 10px', background: '#5f0080',
                    border: 'none', borderRadius: '8px',
                    color: 'white', fontSize: '11px', cursor: 'pointer'
                  }}
                >
                  구매
                </button>
              </div>
            ))}
          </div>
        ))}

        {/* 로딩 */}
        {loading && (
          <div style={{
            display: 'flex', alignItems: 'flex-start', marginBottom: '16px'
          }}>
            <div style={{
              padding: '10px 14px', background: '#1e2130',
              borderRadius: '18px 18px 18px 4px', color: '#888', fontSize: '13px'
            }}>
              분석 중이에요...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* 입력창 */}
      <div style={{
        padding: '12px 16px', borderTop: '1px solid #222',
        display: 'flex', gap: '8px'
      }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="추가로 궁금한 점을 물어보세요..."
          style={{
            flex: 1, padding: '10px 14px', background: '#1e2130',
            border: '1px solid #333', borderRadius: '10px',
            color: 'white', fontSize: '13px', outline: 'none'
          }}
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          style={{
            padding: '10px 16px', background: '#5f0080',
            border: 'none', borderRadius: '10px',
            color: 'white', cursor: 'pointer', fontSize: '13px'
          }}
        >
          전송
        </button>
      </div>
    </div>
  )
}