<template>
  <div class="app-container">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1>MedGraphRAG</h1>
        <p class="subtitle">医疗知识图谱问答</p>
      </div>
      <button class="new-chat-btn" @click="startNewChat">+ 新对话</button>
      <div class="conversation-list">
        <div
          v-for="(conv, cid) in conversations"
          :key="cid"
          :class="['conv-item', { active: cid === currentId }]"
          @click="switchConversation(cid)"
        >
          <span class="conv-title">{{ conv.title || '新对话' }}</span>
          <span class="conv-time">{{ conv.time }}</span>
          <button class="del-btn" @click.stop="deleteConversation(cid)" title="删除对话">×</button>
        </div>
      </div>
      <button
        v-if="Object.keys(conversations).length > 0"
        class="clear-all-btn"
        @click="clearAllConversations"
      >清空全部对话</button>
      <div class="sidebar-footer">
        <div class="status" :class="{ connected: health.neo4j_connected }">
          {{ health.neo4j_connected ? '图谱已连接' : '图谱未连接' }}
        </div>
        <div class="stats">文档数: {{ health.chroma_doc_count }} | 实体: {{ health.kg_node_count }}</div>
      </div>
    </aside>
    <main class="main-area">
      <ChatWindow
        v-if="currentId"
        :messages="currentMessages"
        :loading="loading"
        :streaming-text="streamingText"
        :saved-api-key="savedApiKey"
        :api-key-error="apiKeyError"
        @send="handleSend"
        @send-stream="handleSendStream"
        @update:api-key="saveApiKey"
        @update:api-key-error="v => apiKeyError = v"
      />
      <div v-else class="welcome">
        <h2>欢迎使用 MedGraphRAG</h2>
        <p>基于知识图谱增强的医疗问答系统</p>
        <p class="hint">点击"新对话"开始提问</p>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import ChatWindow from './components/ChatWindow.vue'
import { sendMessage, sendMessageStream } from './api/index.js'

const STORAGE_KEY = 'medgraphrag_conversations'
const APIKEY_STORAGE_KEY = 'medgraphrag_apikey'

const currentId = ref(null)
const loading = ref(false)
const streamingText = ref('')
const conversations = ref(loadFromStorage())
const savedApiKey = ref(loadApiKey())
const apiKeyError = ref('')
const health = ref({ neo4j_connected: false, chroma_doc_count: 0, kg_node_count: 0, kg_edge_count: 0 })

function extractErrorMessage(err) {
  if (err?.response?.status === 401) {
    const detail = err.response.data?.detail || ''
    return `API Key 无效：${detail.slice(0, 200)}`
  }
  if (err?.message?.includes('401')) {
    return `API Key 无效，请检查后重试。`
  }
  return '抱歉，系统遇到了错误，请稍后重试。'
}

function loadApiKey() {
  try { return localStorage.getItem(APIKEY_STORAGE_KEY) || '' } catch { return '' }
}
function saveApiKey(key) {
  try { localStorage.setItem(APIKEY_STORAGE_KEY, key || '') } catch { /* ignore */ }
  savedApiKey.value = key || ''
}

const currentMessages = computed(() => {
  if (!currentId.value) return []
  return conversations.value[currentId.value]?.messages || []
})

// ── Persistence ──
function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch { return {} }
}

function saveToStorage() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations.value))
  } catch { /* quota exceeded, ignore */ }
}

watch(conversations, saveToStorage, { deep: true })

// ── Chat operations ──
function startNewChat() {
  const id = crypto.randomUUID()
  conversations.value[id] = { title: '新对话', time: new Date().toLocaleTimeString(), messages: [] }
  currentId.value = id
  saveToStorage()
}

function switchConversation(cid) {
  currentId.value = cid
}

function deleteConversation(cid) {
  const ids = Object.keys(conversations.value)
  if (ids.length <= 1) {
    // Deleting the last conversation — just clear messages
    conversations.value[cid].messages = []
    conversations.value[cid].title = '新对话'
  } else {
    delete conversations.value[cid]
    if (currentId.value === cid) {
      const remaining = Object.keys(conversations.value)
      currentId.value = remaining.length > 0 ? remaining[remaining.length - 1] : null
    }
  }
  saveToStorage()
}

function clearAllConversations() {
  if (confirm('确定要清空全部对话记录吗？此操作不可撤销。')) {
    conversations.value = {}
    currentId.value = null
    saveToStorage()
  }
}

// ── Non-streaming send (legacy) ──
async function handleSend(question, graphHops = 2, apiKey = null) {
  if (!currentId.value) startNewChat()
  const cid = currentId.value
  const conv = conversations.value[cid]

  conv.messages.push({
    id: crypto.randomUUID(),
    role: 'user',
    content: question,
    timestamp: new Date().toISOString(),
  })
  if (conv.title === '新对话') {
    conv.title = question.slice(0, 25) + (question.length > 25 ? '...' : '')
  }
  saveToStorage()

  loading.value = true
  try {
    const response = await sendMessage(question, cid, false, graphHops, apiKey)
    conv.messages.push({
      id: crypto.randomUUID(),
      role: 'assistant',
      content: response.answer,
      sources: response.sources || [],
      graphData: response.graph_data || { nodes: [], edges: [] },
      reasoningSteps: response.reasoning_steps || [],
      conversationId: response.conversation_id,
      timestamp: new Date().toISOString(),
    })
    saveToStorage()
  } catch (err) {
    const errMsg = extractErrorMessage(err)
    conv.messages.push({
      id: crypto.randomUUID(),
      role: 'assistant',
      content: errMsg,
      isError: true,
      sources: [],
      graphData: { nodes: [], edges: [] },
      reasoningSteps: [],
      timestamp: new Date().toISOString(),
    })
    if (errMsg.includes('API Key')) apiKeyError.value = errMsg
  } finally {
    loading.value = false
  }
}

// ── Streaming send ──
async function handleSendStream(question, graphHops = 2, apiKey = null) {
  if (!currentId.value) startNewChat()
  const cid = currentId.value
  const conv = conversations.value[cid]

  conv.messages.push({
    id: crypto.randomUUID(),
    role: 'user',
    content: question,
    timestamp: new Date().toISOString(),
  })
  if (conv.title === '新对话') {
    conv.title = question.slice(0, 25) + (question.length > 25 ? '...' : '')
  }
  saveToStorage()

  loading.value = true
  streamingText.value = ''

  await sendMessageStream(
    question, cid, false, graphHops, apiKey,
    // onToken
    (token) => {
      streamingText.value += token
    },
    // onDone
    (data) => {
      conv.messages.push({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: streamingText.value,
        sources: data.sources || [],
        graphData: data.graph_data || { nodes: [], edges: [] },
        reasoningSteps: data.reasoning_steps || [],
        conversationId: data.conversation_id,
        timestamp: new Date().toISOString(),
      })
      streamingText.value = ''
      loading.value = false
      saveToStorage()
    },
    // onError
    (err) => {
      streamingText.value = ''
      const detail = err.detail || err.message || ''
      const isApiKeyError = err.status === 401 || detail.includes('API Key') || detail.includes('apikey')
      const errMsg = isApiKeyError
        ? `API Key 无效：${detail.slice(0, 200)}`
        : `请求失败：${detail.slice(0, 200) || '请稍后重试'}`
      conv.messages.push({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: errMsg,
        isError: true,
        sources: [],
        graphData: { nodes: [], edges: [] },
        reasoningSteps: [],
        timestamp: new Date().toISOString(),
      })
      if (isApiKeyError) apiKeyError.value = errMsg
      loading.value = false
      saveToStorage()
    },
  )
}

// ── Init ──
onMounted(async () => {
  // Restore last session
  const ids = Object.keys(conversations.value)
  if (ids.length > 0) {
    currentId.value = ids[ids.length - 1]
  }
  // Health check
  try {
    const res = await fetch('/api/health')
    health.value = await res.json()
  } catch { /* backend not ready */ }
})
</script>

<style scoped>
.app-container {
  display: flex;
  height: 100vh;
}
.sidebar {
  width: 280px;
  background: #1a1a2e;
  color: #eee;
  display: flex;
  flex-direction: column;
  padding: 16px;
}
.sidebar-header h1 {
  font-size: 20px;
  color: #4fc3f7;
}
.subtitle {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
.new-chat-btn {
  margin: 16px 0;
  padding: 10px;
  background: #4fc3f7;
  color: #1a1a2e;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: bold;
}
.new-chat-btn:hover { background: #81d4fa; }
.conversation-list {
  flex: 1;
  overflow-y: auto;
}
.conv-item {
  padding: 10px;
  margin: 4px 0;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
}
.conv-item:hover { background: #16213e; }
.conv-item.active { background: #0f3460; }
.conv-title { font-size: 13px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conv-time { font-size: 11px; color: #888; margin-left: 8px; flex-shrink: 0; }
.del-btn {
  background: none;
  border: none;
  color: #666;
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
  margin-left: 4px;
  line-height: 1;
  flex-shrink: 0;
  visibility: hidden;
}
.conv-item:hover .del-btn { visibility: visible; }
.del-btn:hover { color: #e74c3c; }
.clear-all-btn {
  margin-top: 8px;
  padding: 8px;
  background: transparent;
  color: #e74c3c;
  border: 1px solid #e74c3c;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  width: 100%;
}
.clear-all-btn:hover { background: #e74c3c; color: #fff; }
.sidebar-footer {
  border-top: 1px solid #333;
  padding-top: 12px;
  font-size: 12px;
}
.status { color: #e74c3c; }
.status.connected { color: #2ecc71; }
.stats { color: #888; margin-top: 4px; }
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #666;
}
.welcome h2 { font-size: 28px; color: #333; }
.welcome .hint { margin-top: 20px; color: #999; }
</style>
