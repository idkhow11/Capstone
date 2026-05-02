import { useState, useEffect } from 'react'
import SearchHome from './components/SearchHome'
import ResultChat from './components/ResultChat'
import LoginScreen from './components/LoginScreen'

interface SearchHistory {
  id: number
  query: string
  platform: 'danawa'  // kurly 제거
}

interface User {
  id: number
  name: string
  email: string
  token: string
  profileImage?: string
}

export default function App() {
  const [screen, setScreen] = useState<'home' | 'result' | 'login'>('home')
  const [query, setQuery] = useState('')
  const [platform] = useState<'danawa'>('danawa')  // kurly 제거, setter 불필요
  const [history, setHistory] = useState<SearchHistory[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [hoveredId, setHoveredId] = useState<number | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [profileMenuOpen, setProfileMenuOpen] = useState(false)
  const [user, setUser] = useState<User | null>(null)

  // 앱 시작 시 로컬 저장소 확인
  useEffect(() => {
    chrome.storage.local.get(['history', 'user'], (result) => {
      if (result.user) {
        setUser(result.user)
        fetchServerHistory(result.user)
      } else {
        if (result.history) {
          setHistory(result.history)
        }
      }
    })
  }, [])

  // 서버 히스토리 불러오기
  const fetchServerHistory = async (userData: User) => {
    try {
      const res = await fetch(
        `http://localhost:8000/history/${userData.id}`,
        { headers: { Authorization: `Bearer ${userData.token}` } }
      )
      if (!res.ok) return
      const data = await res.json()
      setHistory(data.map((h: any) => ({
        id: h.id,
        query: h.query,
        platform: 'danawa'
      })))
    } catch {
      console.error('히스토리 불러오기 실패')
    }
  }

  const handleSearch = (q: string) => {
    const newItem: SearchHistory = {
      id: Date.now(),
      query: q,
      platform: 'danawa'
    }
    const newHistory = [newItem, ...history.slice(0, 9)]

    setHistory(newHistory)
    setActiveId(newItem.id)
    setQuery(q)
    setScreen('result')
    setSidebarOpen(false)

    if (user) {
      fetch('http://localhost:8000/history', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${user.token}`
        },
        body: JSON.stringify({
          user_id: user.id,
          query: q,
          platform: 'danawa'
        })
      }).catch(console.error)
    } else {
      chrome.storage.local.set({ history: newHistory })
    }
  }

  const handleHistoryClick = (item: SearchHistory) => {
    setActiveId(item.id)
    setQuery(item.query)
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
    const newHistory = history.filter(h => h.id !== id)
    setHistory(newHistory)

    if (user) {
      fetch(`http://localhost:8000/history/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${user.token}` }
      }).catch(console.error)
    } else {
      chrome.storage.local.set({ history: newHistory })
    }

    if (activeId === id) {
      setScreen('home')
      setActiveId(null)
    }
  }

  const handleLogin = (userData: User) => {
    setUser(userData)
    setHistory([])
    fetchServerHistory(userData)
    setScreen('home')
    setSidebarOpen(false)
    chrome.storage.local.set({ user: userData })
  }

  const handleLogout = () => {
    setUser(null)
    setProfileMenuOpen(false)
    setSidebarOpen(false)
    setScreen('home')
    setHistory([])
    chrome.storage.local.remove(['user'])

    // 로그아웃 후 로컬 히스토리 복원
    chrome.storage.local.get(['history'], (result) => {
      if (result.history) setHistory(result.history)
    })
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
        {screen === 'login' ? (
          <LoginScreen
            onLogin={handleLogin}
            onBack={() => setScreen('home')}
          />
        ) : screen === 'home' ? (
          <SearchHome
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

      {/* 딤 처리 */}
      {sidebarOpen && (
        <div
          onClick={() => {
            setSidebarOpen(false)
            setProfileMenuOpen(false)
          }}
          style={{
            position: 'fixed',
            top: 0, left: 0,
            width: '100%', height: '100%',
            background: 'rgba(0,0,0,0.25)',
            zIndex: 50
          }}
        />
      )}

      {/* 사이드바 */}
      {sidebarOpen && (
        <div style={{
          position: 'fixed',
          top: 0, right: 0,
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

          {/* 사이드바 상단 */}
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

          <div style={{
            display: 'flex', flexDirection: 'column', gap: '2px',
            flex: 1, overflow: 'auto'
          }}>
            {history.length === 0 ? (
              <p style={{
                fontSize: '11px', color: '#ccc',
                paddingLeft: '4px', marginTop: '4px'
              }}>
                검색 기록이 없어요
              </p>
            ) : (
              history.map((item) => (
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
                      🔵 다나와
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
              ))
            )}
          </div>

          {/* 하단 프로필 영역 */}
          <div style={{ marginTop: 'auto', position: 'relative' }}>

            <div style={{
              height: '1px',
              background: '#e0e0e0',
              margin: '12px 0'
            }} />

            {/* 프로필 드롭업 메뉴 */}
            {profileMenuOpen && user && (
              <div style={{
                position: 'absolute',
                bottom: '60px',
                left: 0, right: 0,
                background: '#1a1a1a',
                borderRadius: '10px',
                overflow: 'hidden',
                border: '1px solid #333',
                zIndex: 10
              }}>
                <div style={{
                  padding: '12px 14px',
                  borderBottom: '1px solid #333',
                  fontSize: '11px',
                  color: '#aaa',
                  wordBreak: 'break-all'
                }}>
                  {user.email}
                </div>
                <button
                  onClick={handleLogout}
                  style={{
                    width: '100%',
                    padding: '12px 14px',
                    background: 'none', border: 'none',
                    color: '#ff6b6b', fontSize: '13px',
                    cursor: 'pointer', textAlign: 'left',
                    display: 'flex', alignItems: 'center', gap: '8px'
                  }}
                >
                  <span>↩</span>
                  로그아웃
                </button>
              </div>
            )}

            {/* 프로필 카드 - 로그인 상태 */}
            {user ? (
              <div
                onClick={() => setProfileMenuOpen(!profileMenuOpen)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '10px',
                  padding: '10px 12px', borderRadius: '10px',
                  background: '#111', cursor: 'pointer'
                }}
              >
                {user.profileImage ? (
                  <img
                    src={user.profileImage}
                    style={{
                      width: '32px', height: '32px',
                      borderRadius: '50%', objectFit: 'cover', flexShrink: 0
                    }}
                  />
                ) : (
                  <div style={{
                    width: '32px', height: '32px', borderRadius: '50%',
                    background: '#555', display: 'flex',
                    alignItems: 'center', justifyContent: 'center',
                    fontSize: '14px', fontWeight: 'bold',
                    color: 'white', flexShrink: 0
                  }}>
                    {user.name.charAt(0).toUpperCase()}
                  </div>
                )}
                <div style={{ overflow: 'hidden', flex: 1 }}>
                  <div style={{
                    fontSize: '13px', fontWeight: 'bold', color: 'white',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                  }}>
                    {user.name}
                  </div>
                </div>
                <span style={{
                  color: '#555', fontSize: '10px', flexShrink: 0,
                  transform: profileMenuOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 0.2s'
                }}>
                  ▲
                </span>
              </div>

            ) : (
              <button
                onClick={() => {
                  setSidebarOpen(false)
                  setScreen('login')
                }}
                style={{
                  width: '100%', padding: '10px 12px',
                  borderRadius: '10px', background: '#111',
                  border: 'none', color: 'white',
                  fontSize: '13px', fontWeight: 'bold',
                  cursor: 'pointer', display: 'flex',
                  alignItems: 'center', justifyContent: 'center', gap: '6px'
                }}
              >
                <span>👤</span>
                로그인
              </button>
            )}
          </div>
        </div>
      )}

      {/* 토글 버튼 */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        style={{
          position: 'fixed',
          top: '12px', right: '12px',
          zIndex: 70,
          background: '#f5f5f5',
          border: '1px solid #e0e0e0',
          color: '#111', cursor: 'pointer',
          fontSize: '14px', padding: '6px 10px',
          borderRadius: '8px', height: '32px',
          display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}
      >
        ☰
      </button>

    </div>
  )
}