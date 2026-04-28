import { useState } from 'react'
import SearchHome from './components/SearchHome'
import ResultChat from './components/ResultChat'

interface SearchHistory {
  id: number
  query: string
  platform: 'kurly' | 'danawa'
}

export default function App() {
  const [screen, setScreen] = useState<'home' | 'result'>('home')
  const [query, setQuery] = useState('')
  const [platform, setPlatform] = useState<'kurly' | 'danawa'>('kurly')
  const [history, setHistory] = useState<SearchHistory[]>([
    { id: 1, query: '갑각류 없는 라면', platform: 'kurly' },
    { id: 2, query: '무선 무소음 마우스', platform: 'danawa' },
    { id: 3, query: '당류 낮은 간식', platform: 'kurly' },
  ])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [hoveredId, setHoveredId] = useState<number | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const handleSearch = (q: string) => {
    const newItem: SearchHistory = {
      id: Date.now(),
      query: q,
      platform
    }
    setHistory(prev => [newItem, ...prev.slice(0, 9)])
    setActiveId(newItem.id)
    setQuery(q)
    setScreen('result')
    setSidebarOpen(false) // 검색 시 사이드바 닫기
  }

  const handleHistoryClick = (item: SearchHistory) => {
    setActiveId(item.id)
    setQuery(item.query)
    setPlatform(item.platform)
    setScreen('result')
    setSidebarOpen(false) // 선택 시 사이드바 닫기
  }

  const handleNewChat = () => {
    setActiveId(null)
    setQuery('')
    setScreen('home')
    setSidebarOpen(false)
  }

  const handleDeleteHistory = (id: number, e: React.MouseEvent) => {
    e.stopPropagation()
    setHistory(prev => prev.filter(h => h.id !== id))
    if (activeId === id) {
      setScreen('home')
      setActiveId(null)
    }
  }

  return (
    <div style={{
      position: 'relative',
      width: '100%',
      minHeight: '100vh',
      background: '#0f1117',
      color: 'white',
      fontFamily: 'sans-serif',
      overflow: 'hidden'
    }}>

      {/* 토글 버튼 (항상 고정) */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        style={{
          position: 'absolute',
          top: '12px',
          right: '12px',
          zIndex: 100,
          background: '#161820',
          border: '1px solid #333',
          color: '#888',
          cursor: 'pointer',
          fontSize: '14px',
          padding: '6px 10px',
          borderRadius: '8px',
          transition: 'all 0.2s'
        }}
      >
        {sidebarOpen ? '→' : '☰'}
      </button>

      {/* 사이드바 오버레이 */}
      {sidebarOpen && (
        <>
          {/* 배경 딤 처리 - 클릭하면 닫힘 */}
          <div
            onClick={() => setSidebarOpen(false)}
            style={{
              position: 'absolute',
              top: 0, left: 0, right: 0, bottom: 0,
              background: 'rgba(0,0,0,0.4)',
              zIndex: 50
            }}
          />

          {/* 사이드바 본체 */}
          <div style={{
            position: 'absolute',
            top: 0, right: 0,
            width: '160px',
            minHeight: '100%',
            background: '#161820',
            borderLeft: '1px solid #222',
            display: 'flex',
            flexDirection: 'column',
            padding: '12px 8px',
            zIndex: 60,
            animation: 'slideIn 0.2s ease'
          }}>

            {/* 닫기 버튼 */}
            <button
              onClick={() => setSidebarOpen(false)}
              style={{
                background: 'none', border: 'none',
                color: '#888', cursor: 'pointer',
                fontSize: '14px', padding: '4px',
                marginBottom: '12px',
                alignSelf: 'flex-start'
              }}
            >
              →
            </button>

            {/* 새 검색 버튼 */}
            <button
              onClick={handleNewChat}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '8px 10px', borderRadius: '8px',
                background: 'transparent', border: '1px solid #333',
                color: 'white', cursor: 'pointer', fontSize: '12px',
                marginBottom: '16px', width: '100%'
              }}
            >
              <span style={{ fontSize: '14px' }}>+</span>
              새 검색
            </button>

            {/* 최근 검색 목록 */}
            <p style={{
              fontSize: '10px', color: '#555',
              marginBottom: '8px', paddingLeft: '4px'
            }}>
              최근 검색
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
              {history.map((item) => (
                <div
                  key={item.id}
                  onClick={() => handleHistoryClick(item)}
                  onMouseEnter={() => setHoveredId(item.id)}
                  onMouseLeave={() => setHoveredId(null)}
                  style={{
                    padding: '8px 10px', borderRadius: '8px', cursor: 'pointer',
                    background: activeId === item.id ? '#1e2130' : 'transparent',
                    border: activeId === item.id ? '1px solid #333' : '1px solid transparent',
                    display: 'flex', alignItems: 'center',
                    justifyContent: 'space-between', gap: '4px',
                    transition: 'all 0.15s'
                  }}
                >
                  <div style={{ flex: 1, overflow: 'hidden' }}>
                    <div style={{
                      fontSize: '11px',
                      color: activeId === item.id ? 'white' : '#888',
                      whiteSpace: 'nowrap', overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}>
                      {item.query}
                    </div>
                    <div style={{ fontSize: '9px', color: '#555', marginTop: '2px' }}>
                      {item.platform === 'kurly' ? '🟣 컬리' : '🔵 다나와'}
                    </div>
                  </div>

                  <button
                    onClick={(e) => handleDeleteHistory(item.id, e)}
                    style={{
                      background: 'none', border: 'none', color: '#555',
                      cursor: 'pointer', fontSize: '10px', padding: '0',
                      flexShrink: 0,
                      opacity: (hoveredId === item.id || activeId === item.id) ? 1 : 0,
                      transition: 'opacity 0.15s'
                    }}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* 메인 영역 - 항상 동일한 크기 */}
      <div style={{ width: '100%', minHeight: '100vh' }}>
        {screen === 'home' ? (
          <SearchHome
            platform={platform}
            setPlatform={setPlatform}
            onSearch={handleSearch}
          />
        ) : (
          <ResultChat
            query={query}
            platform={platform}
            onBack={handleNewChat}
          />
        )}
      </div>

    </div>
  )
}