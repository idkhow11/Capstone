import { useState, useEffect, useRef } from 'react'

/// <reference types="chrome"/>

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

  // 수정 - 한 번만 실행되게
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

  // const fetchResult = async (q: string) => {
  //   setLoading(true)
  //   try {
  //     const res = await fetch('http://localhost:8000/search', {
  //       method: 'POST',
  //       headers: { 'Content-Type': 'application/json' },
  //       body: JSON.stringify({ query: q, platform })
  //     })
  //     const data = await res.json()
  //     setMessages(prev => [...prev, {
  //       role: 'ai',
  //       content: data.recommendation,
  //       products: data.products
  //     }])
  //   } catch {
  //     setMessages(prev => [...prev, {
  //       role: 'ai',
  //       content: '오류가 발생했어요. 다시 시도해주세요.'
  //     }])
  //   } finally {
  //     setLoading(false)
  //   }
  // }

  const fetchResult = async (q: string) => {
  setLoading(true)

  // 로딩 효과를 위해 1.5초 대기
  await new Promise(resolve => setTimeout(resolve, 1500))

  // 질문에 따라 다른 답변 반환
  const mockResponse = getMockResponse(q, platform)
  
  setMessages(prev => [...prev, {
    role: 'ai',
    content: mockResponse.recommendation,
    products: mockResponse.products
  }])

  setLoading(false)
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
        padding: '0px 16px',
        borderBottom: '1px solid #eee',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        background: '#ffffff'
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
          {/*platform === 'kurly' ? '🟣 마켓컬리' : '🔵 다나와'*/} 검색 결과
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
              lineHeight: '1.5'
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
                    background: '#eee'
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
                    color: platform === 'kurly' ? '#5f0080' : '#0057ff'
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
                    background: platform === 'kurly' ? '#5f0080' : '#0057ff',
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

function getMockResponse(query: string, platform: 'kurly' | 'danawa') {

  // 마켓컬리 - 운동 후 식사
  if (query.includes('운동') || query.includes('단백질') || query.includes('저녁')) {
    return {
      recommendation: `운동 후 저녁 식사로 단백질을 보충하면서, 밤에 부담 없이 가볍고 건강하게 한 끼를 해결하고 싶으신 거군요! 운동으로 지친 몸에 활력을 불어넣어 줄 맛있는 메뉴들로 골라봤어요. 😊`,
      products: [
        {
          name: '[롤린스 다이닝] 구운채소 닭가슴살 샐러드',
          price: 7900,
          url: 'https://www.kurly.com/goods/1001847697',
          thumbnail: 'https://img.kurly.com/product/image/2025/1001847697.jpg',
          reason: '맛있는 구운 채소와 촉촉한 닭가슴살이 듬뿍 — 든든하면서도 건강한 한 끼를 간편하게 즐길 수 있어요. 단백질 보충에 최고이고 밤에도 부담 없이 속 편하게 드실 수 있답니다!'
        },
        {
          name: '[햇반] 파로곤약 닭가슴살 주먹밥 2종 (택 1)',
          price: 8980,
          url: 'https://www.kurly.com/goods/1001765127',
          thumbnail: 'https://img.kurly.com/product/image/2025/1001765127.jpg',
          reason: '고단백 저탄수 건강식으로 아주 훌륭해요! 꼬들꼬들한 파로곤약밥에 닭가슴살이 더해져 맛있고 든든하답니다. 전자레인지에 쏙 돌리면 되니 정말 간편해요.'
        },
        {
          name: '[햇반] 라이스플랜 병아리콩퀴노아곤약밥 150g*3입',
          price: 8940,
          url: 'https://www.kurly.com/goods/1001626707',
          thumbnail: 'https://img.kurly.com/product/image/2025/1001626707.jpg',
          reason: '좀 더 가볍게, 하지만 영양 균형은 놓치지 않고 탄수화물을 보충하고 싶으실 때 좋아요. 병아리콩, 퀴노아, 곤약이 칼로리 부담 없이 맛있는 밥을 즐길 수 있답니다.'
        }
      ]
    }
  }

  // 마켓컬리 - 알레르기
  if (query.includes('갑각류') || query.includes('알레르기')) {
    return {
      recommendation: `갑각류 알레르기가 있으신 분께 안전한 제품들을 찾았어요! ✓ 갑각류 원재료 미포함 확인 완료된 상품들이에요.`,
      products: [
        {
          name: '농심 신라면 건면',
          price: 1580,
          url: 'https://www.kurly.com/goods/1000100001',
          thumbnail: 'https://img.kurly.com/product/image/2025/1000100001.jpg',
          reason: '갑각류 성분 미포함 ✓ 나트륨 1,370mg으로 일반 라면 대비 낮은 편이에요.'
        },
        {
          name: '오뚜기 진라면 순한맛',
          price: 1350,
          url: 'https://www.kurly.com/goods/1000100002',
          thumbnail: 'https://img.kurly.com/product/image/2025/1000100002.jpg',
          reason: '갑각류 성분 미포함 ✓ 순한 맛으로 자극 없이 즐길 수 있어요.'
        }
      ]
    }
  }

  // 다나와 - 마우스
  if (query.includes('마우스') || query.includes('무선') || query.includes('무소음')) {
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

  // 기본 응답
  return {
    recommendation: `"${query}"에 대한 결과를 찾았어요! 아래 상품들을 확인해보세요.`,
    products: [
      {
        name: '추천 상품 예시 1',
        price: 12000,
        url: 'https://www.kurly.com',
        thumbnail: '',
        reason: '조건에 맞는 상품이에요.'
      }
    ]
  }
}