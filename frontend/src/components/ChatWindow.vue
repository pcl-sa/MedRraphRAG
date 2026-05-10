<template>
  <div class="chat-window">
    <div class="messages-container" ref="msgContainer">
      <MessageBubble v-for="msg in messages" :key="msg.id" :message="msg" />
      <div v-if="loading" class="typing-indicator">
        <span class="streaming-text">{{ streamingText || '思考中...' }}</span>
      </div>
    </div>
    <div class="input-area">
      <div class="input-row">
        <input
          v-model="input"
          class="question-input"
          placeholder="请输入您的医疗问题..."
          @keyup.enter="submit"
          :disabled="loading"
        />
        <button class="send-btn" @click="submit" :disabled="!input.trim() || loading">发送</button>
      </div>
      <div class="options-row">
        <label class="hop-label">图谱跳数:</label>
        <select v-model.number="graphHops" class="hop-select">
          <option :value="1">1 跳</option>
          <option :value="2">2 跳</option>
          <option :value="3">3 跳</option>
        </select>
        <label class="stream-label">
          <input type="checkbox" v-model="useStream" />
          流式
        </label>
        <div class="apikey-wrapper">
          <input
            v-model="apiKey"
            :class="['apikey-input', { 'apikey-error': apiKeyError }]"
            type="password"
            placeholder="API Key (可选，留空使用默认)"
            :disabled="loading"
            @input="apiKeyError ? emit('update:apiKeyError', '') : null"
          />
          <span v-if="apiKeyError" class="apikey-error-text">{{ apiKeyError }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import MessageBubble from './MessageBubble.vue'

const props = defineProps({
  messages: { type: Array, required: true },
  loading: { type: Boolean, default: false },
  streamingText: { type: String, default: '' },
  savedApiKey: { type: String, default: '' },
  apiKeyError: { type: String, default: '' },
})
const emit = defineEmits(['send', 'sendStream', 'update:apiKey', 'update:apiKeyError'])

const input = ref('')
const msgContainer = ref(null)
const graphHops = ref(2)
const useStream = ref(true)
const apiKey = ref(props.savedApiKey || '')

function submit() {
  const q = input.value.trim()
  if (!q) return
  const key = apiKey.value.trim() || null
  if (useStream.value) {
    emit('sendStream', q, graphHops.value, key)
  } else {
    emit('send', q, graphHops.value, key)
  }
  input.value = ''
  // Save API key to parent for persistence
  if (key !== (props.savedApiKey || null)) {
    emit('update:apiKey', key)
  }
}

watch(() => props.messages.length, async () => {
  await nextTick()
  scrollDown()
})

watch(() => props.streamingText, () => {
  scrollDown()
})

function scrollDown() {
  if (msgContainer.value) {
    msgContainer.value.scrollTop = msgContainer.value.scrollHeight
  }
}
</script>

<style scoped>
.chat-window {
  display: flex;
  flex-direction: column;
  height: 100vh;
}
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #f5f5f5;
}
.typing-indicator {
  padding: 8px 16px;
}
.streaming-text {
  color: #333;
  font-size: 14px;
  line-height: 1.6;
}
.input-area {
  background: #fff;
  border-top: 1px solid #e0e0e0;
  padding: 12px 16px;
}
.input-row {
  display: flex;
  gap: 12px;
}
.question-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
}
.question-input:focus { border-color: #4fc3f7; }
.send-btn {
  padding: 10px 20px;
  background: #4fc3f7;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: bold;
  white-space: nowrap;
}
.send-btn:hover { background: #29b6f6; }
.send-btn:disabled { background: #bdbdbd; cursor: not-allowed; }
.options-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
  font-size: 12px;
  color: #666;
}
.hop-label { font-weight: 500; }
.hop-select {
  padding: 2px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 12px;
  outline: none;
}
.stream-label {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}
.apikey-wrapper {
  flex: 1;
  max-width: 260px;
  position: relative;
}
.apikey-input {
  width: 100%;
  padding: 2px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 11px;
  outline: none;
}
.apikey-input:focus { border-color: #4fc3f7; }
.apikey-input.apikey-error {
  border-color: #e74c3c;
  background: #fdf0ef;
}
.apikey-error-text {
  display: block;
  color: #e74c3c;
  font-size: 10px;
  margin-top: 2px;
  line-height: 1.3;
}
</style>
