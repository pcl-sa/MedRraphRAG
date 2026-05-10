<template>
  <div class="graph-viewer">
    <h4>知识图谱子图</h4>
    <div ref="container" class="graph-container"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'

const props = defineProps({ graphData: { type: Object, required: true } })

const container = ref(null)
let network = null

function renderGraph() {
  if (!container.value) return
  const { nodes, edges } = props.graphData
  if (!nodes?.length) return

  const colorMap = {
    '#e74c3c': { border: '#c0392b', background: '#e74c3c' },
    '#f39c12': { border: '#e67e22', background: '#f39c12' },
    '#3498db': { border: '#2980b9', background: '#3498db' },
    '#2ecc71': { border: '#27ae60', background: '#2ecc71' },
    '#9b59b6': { border: '#8e44ad', background: '#9b59b6' },
    '#1abc9c': { border: '#16a085', background: '#1abc9c' },
    '#e67e22': { border: '#d35400', background: '#e67e22' },
    '#95a5a6': { border: '#7f8c8d', background: '#95a5a6' },
    '#34495e': { border: '#2c3e50', background: '#34495e' },
  }

  const dsNodes = new DataSet(
    nodes.map(n => ({
      id: n.id,
      label: n.label,
      color: colorMap[n.group] || { border: '#333', background: '#ccc' },
      font: { size: 12, color: '#333' },
      shape: 'dot',
      size: 20,
    }))
  )

  const dsEdges = new DataSet(
    edges.map(e => ({
      from: e.source,
      to: e.target,
      label: e.relation,
      font: { size: 9, color: '#888', align: 'middle' },
      arrows: 'to',
      color: { color: '#999' },
      smooth: { type: 'curvedCW', roundness: 0.2 },
    }))
  )

  const options = {
    layout: { improvedLayout: true },
    physics: { solver: 'forceAtlas2Based', stabilization: { iterations: 100 } },
    interaction: { zoomView: true, dragView: true },
  }

  network = new Network(container.value, { nodes: dsNodes, edges: dsEdges }, options)
}

watch(() => props.graphData, renderGraph, { deep: true })
onMounted(renderGraph)
onBeforeUnmount(() => { if (network) network.destroy() })
</script>

<style scoped>
.graph-viewer {
  background: #fafafa;
  border-radius: 8px;
  padding: 12px;
  margin-top: 8px;
}
h4 {
  font-size: 13px;
  color: #6a1b9a;
  margin-bottom: 8px;
}
.graph-container {
  width: 100%;
  height: 300px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
}
</style>
