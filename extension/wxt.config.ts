import { defineConfig } from 'wxt'

export default defineConfig({
  manifest: {
    name: '쇼핑 도우미',
    description: '자연어로 식품을 검색해드려요',
    permissions: ['sidePanel', 'storage', 'tabs', 'identity'],
    side_panel: {
      default_path: 'sidepanel.html'
    },
    oauth2: {
      client_id: '410613268292-9l8livar4ndbfkbbhsfpespeak1gr375.apps.googleusercontent.com',
      scopes: [
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile'
      ]
    }
  }
})