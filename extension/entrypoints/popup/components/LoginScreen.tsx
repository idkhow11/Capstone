import { useState } from 'react'

interface Props {
  onLogin: (user: {
    id: number
    name: string
    email: string
    token: string
    profileImage?: string
    profile_image?: string
  }) => void
  onBack: () => void
}

export default function LoginScreen({ onLogin, onBack }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // 일반 로그인 / 회원가입
  const handleSubmit = async () => {
    if (!email.trim() || !password.trim()) {
      setError('이메일과 비밀번호를 입력해주세요')
      return
    }
    if (mode === 'register' && !name.trim()) {
      setError('이름을 입력해주세요')
      return
    }

    setLoading(true)
    setError('')

    try {
      const endpoint = mode === 'login'
        ? 'http://localhost:8000/auth/login'
        : 'http://localhost:8000/auth/register'

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, name })
      })

      const data = await res.json()

      if (!res.ok) {
        setError(data.detail ?? '오류가 발생했어요')
        return
      }

      if (mode === 'register') {
        setMode('login')
        setError('가입 완료! 로그인해주세요.')
        return
      }

      // 로그인 성공
      chrome.storage.local.set({ user: data })
      onLogin(data)

    } catch {
      setError('서버 연결 오류')
    } finally {
      setLoading(false)
    }
  }

  // 구글 로그인
  const handleGoogleLogin = async () => {
    setLoading(true)
    setError('')

    try {
      // Chrome Identity API로 구글 토큰 발급
      const token = await new Promise<string>((resolve, reject) => {
        chrome.identity.getAuthToken({ interactive: true }, (tokenResult) => {
          const accessToken = typeof tokenResult === 'string'
            ? tokenResult
            : tokenResult?.token

          if (chrome.runtime.lastError || !accessToken) {
            reject(chrome.runtime.lastError)
          } else {
            resolve(accessToken)
          }
        })
      })

      // 백엔드에서 토큰을 검증하고 사용자 정보를 가져옴
      const res = await fetch('http://localhost:8000/auth/google', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_token: token })
      })

      const data = await res.json()

      if (!res.ok) {
        setError('구글 로그인 실패')
        return
      }

      chrome.storage.local.set({ user: data })
      onLogin(data)

    } catch {
      setError('구글 로그인 오류')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      height: '100vh',
      background: '#fff',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      padding: '32px 24px',
      boxSizing: 'border-box', 
      position: 'relative'
    }}>
        {/* 뒤로가기 버튼 */}
    <button
      onClick={onBack}
      style={{
        position: 'absolute',
        top: '12px',
        left: '12px',
        background: 'none',
        border: 'none',
        fontSize: '20px',
        cursor: 'pointer',
        color: '#aaa',
        padding: '6px'
      }}
    >
      ←
    </button>

      {/* 로고 */}
      <div style={{ textAlign: 'center', marginBottom: '36px' }}>
        <div style={{ fontSize: '36px', marginBottom: '8px' }}>🛒</div>
        <h1 style={{
          fontSize: '20px', fontWeight: 'bold',
          color: '#111', margin: 0
        }}>
          쇼핑 도우미
        </h1>
        <p style={{ fontSize: '13px', color: '#aaa', marginTop: '6px' }}>
          {mode === 'login' ? '로그인하고 시작하세요' : '계정을 만들어보세요'}
        </p>
      </div>

      {/* 입력 폼 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>

        {/* 이름 - 회원가입 시에만 */}
        {mode === 'register' && (
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="이름"
            style={{
              padding: '12px 16px',
              borderRadius: '10px',
              border: '1px solid #e0e0e0',
              fontSize: '14px',
              outline: 'none',
              color: '#111',
              boxSizing: 'border-box',
              width: '100%'
            }}
          />
        )}

        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="이메일"
          type="email"
          style={{
            padding: '12px 16px',
            borderRadius: '10px',
            border: '1px solid #e0e0e0',
            fontSize: '14px',
            outline: 'none',
            color: '#111',
            boxSizing: 'border-box',
            width: '100%'
          }}
        />

        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          placeholder="비밀번호"
          type="password"
          style={{
            padding: '12px 16px',
            borderRadius: '10px',
            border: '1px solid #e0e0e0',
            fontSize: '14px',
            outline: 'none',
            color: '#111',
            boxSizing: 'border-box',
            width: '100%'
          }}
        />

        {/* 에러 메시지 */}
        {error && (
          <p style={{
            fontSize: '12px',
            color: error.includes('완료') ? '#22c55e' : '#ef4444',
            paddingLeft: '4px',
            margin: 0
          }}>
            {error}
          </p>
        )}

        {/* 로그인/가입 버튼 */}
        <button
          onClick={handleSubmit}
          disabled={loading}
          style={{
            padding: '13px',
            borderRadius: '10px',
            background: loading ? '#888' : '#111',
            border: 'none',
            color: 'white',
            fontSize: '14px',
            fontWeight: 'bold',
            cursor: loading ? 'not-allowed' : 'pointer',
            marginTop: '4px'
          }}
        >
          {loading ? '처리 중...' : mode === 'login' ? '로그인' : '가입하기'}
        </button>

        {/* 구분선 */}
        <div style={{
          display: 'flex', alignItems: 'center',
          gap: '12px', margin: '4px 0'
        }}>
          <div style={{ flex: 1, height: '1px', background: '#e0e0e0' }} />
          <span style={{ fontSize: '12px', color: '#aaa' }}>또는</span>
          <div style={{ flex: 1, height: '1px', background: '#e0e0e0' }} />
        </div>

        {/* 구글 로그인 버튼 */}
        <button
          onClick={handleGoogleLogin}
          disabled={loading}
          style={{
            padding: '13px',
            borderRadius: '10px',
            background: '#fff',
            border: '1px solid #e0e0e0',
            color: '#111',
            fontSize: '14px',
            fontWeight: 'bold',
            cursor: loading ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px'
          }}
        >
          {/* 구글 로고 */}
          <svg width="18" height="18" viewBox="0 0 18 18">
            <path fill="#4285F4" d="M16.51 8H8.98v3h4.3c-.18 1-.74 1.48-1.6 2.04v2.01h2.6a7.8 7.8 0 002.38-5.88c0-.57-.05-.66-.15-1.18z"/>
            <path fill="#34A853" d="M8.98 17c2.16 0 3.97-.72 5.3-1.94l-2.6-2a4.8 4.8 0 01-7.18-2.54H1.83v2.07A8 8 0 008.98 17z"/>
            <path fill="#FBBC05" d="M4.5 10.52a4.8 4.8 0 010-3.04V5.41H1.83a8 8 0 000 7.18l2.67-2.07z"/>
            <path fill="#EA4335" d="M8.98 4.18c1.17 0 2.23.4 3.06 1.2l2.3-2.3A8 8 0 001.83 5.4L4.5 7.49a4.77 4.77 0 014.48-3.31z"/>
          </svg>
          Google로 계속하기
        </button>

        {/* 모드 전환 */}
        <button
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login')
            setError('')
            setEmail('')
            setPassword('')
            setName('')
          }}
          style={{
            background: 'none', border: 'none',
            color: '#aaa', fontSize: '12px',
            cursor: 'pointer', marginTop: '4px',
            textDecoration: 'underline'
          }}
        >
          {mode === 'login'
            ? '계정이 없으신가요? 회원가입'
            : '이미 계정이 있으신가요? 로그인'}
        </button>

      </div>
    </div>
  )
}
