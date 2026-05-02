import { apiRequest } from './client'

export const searchApi = {

  search: (query: string, platform: string) =>
    apiRequest<{ products: any[]; recommendation: string }>(
      '/search',
      {
        method: 'POST',
        body: JSON.stringify({ query, platform })
      }
    ),

  getHistory: (userId: number) =>
    apiRequest<any[]>(`/history/${userId}`),

  saveHistory: (userId: number, query: string, platform: string, result: any) =>
    apiRequest('/history', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, query, platform, result })
    })
}