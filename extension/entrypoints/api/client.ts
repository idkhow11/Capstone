// 기본 설정 한 곳에서 관리 — URL은 이제 여기 한 곳만 바꾸면 됨
export const BASE_URL = 'https://capstone-production-86c4.up.railway.app'

// 로컬 백엔드로 테스트할 땐 위를 주석 처리하고 아래를 사용
// export const BASE_URL = 'http://localhost:8000'

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