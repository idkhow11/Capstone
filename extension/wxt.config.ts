import { defineConfig } from 'wxt'

export default defineConfig({
  manifest: {
    name: '쇼핑 도우미',
    description: '자연어로 식품을 검색해드려요',
    permissions: ['sidePanel', 'storage', 'tabs'],
    side_panel: {
      default_path: 'sidepanel.html'
    }
  }
})