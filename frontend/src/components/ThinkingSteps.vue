<template>
  <div class="thinking-steps">
    <h4>推理过程</h4>
    <div v-for="(step, i) in steps" :key="i" class="step">
      <span class="step-number">{{ i + 1 }}</span>
      <span class="step-text">{{ step }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({ steps: { type: Array, required: true } })
</script>

<style scoped>
.thinking-steps {
  background: #fff3e0;
  border-radius: 8px;
  padding: 12px;
  margin-top: 8px;
}
h4 {
  font-size: 13px;
  color: #e65100;
  margin-bottom: 8px;
}
.step {
  display: flex;
  margin: 6px 0;
  font-size: 13px;
}
.step-number {
  width: 22px; height: 22px;
  border-radius: 50%;
  background: #ff9800;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  flex-shrink: 0;
  margin-right: 8px;
}
.step-text { color: #333; line-height: 1.5; }
</style>
