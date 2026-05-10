import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

export async function sendMessage(question, conversationId = null, newConversation = false, graphHops = 2, apiKey = null) {
  const body = {
    question,
    conversation_id: conversationId,
    new_conversation: newConversation,
    graph_hops: graphHops,
  }
  if (apiKey) body.api_key = apiKey
  const { data } = await api.post('/chat', body)
  return data
}

export async function sendMessageStream(question, conversationId, newConversation, graphHops, apiKey, onToken, onDone, onError) {
  const body = {
    question,
    conversation_id: conversationId || null,
    new_conversation: newConversation || false,
    graph_hops: graphHops || 2,
  }
  if (apiKey) body.api_key = apiKey

  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  // Check for HTTP errors (e.g. 401 from API key validation)
  if (!response.ok) {
    let detail = ''
    try { const err = await response.json(); detail = err.detail || '' } catch {}
    const err = new Error(detail || `HTTP ${response.status}`)
    err.status = response.status
    err.detail = detail
    onError(err)
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6))
          if (data.done) {
            onDone(data)
          } else if (data.token) {
            onToken(data.token)
          }
        } catch { /* skip malformed chunks */ }
      }
    }
  }
}

export async function getTrace(question, conversationId = null) {
  const { data } = await api.post('/trace', {
    question,
    conversation_id: conversationId,
  })
  return data
}

export async function checkHealth() {
  const { data } = await api.get('/health')
  return data
}
