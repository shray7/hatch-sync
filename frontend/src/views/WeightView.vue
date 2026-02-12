<template>
  <div class="flex w-full flex-col gap-4">
    <section>
      <h1 class="text-xl font-semibold tracking-tight text-rose-200/90 md:text-2xl">
        Weight
      </h1>
      <p class="mt-1 text-sm text-slate-400">
        Growth curve and recent weight measurements.
      </p>
    </section>

    <section v-if="loaded" class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <TimeSeriesChart
        title="Weight over time (g)"
        :labels="weightOverTime.labels"
        :data="weightOverTime.values"
      />
      <div class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70 p-4">
        <div class="mb-2 text-sm font-medium text-slate-200">
          Stats
        </div>
        <ul class="space-y-1 text-xs text-slate-300">
          <li>
            <span class="text-slate-400">Latest weight:</span>
            <span class="ml-1 font-semibold">{{ latest?.weight ?? "-" }} g</span>
            <span v-if="latest" class="ml-1 text-slate-500">({{ latest.date }})</span>
          </li>
          <li v-if="gainPerWeek !== null">
            <span class="text-slate-400">Approx. gain per week:</span>
            <span class="ml-1 font-semibold">{{ gainPerWeek.toFixed(0) }} g</span>
          </li>
        </ul>
      </div>
    </section>

    <section v-if="loaded" class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70">
      <div class="border-b border-slate-800 px-4 py-3 text-sm font-medium">
        Measurements
      </div>
      <div class="divide-y divide-slate-800 text-xs">
        <div
          v-for="w in allWeights"
          :key="w.id"
          class="grid grid-cols-2 gap-x-2 gap-y-1 px-4 py-2 md:grid-cols-3"
        >
          <div>
            <span class="md:hidden text-slate-400">Date: </span>{{ w.date }}
          </div>
          <div>
            <span class="md:hidden text-slate-400">Time: </span>{{ w.time }}
          </div>
          <div>
            <span class="md:hidden text-slate-400">Weight: </span
            >{{ w.weight }} g
          </div>
        </div>
      </div>
    </section>

    <section v-if="!loaded" class="flex items-center justify-center py-16">
      <p class="text-sm text-slate-400">Loading weight…</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { fetchGrowData } from "../api/grow";
import TimeSeriesChart from "../components/TimeSeriesChart.vue";

const raw = ref(null);
const loaded = ref(false);

function toDate(dateStr) {
  return new Date(dateStr.replace(" ", "T"));
}

const weightOverTime = computed(() => {
  if (!raw.value) return { labels: [], values: [] };
  const sorted = [...raw.value.weights].sort(
    (a, b) =>
      toDate(a.weightDate || a.createDate) -
      toDate(b.weightDate || b.createDate)
  );
  return {
    labels: sorted.map((w) => (w.weightDate || w.createDate).slice(0, 10)),
    values: sorted.map((w) => w.weight)
  };
});

const allWeights = computed(() => {
  if (!raw.value) return [];
  const sorted = [...raw.value.weights].sort(
    (a, b) =>
      toDate(b.weightDate || b.createDate) -
      toDate(a.weightDate || a.createDate)
  );
  return sorted.map((w) => {
    const d = toDate(w.weightDate || w.createDate);
    return {
      id: w.id,
      date: d.toISOString().slice(0, 10),
      time: d.toTimeString().slice(0, 5),
      weight: w.weight
    };
  });
});

const latest = computed(() => {
  const list = allWeights.value;
  return list.length ? list[0] : null;
});

const gainPerWeek = computed(() => {
  const list = allWeights.value;
  if (list.length < 2) return null;
  const oldest = list[list.length - 1];
  const newest = list[0];
  const days =
    (toDate(newest.date) - toDate(oldest.date)) / (1000 * 60 * 60 * 24);
  if (days <= 0) return null;
  const gainPerDay = (newest.weight - oldest.weight) / days;
  return gainPerDay * 7;
});

onMounted(async () => {
  const data = await fetchGrowData();
  raw.value = data;
  loaded.value = true;
});
</script>

