import { defineStore } from 'pinia'
import { ref } from 'vue'
import { sendMessage as apiSend } from '../api/index.js'

export const useChatStore = defineStore('chat', () => {
  const conversations = ref({})
  const currentId = ref(null)
  const loading = ref(false)

  function getConversation(cid) {
    if (!conversations.value[cid]) {
      conversations.value[cid] = { messages: [], title: '新对话' }
    }
    return conversations.value[cid]
  }

  function addMessage(cid, message) {
    const conv = getConversation(cid)
    conv.messages.push({
      id: crypto.randomUUID(),
      ...message,
      timestamp: new Date().toISOString(),
    })
    // Auto-set title from first user message
    if (message.role === 'user' && conv.title === '新对话') {
      conv.title = message.content.slice(0, 30) + (message.content.length > 30 ? '...' : '')
    }
  }

  async function sendMessage(cid, question) {
    addMessage(cid, { role: 'user', content: question })
    loading.value = true

    try {
      const response = await apiSend(question, cid, false)
      addMessage(cid, {
        role: 'assistant',
        content: response.answer,
        sources: response.sources || [],
        graphData: response.graph_data || { nodes: [], edges: [] },
        reasoningSteps: response.reasoning_steps || [],
        conversationId: response.conversation_id,
      })
      if (response.conversation_id && cid !== response.conversation_id) {
        // If backend returned a different conversation_id, update
      }
    } catch (err) {
      addMessage(cid, {
        role: 'assistant',
        content: '抱歉，系统遇到了错误。请稍后重试。',
        sources: [],
        graphData: { nodes: [], edges: [] },
        reasoningSteps: [],
      })
    } finally {
      loading.value = false
    }
  }

  return { conversations, currentId, loading, sendMessage, addMessage, getConversation }
})
