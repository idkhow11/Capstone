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
    { id: 1, query: '우유 없는 샐러드', platform: 'kurly' },
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
    setSidebarOpen(false)
  }

  const handleHistoryClick = (item: SearchHistory) => {
    setActiveId(item.id)
    setQuery(item.query)
    setPlatform(item.platform)
    setScreen('result')
    setSidebarOpen(false)
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
      height: '100vh',
      background: '#ffffff',
      color: '#111',
      fontFamily: 'sans-serif',
      overflow: 'hidden'
    }}>

      {/* 메인 영역 */}
      <div style={{ width: '100%', height: '100vh', overflow: 'hidden' }}>
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

      {/* 딤 처리 - 사이드바 열릴 때만, 전체 덮음 */}
      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{
            position: 'fixed',
            top: 0, left: 0,
            width: '100%',
            height: '100%',
            background: 'rgba(0,0,0,0.25)',
            zIndex: 50
          }}
        />
      )}

      {/* 사이드바 */}
      {sidebarOpen && (
        <div style={{
          position: 'fixed',
          top: 0,
          right: 0,
          width: '200px',
          height: '100%',
          background: '#ffffff',
          borderLeft: '1px solid #e0e0e0',
          display: 'flex',
          flexDirection: 'column',
          padding: '12px 8px',
          zIndex: 60,
          boxSizing: 'border-box'
        }}>

          {/* 사이드바 상단 - 토글 버튼과 높이 맞춤 */}
          <div style={{
            height: '44px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            marginBottom: '12px'
          }}>
            <button
              onClick={() => setSidebarOpen(false)}
              style={{
                background: 'none', border: 'none',
                color: '#aaa', cursor: 'pointer',
                fontSize: '14px', padding: '6px 10px',
              }}
            >
              →
            </button>
          </div>

          {/* 새 검색 버튼 */}
          <button
            onClick={handleNewChat}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '8px 10px', borderRadius: '8px',
              background: 'transparent', border: '1px solid #e0e0e0',
              color: '#111', cursor: 'pointer', fontSize: '12px',
              marginBottom: '16px', width: '100%'
            }}
          >
            <span style={{ fontSize: '14px' }}>+</span>
            새 검색
          </button>

          {/* 최근 검색 목록 */}
          <p style={{
            fontSize: '10px', color: '#aaa',
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
                  background: activeId === item.id ? '#f5f5f5' : 'transparent',
                  border: activeId === item.id ? '1px solid #e0e0e0' : '1px solid transparent',
                  display: 'flex', alignItems: 'center',
                  justifyContent: 'space-between', gap: '4px',
                  transition: 'all 0.15s'
                }}
              >
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <div style={{
                    fontSize: '11px',
                    color: activeId === item.id ? '#111' : '#888',
                    whiteSpace: 'nowrap', overflow: 'hidden',
                    textOverflow: 'ellipsis'
                  }}>
                    {item.query}
                  </div>
                  <div style={{ fontSize: '9px', color: '#bbb', marginTop: '2px' }}>
                    {item.platform === 'kurly' ? '🟣 컬리' : '🔵 다나와'}
                  </div>
                </div>
                <button
                  onClick={(e) => handleDeleteHistory(item.id, e)}
                  style={{
                    background: 'none', border: 'none', color: '#bbb',
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
      )}

      {/* 토글 버튼 - 항상 위에 고정, 헤더와 수평 맞춤 */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        style={{
          position: 'fixed',
          top: '12px',
          right: '12px',
          zIndex: 70,
          background: '#f5f5f5',
          border: '1px solid #e0e0e0',
          color: '#111',
          cursor: 'pointer',
          fontSize: '14px',
          padding: '6px 10px',
          borderRadius: '8px',
          height: '32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}
      >
        ☰
      </button>

    </div>
  )
}