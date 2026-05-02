import { apiRequest } from './client'

export const authApi = {

  login: (email: string, password: string) =>
    apiRequest<{ id: number; name: string; email: string; token: string }>(
      '/auth/login',
      {
        method: 'POST',
        body: JSON.stringify({ email, password })
      }
    ),

  register: (email: string, password: string, name: string) =>
    apiRequest('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, name })
    }),

  googleLogin: (googleId: string, email: string, name: string, profileImage: string) =>
    apiRequest<{ id: number; name: string; email: string; token: string }>(
      '/auth/google',
      {
        method: 'POST',
        body: JSON.stringify({
          google_id: googleId,
          email, name,
          profile_image: profileImage
        })
      }
    ),

  logout: () => chrome.storage.local.remove(['user'])
}