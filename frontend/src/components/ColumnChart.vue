<template>
  <div class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70 p-4 overflow-hidden">
    <div class="mb-2 text-sm font-medium text-slate-200">
      {{ title }}
    </div>
    <div class="h-48 w-full md:h-64">
      <canvas ref="canvasEl" class="block w-full h-full"></canvas>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from "vue";
import {
  Chart,
  BarController,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip
} from "chart.js";

Chart.register(
  BarController,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip
);

const props = defineProps({
  title: { type: String, required: true },
  labels: { type: Array, required: true },
  data: { type: Array, required: true },
  // Optional array of colors per bar, or single color for all
  backgroundColor: { type: [Array, String], default: "rgba(251, 113, 133, 0.8)" }
});

const canvasEl = ref(null);
let chart = null;

function dataSignature(labels, data) {
  return `${labels?.length ?? 0}-${data?.length ?? 0}-${JSON.stringify(data ?? [])}`;
}

const buildChart = () => {
  if (!canvasEl.value) return;
  if (chart) {
    chart.destroy();
    chart = null;
  }
  const bgColors = Array.isArray(props.backgroundColor)
    ? [...props.backgroundColor]
    : props.labels?.map(() => props.backgroundColor) ?? [props.backgroundColor];
  chart = new Chart(canvasEl.value, {
    type: "bar",
    data: {
      labels: [...(props.labels || [])],
      datasets: [
        {
          data: [...(props.data || [])],
          backgroundColor: bgColors,
          borderWidth: 0
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: 0 },
      plugins: {
        legend: { display: false },
        tooltip: {
          mode: "index",
          intersect: false
        }
      },
      scales: {
        x: {
          ticks: { color: "#9ca3af", maxRotation: 0, autoSkip: true }
        },
        y: {
          ticks: { color: "#9ca3af", stepSize: 1 },
          grid: { color: "rgba(148, 163, 184, 0.2)" }
        }
      }
    }
  });
};

const updateChartData = () => {
  if (!chart || !props.labels || !props.data) return;
  chart.data.labels = [...props.labels];
  chart.data.datasets[0].data = [...props.data];
  const bgColors = Array.isArray(props.backgroundColor)
    ? [...props.backgroundColor]
    : props.labels?.map(() => props.backgroundColor) ?? [props.backgroundColor];
  chart.data.datasets[0].backgroundColor = bgColors;
  chart.update("none");
};

let lastSig = "";

onMounted(() => {
  buildChart();
  lastSig = dataSignature(props.labels, props.data);
});

watch(
  () => [props.labels, props.data, props.backgroundColor],
  () => {
    const sig = dataSignature(props.labels, props.data);
    if (sig === lastSig) return;
    lastSig = sig;
    if (chart) {
      updateChartData();
    } else if (canvasEl.value) {
      buildChart();
    }
  },
  { deep: true }
);

onBeforeUnmount(() => {
  if (chart) {
    chart.destroy();
    chart = null;
  }
});
</script>
