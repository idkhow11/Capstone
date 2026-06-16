import { apiRequest } from './client'

export interface ProductResponse {
  product_id?: string | null
  name: string
  brand?: string | null
  price?: number | null
  url?: string | null
  thumbnail?: string | null
  reason?: string | null
  score?: number | null
}

export interface SearchResponse {
  products: ProductResponse[]
  recommendation: string
  conversation_id: number | null
}

// 멀티턴: 이전 대화 한 턴 ({role, content})
export interface ChatMessage {
  role: string      // 'user' | 'ai'
  content: string
}

export const searchApi = {

  search: (
    query: string,
    platform: string,
    conversationId?: number | null,
    messages?: ChatMessage[]            // 이전 대화 이력 (게스트 멀티턴)
  ) =>
    apiRequest<SearchResponse>(
      '/search',
      {
        method: 'POST',
        body: JSON.stringify({
          query,
          platform,
          ...(conversationId ? { conversation_id: conversationId } : {}),
          ...(messages && messages.length ? { messages } : {})
        })
      }
    ),

  getHistory: () =>
    apiRequest<any[]>('/history'),

  saveHistory: (userId: number, query: string, platform: string, result: any) =>
    apiRequest('/history', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, query, platform, result })
    })
}