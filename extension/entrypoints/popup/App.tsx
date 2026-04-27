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
  const [sidebarOpen, setSidebarOpen] = useState(true)

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
  }

  const handleHistoryClick = (item: SearchHistory) => {
    setActiveId(item.id)
    setQuery(item.query)
    setPlatform(item.platform)
    setScreen('result')
  }

  const handleNewChat = () => {
    setActiveId(null)
    setQuery('')
    setScreen('home')
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
      display: 'flex',
      width: '100%',
      minHeight: '100vh',
      background: '#0f1117',
      color: 'white',
      fontFamily: 'sans-serif'
    }}>

      {/* 왼쪽 사이드바 */}
      <div style={{
        width: sidebarOpen ? '140px' : '32px',
        minHeight: '100vh',
        background: '#161820',
        borderRight: '1px solid #222',
        display: 'flex',
        flexDirection: 'column',
        padding: '12px 8px',
        flexShrink: 0,
        overflow: 'hidden',
        transition: 'width 0.2s ease'
      }}>

        {/* 토글 버튼 */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          style={{
            background: 'none', border: 'none',
            color: '#888', cursor: 'pointer',
            fontSize: '14px', padding: '4px',
            marginBottom: '12px',
            alignSelf: sidebarOpen ? 'flex-end' : 'center',
            transition: 'all 0.2s'
          }}
        >
          {sidebarOpen ? '←' : '→'}
        </button>

        {/* 사이드바 열렸을 때만 표시 */}
        {sidebarOpen && (
          <>
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

                  {/* 호버하거나 선택됐을 때만 X 버튼 표시 */}
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
          </>
        )}
      </div>

      {/* 오른쪽 메인 영역 */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
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