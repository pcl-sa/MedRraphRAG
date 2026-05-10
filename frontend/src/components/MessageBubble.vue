<template>
  <div :class="['message', message.role]">
    <div :class="['avatar', { 'avatar-error': message.isError }]">{{ message.isError ? '!' : (message.role === 'user' ? '我' : 'AI') }}</div>
    <div class="bubble">
      <div :class="['content', { 'content-error': message.isError }]" v-html="renderedContent"></div>

      <div v-if="message.role === 'assistant' && hasExtras" class="extras">
        <button
          v-if="message.reasoningSteps?.length"
          class="toggle-btn"
          @click="showReasoning = !showReasoning"
        >{{ showReasoning ? '收起' : '查看' }}推理过程 ({{ message.reasoningSteps.length }}步)</button>

        <button
          v-if="message.sources?.length"
          class="toggle-btn"
          @click="showSources = !showSources"
        >{{ showSources ? '收起' : '查看' }}知识来源 ({{ message.sources.length }}条)</button>

        <button
          v-if="message.graphData?.nodes?.length"
          class="toggle-btn"
          @click="showGraph = !showGraph"
        >{{ showGraph ? '收起' : '查看' }}知识图谱</button>

        <ThinkingSteps v-if="showReasoning" :steps="message.reasoningSteps" />
        <SourcePanel v-if="showSources" :sources="message.sources" />
        <GraphViewer v-if="showGraph" :graph-data="message.graphData" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { marked } from 'marked'
import ThinkingSteps from './ThinkingSteps.vue'
import SourcePanel from './SourcePanel.vue'
import GraphViewer from './GraphViewer.vue'

const props = defineProps({ message: { type: Object, required: true } })

const showReasoning = ref(false)
const showSources = ref(false)
const showGraph = ref(false)

const renderedContent = computed(() => {
  try {
    return marked.parse(props.message.content || '')
  } catch {
    return props.message.content?.replace(/\n/g, '<br>') || ''
  }
})

const hasExtras = computed(() => {
  return props.message.sources?.length || props.message.graphData?.nodes?.length || props.message.reasoningSteps?.length
})
</script>

<style scoped>
.message {
  display: flex;
  margin-bottom: 20px;
}
.message.user { flex-direction: row-reverse; }
.avatar {
  width: 36px; height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
  flex-shrink: 0;
}
.user .avatar { background: #4fc3f7; color: #fff; }
.assistant .avatar { background: #66bb6a; color: #fff; }
.bubble {
  max-width: 75%;
  margin: 0 12px;
}
.user .bubble { margin-right: 12px; }
.assistant .bubble { margin-left: 12px; }
.content {
  background: #fff;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.assistant .content {
  background: linear-gradient(135deg, #e8f5e9, #f1f8e9);
}
.extras {
  margin-top: 8px;
}
.toggle-btn {
  display: block;
  margin: 4px 0;
  padding: 6px 12px;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  color: #555;
}
.toggle-btn:hover { background: #f0f0f0; }
.avatar-error {
  background: #e74c3c !important;
  color: #fff !important;
}
.content-error {
  background: #fdf0ef !important;
  border: 1px solid #e74c3c !important;
  color: #c0392b !important;
}
</style>
