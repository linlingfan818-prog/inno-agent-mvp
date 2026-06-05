const API_BASE = 'http://127.0.0.1:8088'

export async function healthCheck() {
  const res = await fetch(`${API_BASE}/api/health`)
  if (!res.ok) throw new Error('health check failed')
  return res.json()
}

export async function uploadFile(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: form })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'upload failed')
  return data
}

export async function confirmParsed(sessionId, parsedCharter) {
  const res = await fetch(`${API_BASE}/api/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, parsed_charter: parsedCharter }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'confirm failed')
  return data
}

export async function generateCard(sessionId, parsedCharter) {
  const res = await fetch(`${API_BASE}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, parsed_charter: parsedCharter }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'generate failed')
  return data
}

export function getDownloadUrl(relativeUrl) {
  return `${API_BASE}${relativeUrl}`
}
