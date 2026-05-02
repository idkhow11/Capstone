import { useState } from 'react'

interface Props {
  onSearch: (query: string) => void
}

export default function SearchHome({ onSearch }: Props) {
  const [query, setQuery] = useState('')

  const handleSearch = () => {
    if (!query.trim()) return
    onSearch(query)
  }

  return (
    <div style={{
      height: '100vh',
      boxSizing: 'border-box',
      background: '#ffffff',
      color: '#111',
      fontFamily: 'sans-serif',
      display: 'flex',
      flexDirection: 'column',
      padding: '0'
    }}>

      {/* 헤더 */}
      <div style={{
        height: '56px',
        padding: '0 56px 0 20px',
        display: 'flex',
        alignItems: 'center',
        borderBottom: '1px solid #f0f0f0',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '18px' }}>🛒</span>
          <span style={{ fontSize: '16px', fontWeight: 'bold', color: '#111' }}>
            쇼핑 도우미
          </span>
        </div>
      </div>

      {/* 본문 */}
      <div style={{ padding: '28px 20px', flex: 1 }}>

        {/* 타이틀 */}
        <p style={{
          fontSize: '22px',
          fontWeight: 'bold',
          color: '#111',
          marginBottom: '24px',
          lineHeight: '1.4'
        }}>
          오늘은 어떻게 도와드릴까요?
        </p>

        {/* 검색창 */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          background: '#f5f5f5',
          borderRadius: '12px',
          padding: '14px 16px',
          border: '1px solid #e0e0e0',
          marginBottom: '10px'
        }}>
          <span style={{ marginRight: '8px', color: '#aaa' }}>🔍</span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="무선 무소음 마우스, 게이밍 키보드 추천..."
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: '#111',
              fontSize: '14px',
            }}
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              style={{
                background: 'none', border: 'none',
                color: '#aaa', cursor: 'pointer', fontSize: '16px'
              }}
            >
              ✕
            </button>
          )}
        </div>

        {/* 안내 텍스트 */}
        <p style={{
          fontSize: '12px',
          color: '#aaa',
          paddingLeft: '4px'
        }}>
          Enter 키를 눌러 검색하세요
        </p>

      </div>
    </div>
  )
}