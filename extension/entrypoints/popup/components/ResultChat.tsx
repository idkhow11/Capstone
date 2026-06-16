import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { searchApi, type ProductResponse } from '../../api/search'
import remarkCjkFriendly from 'remark-cjk-friendly'

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
    fetchResult(query, [])   // 첫 검색: 이전 대화 없음
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // history = 현재 질문 이전까지의 대화 (멀티턴 맥락으로 백엔드에 전달)
  const fetchResult = async (q: string, history: Message[]) => {
    setLoading(true)
    try {
      // products 등 부가 필드를 떼고 {role, content}만 전송
      const priorMessages = history.map(m => ({
        role: m.role,
        content: m.content
      }))

      const data = await searchApi.search(q, 'danawa', conversationId, priorMessages)
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
    // 방금 입력(q)을 추가하기 전까지의 messages = "이전 대화"
    // 이 시점의 messages는 이전 응답까지 확정된 상태라 안전하게 캡처됨
    const priorHistory = messages
    setMessages(prev => [...prev, { role: 'user', content: q }])
    fetchResult(q, priorHistory)   // q는 query로, 나머지는 이전 대화로 전달
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

      {/* 마크다운 렌더 스타일 (한 번만 주입) */}
      <style>{`
        .modumoa-md { font-size: 13px; line-height: 1.55; color: #111; }
        .modumoa-md > *:first-child { margin-top: 0; }
        .modumoa-md > *:last-child { margin-bottom: 0; }
        .modumoa-md p { margin: 0 0 8px; }
        .modumoa-md ul, .modumoa-md ol { margin: 0 0 8px; padding-left: 18px; }
        .modumoa-md li { margin: 2px 0; }
        .modumoa-md strong { font-weight: 700; }
        .modumoa-md h1, .modumoa-md h2, .modumoa-md h3 { font-size: 14px; margin: 10px 0 4px; }
        .modumoa-md a { color: #0057ff; text-decoration: none; }
        .modumoa-md code { background: #ececec; padding: 1px 4px; border-radius: 4px; font-size: 12px; }
        /* 비교표 — 좁은 패널에서 가로 스크롤 */
        .modumoa-md table {
          border-collapse: collapse;
          margin: 8px 0;
          font-size: 12px;
          display: block;
          overflow-x: auto;
          max-width: 100%;
        }
        .modumoa-md th, .modumoa-md td {
          border: 1px solid #ddd;
          padding: 6px 8px;
          text-align: left;
          white-space: nowrap;
        }
        .modumoa-md th { background: #f0f0f0; font-weight: 700; }
      `}</style>

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
            {msg.role === 'user' ? (
              <div style={{
                maxWidth: '80%',
                padding: '10px 14px',
                borderRadius: '18px 18px 4px 18px',
                background: '#111',
                color: '#fff',
                fontSize: '13px',
                lineHeight: '1.5',
                whiteSpace: 'pre-wrap'
              }}>
                {msg.content}
              </div>
            ) : (
              <div
                className="modumoa-md"
                style={{
                  maxWidth: '100%',
                  padding: '10px 14px',
                  borderRadius: '18px 18px 18px 4px',
                  background: '#f5f5f5',
                  color: '#111',
                  boxSizing: 'border-box'
                }}
              >
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkCjkFriendly]}>
                  {msg.content}
                </ReactMarkdown>
              </div>
            )}

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