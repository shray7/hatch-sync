<template>
  <div class="flex w-full flex-col gap-4">
    <section>
      <h1 class="text-xl font-semibold tracking-tight text-rose-200/90 md:text-2xl">
        Feedings
      </h1>
      <p class="mt-1 text-sm text-slate-400">
        Volume, count and timing of feedings over the last 14 days.
      </p>
    </section>

    <section
      v-if="loaded"
      class="grid grid-cols-1 gap-4 md:grid-cols-2"
    >
      <TimeSeriesChart
        title="Feedings per day"
        :labels="feedingsPerDay.labels"
        :data="feedingsPerDay.values"
      />
      <TimeSeriesChart
        title="Total volume per day (g)"
        :labels="volumePerDay.labels"
        :data="volumePerDay.values"
      />
    </section>

    <section v-if="loaded" class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70">
      <div class="border-b border-slate-800 px-4 py-3 text-sm font-medium">
        Recent feedings
      </div>
      <div class="hidden text-xs text-slate-400 md:grid md:grid-cols-6 md:gap-2 md:px-4 md:py-2">
        <div>Date</div>
        <div>Time</div>
        <div>Method</div>
        <div>Source</div>
        <div>Amount (g)</div>
        <div>Duration</div>
      </div>
      <div class="divide-y divide-slate-800 text-xs">
        <div
          v-for="f in recentFeedings"
          :key="f.id"
          class="grid grid-cols-2 gap-x-2 gap-y-1 px-4 py-2 md:grid-cols-6"
        >
          <div>
            <span class="md:hidden text-slate-400">Date: </span>{{ f.date }}
          </div>
          <div>
            <span class="md:hidden text-slate-400">Time: </span>{{ f.time }}
          </div>
          <div>
            <span class="md:hidden text-slate-400">Method: </span>{{ f.method }}
          </div>
          <div>
            <span class="md:hidden text-slate-400">Source: </span>{{ f.source }}
          </div>
          <div>
            <span class="md:hidden text-slate-400">Amount: </span>{{ f.amount }}
          </div>
          <div>
            <span class="md:hidden text-slate-400">Duration: </span>{{ f.duration }}
          </div>
        </div>
      </div>
    </section>

    <section v-if="!loaded" class="flex items-center justify-center py-16">
      <p class="text-sm text-slate-400">Loading feedings…</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { fetchGrowData } from "../api/grow";
import TimeSeriesChart from "../components/TimeSeriesChart.vue";

const raw = ref(null);
const loaded = ref(false);

function dateKey(dateStr) {
  return dateStr.slice(0, 10);
}

function toDate(dateStr) {
  return new Date(dateStr.replace(" ", "T"));
}

const lastNDaysKeys = (n) => {
  const keys = [];
  const now = new Date();
  for (let i = 0; i < n; i++) {
    const d = new Date(
      Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - i)
    );
    keys.push(d.toISOString().slice(0, 10));
  }
  return keys.reverse();
};

const feedingsPerDay = computed(() => {
  if (!raw.value) return { labels: [], values: [] };
  const keys = lastNDaysKeys(14);
  const counts = {};
  keys.forEach((k) => (counts[k] = 0));
  raw.value.feedings.forEach((f) => {
    const k = dateKey(f.startTime || f.createDate);
    if (k in counts) counts[k] += 1;
  });
  return {
    labels: keys,
    values: keys.map((k) => counts[k] || 0)
  };
});

const volumePerDay = computed(() => {
  if (!raw.value) return { labels: [], values: [] };
  const keys = lastNDaysKeys(14);
  const totals = {};
  keys.forEach((k) => (totals[k] = 0));
  raw.value.feedings.forEach((f) => {
    const k = dateKey(f.startTime || f.createDate);
    if (k in totals) totals[k] += f.amount || 0;
  });
  return {
    labels: keys,
    values: keys.map((k) => totals[k] || 0)
  };
});

const recentFeedings = computed(() => {
  if (!raw.value) return [];
  const sorted = [...raw.value.feedings].sort(
    (a, b) =>
      toDate(b.startTime || b.createDate) - toDate(a.startTime || a.createDate)
  );
  return sorted.slice(0, 20).map((f) => {
    const d = toDate(f.startTime || f.createDate);
    const date = d.toISOString().slice(0, 10);
    const time = d.toTimeString().slice(0, 5);
    const durationMin = (f.durationInSeconds || 0) / 60;
    return {
      id: f.id,
      date,
      time,
      method: f.method || "-",
      source: f.source || "-",
      amount: f.amount != null ? f.amount : "-",
      duration: durationMin ? `${durationMin.toFixed(0)} min` : "-"
    };
  });
});

onMounted(async () => {
  const data = await fetchGrowData();
  raw.value = data;
  loaded.value = true;
});
</script>

