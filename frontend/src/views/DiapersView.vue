<template>
  <div class="flex w-full flex-col gap-4">
    <section>
      <h1 class="text-xl font-semibold tracking-tight text-rose-200/90 md:text-2xl">
        Diapers
      </h1>
      <p class="mt-1 text-sm text-slate-400">
        Diaper changes and type breakdown over the last 14 days.
      </p>
    </section>

    <section
      v-if="loaded"
      class="grid grid-cols-1 gap-4 md:grid-cols-2"
    >
      <TimeSeriesChart
        title="Diapers per day"
        :labels="diapersPerDay.labels"
        :data="diapersPerDay.values"
        :moving-average-window="7"
      />
      <ColumnChart
        title="Type breakdown (last 14 days)"
        :labels="typeBreakdownChart.labels"
        :data="typeBreakdownChart.values"
        :backgroundColor="typeBreakdownChart.colors"
      />
    </section>

    <section v-if="loaded" class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70">
      <div class="border-b border-slate-800 px-4 py-3 text-sm font-medium">
        Recent diapers
      </div>
      <div class="divide-y divide-slate-800 text-xs">
        <div
          v-for="d in recentDiapers"
          :key="d.id"
          class="grid grid-cols-2 gap-x-2 gap-y-1 px-4 py-2 md:grid-cols-4"
        >
          <div>
            <span class="md:hidden text-slate-400">Date: </span>{{ d.date }}
          </div>
          <div>
            <span class="md:hidden text-slate-400">Time: </span>{{ d.time }}
          </div>
          <div>
            <span class="md:hidden text-slate-400">Type: </span>{{ d.type }}
          </div>
          <div>
            <span class="md:hidden text-slate-400">Details: </span
            ><span class="truncate">{{ d.details }}</span>
          </div>
        </div>
      </div>
    </section>

    <section v-if="!loaded" class="flex items-center justify-center py-16">
      <p class="text-sm text-slate-400">Loading diapers…</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { fetchGrowData } from "../api/grow";
import {
  dateKey,
  formatDatePST,
  formatTimePST,
  lastNDaysKeysPST,
  toDate
} from "../utils/pst";
import ColumnChart from "../components/ColumnChart.vue";
import TimeSeriesChart from "../components/TimeSeriesChart.vue";

const raw = ref(null);
const loaded = ref(false);

const lastNDaysKeys = (n) => lastNDaysKeysPST(n);

const diapersPerDay = computed(() => {
  if (!raw.value) return { labels: [], values: [] };
  const keys = lastNDaysKeys(14);
  const counts = {};
  keys.forEach((k) => (counts[k] = 0));
  raw.value.diapers.forEach((d) => {
    const k = dateKey(d.diaperDate || d.createDate);
    if (k in counts) counts[k] += 1;
  });
  return {
    labels: keys,
    values: keys.map((k) => counts[k] || 0)
  };
});

const typeBreakdownColors = {
  Wet: "rgba(244, 114, 182, 0.8)",
  Dirty: "rgba(252, 211, 77, 0.8)",
  Both: "rgba(253, 164, 175, 0.8)"
};

const typeBreakdownChart = computed(() => {
  if (!raw.value) return { labels: [], values: [], colors: [] };
  const keys = new Set(lastNDaysKeys(14));
  const counts = { Wet: 0, Dirty: 0, Both: 0 };
  raw.value.diapers.forEach((d) => {
    const k = dateKey(d.diaperDate || d.createDate);
    if (!keys.has(k)) return;
    const t = d.diaperType || "Wet";
    if (!(t in counts)) counts[t] = 0;
    counts[t] += 1;
  });
  const entries = Object.entries(counts).filter(([, c]) => c > 0);
  return {
    labels: entries.map(([t]) => t),
    values: entries.map(([, c]) => c),
    colors: entries.map(([t]) => typeBreakdownColors[t] || "rgba(148, 163, 184, 0.8)")
  };
});

const recentDiapers = computed(() => {
  if (!raw.value) return [];
  const sorted = [...raw.value.diapers].sort(
    (a, b) =>
      toDate(b.diaperDate || b.createDate) -
      toDate(a.diaperDate || a.createDate)
  );
  return sorted.slice(0, 30).map((d) => {
    const dateStr = d.diaperDate || d.createDate;
    return {
      id: d.id,
      date: formatDatePST(dateStr),
      time: formatTimePST(dateStr),
      type: d.diaperType || "-",
      details: d.details || ""
    };
  });
});

onMounted(async () => {
  const data = await fetchGrowData();
  raw.value = data;
  loaded.value = true;
});
</script>

