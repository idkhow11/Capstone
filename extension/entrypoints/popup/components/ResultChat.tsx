import { useState, useEffect, useRef } from 'react'

/// <reference types="chrome"/>

// ─── 타입 정의 ───────────────────────────────────────
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
  platform: 'danawa'
  onBack: () => void
}

// ─── API 호출 (백엔드 연결 시 이 부분만 교체) ────────
const BASE_URL = 'http://localhost:8000'

async function searchAPI(query: string): Promise<{
  recommendation: string
  products: Product[]
}> {
  // 백엔드 연결 전 mock 응답
  // 실제 연결 시 아래 주석 해제하고 mock 부분 삭제
  /*
  const res = await fetch(`${BASE_URL}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, platform: 'danawa' })
  })
  if (!res.ok) throw new Error('검색 실패')
  return res.json()
  */

  await new Promise(resolve => setTimeout(resolve, 1500))
  return getMockResponse(query)
}

// ─── 컴포넌트 ─────────────────────────────────────────
export default function ResultChat({ query, onBack }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
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
      const data = await searchAPI(q)
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
                    {product.price?.toLocaleString()}원
                  </div>
                  {product.reason && (
                    <div style={{
                      fontSize: '11px', color: '#888', marginTop: '4px'
                    }}>
                      ✓ {product.reason}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => chrome.tabs.create({ url: product.url })}
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

// ─── Mock 데이터 (백엔드 연결 시 삭제) ───────────────
function getMockResponse(query: string): {
  recommendation: string
  products: Product[]
} {

  // 마우스
  if (query.includes('마우스') || query.includes('무소음') || query.includes('무선')) {
    return {
      recommendation: `무선 무소음 마우스 5~10만원대로 찾아봤어요! 조용한 환경에서도 쾌적하게 사용할 수 있는 제품들이에요. 🖱️`,
      products: [
        {
          name: '로지텍 MX Anywhere 3',
          price: 79000,
          url: 'https://prod.danawa.com/info/?pcode=12345678',
          thumbnail: 'https://img.danawa.com/prod_img/500000/123/456/img/12345678_1.jpg',
          reason: '무선 + 무소음 클릭 ✓ 배터리 최대 70일 — 이 가격대 최고 수준이에요.'
        },
        {
          name: '앱코 AMG200 무선 무소음',
          price: 58000,
          url: 'https://prod.danawa.com/info/?pcode=87654321',
          thumbnail: 'https://img.danawa.com/prod_img/500000/321/654/img/87654321_1.jpg',
          reason: '무선 + 무소음 ✓ 가격 대비 성능 우수, 배터리 30일.'
        }
      ]
    }
  }

  // 키보드
  if (query.includes('키보드') || query.includes('기계식') || query.includes('게이밍')) {
    return {
      recommendation: `게이밍 키보드를 찾아봤어요! 타건감과 성능 모두 만족스러운 제품들이에요. ⌨️`,
      products: [
        {
          name: '로지텍 G913 TKL 무선 기계식',
          price: 189000,
          url: 'https://prod.danawa.com/info/?pcode=11111111',
          thumbnail: 'https://img.danawa.com/prod_img/500000/111/111/img/11111111_1.jpg',
          reason: '무선 + 얇은 로우프로파일 ✓ 게이밍과 사무용 모두 적합해요.'
        },
        {
          name: '앱코 K935P 유선 기계식',
          price: 45000,
          url: 'https://prod.danawa.com/info/?pcode=22222222',
          thumbnail: 'https://img.danawa.com/prod_img/500000/222/222/img/22222222_1.jpg',
          reason: '가성비 최고 ✓ 청축 타건감으로 게이밍에 최적화.'
        }
      ]
    }
  }

  // 기본 응답
  return {
    recommendation: `"${query}"에 대한 결과를 찾았어요! 아래 상품들을 확인해보세요.`,
    products: [
      {
        name: '검색 결과 예시',
        price: 50000,
        url: 'https://prod.danawa.com',
        thumbnail: '',
        reason: '조건에 맞는 상품이에요.'
      }
    ]
  }
}