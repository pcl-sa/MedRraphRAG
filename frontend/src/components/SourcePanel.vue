<template>
  <div class="source-panel">
    <h4>知识来源 ({{ sources.length }}条)</h4>
    <div v-for="(src, i) in sources" :key="i" class="source-card">
      <div class="source-header">
        <span class="source-title">{{ src.title || '无标题' }}</span>
        <span class="source-dept">{{ src.department }}</span>
      </div>
      <div class="source-score">相关度: {{ (src.score * 100).toFixed(1) }}%</div>
      <div class="source-preview">{{ src.text_preview }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({ sources: { type: Array, required: true } })
</script>

<style scoped>
.source-panel {
  background: #e3f2fd;
  border-radius: 8px;
  padding: 12px;
  margin-top: 8px;
}
h4 {
  font-size: 13px;
  color: #1565c0;
  margin-bottom: 8px;
}
.source-card {
  background: #fff;
  border-radius: 6px;
  padding: 10px;
  margin: 6px 0;
}
.source-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.source-title {
  font-size: 13px;
  font-weight: bold;
  color: #333;
}
.source-dept {
  font-size: 11px;
  color: #666;
  background: #e0e0e0;
  padding: 2px 8px;
  border-radius: 10px;
}
.source-score {
  font-size: 11px;
  color: #1565c0;
  margin: 4px 0;
}
.source-preview {
  font-size: 12px;
  color: #555;
  line-height: 1.5;
  margin-top: 6px;
  max-height: 80px;
  overflow: hidden;
}
</style>
