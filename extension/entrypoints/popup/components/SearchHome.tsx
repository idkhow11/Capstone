import { useState } from 'react'

interface Props {
  platform: 'kurly' | 'danawa'
  setPlatform: (p: 'kurly' | 'danawa') => void
  onSearch: (query: string) => void
}

export default function SearchHome({ platform, setPlatform, onSearch }: Props) {
  const [query, setQuery] = useState('')

  const handleSearch = () => {
    if (!query.trim()) return
    onSearch(query)
  }

  return (
    <div style={{ padding: '20px' }}>

      {/* 헤더 */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '20px' }}>🛒</span>
          <span style={{ fontSize: '18px', fontWeight: 'bold' }}>쇼핑 도우미</span>
          {/* <span style={{
            marginLeft: 'auto', fontSize: '11px', color: '#00c471',
            background: '#00c47120', padding: '2px 8px', borderRadius: '10px'
          }}>● 실시간</span> */}
        </div>
        <p style={{ fontSize: '12px', color: '#888', marginTop: '4px' }}>
          똑똑한 쇼핑의 시작
        </p>
        <p style={{ fontSize: '20px', color: '#ffffff', marginTop: '4px' }}>
          오늘은 어떻게 도와드릴까요?
        </p>
      </div>

      {/* 플랫폼 선택 */}
      <div style={{ marginBottom: '20px' }}>
        <p style={{ fontSize: '12px', color: '#888', marginBottom: '8px' }}>
          플랫폼 선택
        </p>
        <div style={{ display: 'flex', gap: '8px' }}>
          {(['kurly', 'danawa'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPlatform(p)}
              style={{
                flex: 1, padding: '10px', borderRadius: '10px', cursor: 'pointer',
                border: platform === p
                  ? `2px solid ${p === 'kurly' ? '#5f0080' : '#0057ff'}`
                  : '2px solid #333',
                background: platform === p
                  ? (p === 'kurly' ? '#5f008020' : '#0057ff20')
                  : 'transparent',
                color: platform === p
                  ? (p === 'kurly' ? '#bf59cf' : '#4d94ff')
                  : '#888',
                fontWeight: 'bold', fontSize: '13px'
              }}
            >
              {p === 'kurly' ? '🟣 마켓컬리' : '🔵 다나와'}
            </button>
          ))}
        </div>
      </div>

      {/* 검색창 */}
      <div>
        <div style={{
          display: 'flex', alignItems: 'center',
          background: '#1e2130', borderRadius: '12px',
          padding: '12px 16px', marginBottom: '10px',
          border: '1px solid #333'
        }}>
          <span style={{ marginRight: '8px', color: '#888' }}>🔍</span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder={
              platform === 'kurly'
                ? '예: 갑각류 없는 라면, 당류 낮은 간식'
                : '예: 무선 무소음 마우스 5~10만원'
            }
            style={{
              flex: 1, background: 'transparent', border: 'none',
              outline: 'none', color: 'white', fontSize: '13px'
            }}
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              style={{
                background: 'none', border: 'none',
                color: '#888', cursor: 'pointer', fontSize: '16px'
              }}
            >
              ✕
            </button>
          )}
        </div>

        <button
          onClick={handleSearch}
          disabled={!query.trim()}
          style={{
            width: '100%', padding: '14px', borderRadius: '12px', border: 'none',
            background: query.trim()
              ? (platform === 'kurly' ? '#5f0080' : '#0057ff')
              : '#333',
            color: query.trim() ? 'white' : '#666',
            fontSize: '15px', fontWeight: 'bold',
            cursor: query.trim() ? 'pointer' : 'not-allowed',
            transition: 'all 0.2s'
          }}
        >
          검색하기
        </button>
      </div>

    </div>
  )
}