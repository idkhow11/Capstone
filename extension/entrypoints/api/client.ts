// 기본 설정 한 곳에서 관리
const BASE_URL = 'http://localhost:8000'

// 나중에 배포 시 여기만 바꾸면 됨
// const BASE_URL = 'https://our-server.com'

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {

  // Chrome Storage에서 토큰 자동으로 가져옴
  const storage = await chrome.storage.local.get(['user']) as {
    user?: { token?: string }
  }
  const token = storage.user?.token

  const res = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  })

  // 401 → 자동 로그아웃
  if (res.status === 401) {
    chrome.storage.local.remove(['user'])
    throw new Error('UNAUTHORIZED')
  }

  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail ?? '오류가 발생했어요')
  }

  return res.json()
}
