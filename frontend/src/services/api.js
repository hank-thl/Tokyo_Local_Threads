const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5004'

async function requestJson(path) {
  const response = await fetch(`${API_BASE_URL}${path}`)

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`)
  }

  return response.json()
}

export async function fetchDocuments({ limit = 100, category } = {}) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (category) {
    params.set('category', category)
  }

  const payload = await requestJson(`/api/documents?${params.toString()}`)
  return payload.data || []
}

export async function fetchSdgTags() {
  const payload = await requestJson('/api/sdg-tags')
  return payload.data || []
}
