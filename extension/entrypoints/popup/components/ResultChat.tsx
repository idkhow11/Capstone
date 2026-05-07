import { useState, useEffect, useRef } from 'react'
import { searchApi, type ProductResponse } from '../../api/search'

/// <reference types="chrome"/>

// ─── 타입 정의 ───────────────────────────────────────
interface Message {
  role: 'user' | 'ai'
  content: string
  products?: ProductResponse[]
}

interface Props {
  query: string
  platform: 'danawa'
  onBack: () => void
}

// ─── 컴포넌트 ─────────────────────────────────────────
export default function ResultChat({ query, onBack }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [conversationId, setConversationId] = useState<number | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const initialized = useRef(false)

  useEffect(() => {
    if (initialized.current) return
    initialized.current = true
    setMessages([{ role: 'user', content: query }])
    fetchResult(query)
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const fetchResult = async (q: string) => {
    setLoading(true)
    try {
      const data = await searchApi.search(q, 'danawa', conversationId)
      setConversationId(data.conversation_id)
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
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      background: '#ffffff',
      color: '#111',
      fontFamily: 'sans-serif'
    }}>

      {/* 헤더 */}
      <div style={{
        height: '56px',
        padding: '0px 56px 0px 16px',
        borderBottom: '1px solid #eee',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        background: '#ffffff',
        boxSizing: 'border-box'
      }}>
        <button
          onClick={onBack}
          style={{
            background: 'none', border: 'none',
            color: '#aaa', cursor: 'pointer', fontSize: '18px'
          }}
        >
          ←
        </button>
        <span style={{ fontSize: '16px', fontWeight: 'bold', color: '#111' }}>
          🔵 다나와 검색 결과
        </span>
      </div>

      {/* 메시지 영역 */}
      <div style={{
        flex: 1,
        overflow: 'auto',
        padding: '16px',
        background: '#ffffff'
      }}>
        {messages.map((msg, i) => (
          <div key={i} style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
            marginBottom: '16px'
          }}>

            {/* 말풍선 */}
            <div style={{
              maxWidth: '80%',
              padding: '10px 14px',
              borderRadius: msg.role === 'user'
                ? '18px 18px 4px 18px'
                : '18px 18px 18px 4px',
              background: msg.role === 'user' ? '#111' : '#f5f5f5',
              color: msg.role === 'user' ? '#fff' : '#111',
              fontSize: '13px',
              lineHeight: '1.5',
              whiteSpace: 'pre-wrap'
            }}>
              {msg.content}
            </div>

            {/* 상품 카드 */}
            {msg.products && msg.products.map((product, j) => (
              <div key={j} style={{
                width: '100%',
                marginTop: '8px',
                background: '#f9f9f9',
                borderRadius: '12px',
                padding: '12px',
                display: 'flex',
                gap: '12px',
                border: '1px solid #eee',
                boxSizing: 'border-box'
              }}>
                {product.thumbnail && (
                  <img
                    src={product.thumbnail}
                    style={{
                      width: '60px', height: '60px',
                      borderRadius: '8px', objectFit: 'cover',
                      background: '#eee', flexShrink: 0
                    }}
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none'
                    }}
                  />
                )}
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <div style={{
                    fontSize: '13px', fontWeight: 'bold',
                    color: '#111', marginBottom: '4px',
                    whiteSpace: 'nowrap', overflow: 'hidden',
                    textOverflow: 'ellipsis'
                  }}>
                    {product.name}
                  </div>
                  <div style={{
                    fontSize: '13px', fontWeight: 'bold',
                    color: '#0057ff'
                  }}>
                    {typeof product.price === 'number'
                      ? `${product.price.toLocaleString()}원`
                      : '가격 정보 없음'}
                  </div>
                  {product.reason && (
                    <div style={{
                      fontSize: '11px', color: '#888', marginTop: '4px'
                    }}>
                      ✓ {product.reason}
                    </div>
                  )}
                </div>
                {product.url && (
                  <button
                    onClick={() => {
                      if (product.url) chrome.tabs.create({ url: product.url })
                    }}
                    style={{
                      padding: '6px 10px',
                      background: '#0057ff',
                      border: 'none', borderRadius: '8px',
                      color: 'white', fontSize: '11px',
                      cursor: 'pointer', flexShrink: 0,
                      alignSelf: 'center'
                    }}
                  >
                    구매
                  </button>
                )}
              </div>
            ))}
          </div>
        ))}

        {/* 로딩 */}
        {loading && (
          <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            marginBottom: '16px'
          }}>
            <div style={{
              padding: '10px 14px',
              background: '#f5f5f5',
              borderRadius: '18px 18px 18px 4px',
              color: '#888',
              fontSize: '13px'
            }}>
              분석 중이에요...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* 입력창 */}
      <div style={{
        padding: '12px 16px',
        borderTop: '1px solid #eee',
        display: 'flex',
        gap: '8px',
        background: '#ffffff'
      }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="추가로 궁금한 점을 물어보세요."
          style={{
            flex: 1,
            padding: '10px 14px',
            background: '#f5f5f5',
            border: '1px solid #eee',
            borderRadius: '10px',
            color: '#111',
            fontSize: '13px',
            outline: 'none'
          }}
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          style={{
            padding: '10px 16px',
            background: input.trim() ? '#111' : '#eee',
            border: 'none',
            borderRadius: '10px',
            color: input.trim() ? 'white' : '#aaa',
            cursor: input.trim() ? 'pointer' : 'not-allowed',
            fontSize: '13px',
            transition: 'all 0.2s'
          }}
        >
          전송
        </button>
      </div>
    </div>
  )
}
