<template>
  <div class="flex w-full flex-col gap-4">
    <section>
      <h1 class="text-xl font-semibold tracking-tight text-rose-200/90 md:text-2xl">
        Sleep
      </h1>
      <p class="mt-1 text-sm text-slate-400">
        Total sleep per day and recent sleep sessions.
      </p>
    </section>

    <section
      v-if="loaded"
      class="grid grid-cols-1 gap-4 md:grid-cols-2"
    >
      <TimeSeriesChart
        title="Total sleep per day (hours)"
        :labels="sleepPerDay.labels"
        :data="sleepPerDay.values"
      />
      <TimeSeriesChart
        title="Naps per day"
        :labels="napsPerDay.labels"
        :data="napsPerDay.values"
      />
    </section>

    <section v-if="loaded" class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70">
      <div class="border-b border-slate-800 px-4 py-3 text-sm font-medium">
        Recent sleep sessions
      </div>
      <div class="divide-y divide-slate-800 text-xs">
        <div
          v-for="s in recentSleeps"
          :key="s.id"
          class="grid grid-cols-2 gap-x-2 gap-y-1 px-4 py-2 md:grid-cols-5"
        >
          <div>
            <span class="md:hidden text-slate-400">Date: </span>{{ s.date }}
          </div>
          <div>
            <span class="md:hidden text-slate-400">Start: </span>{{ s.start }}
          </div>
          <div>
            <span class="md:hidden text-slate-400">End: </span>{{ s.end }}
          </div>
          <div>
            <span class="md:hidden text-slate-400">Duration: </span
            >{{ s.duration }}
          </div>
          <div>
            <span class="md:hidden text-slate-400">Type: </span>{{ s.type }}
          </div>
        </div>
      </div>
    </section>

    <section v-if="!loaded" class="flex items-center justify-center py-16">
      <p class="text-sm text-slate-400">Loading sleep…</p>
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

function dateKey(dateStr) {
  return dateStr.slice(0, 10);
}

function hoursBetween(startStr, endStr) {
  const start = toDate(startStr);
  const end = toDate(endStr);
  return (end - start) / (1000 * 60 * 60);
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

const sleepPerDay = computed(() => {
  if (!raw.value) return { labels: [], values: [] };
  const keys = lastNDaysKeys(14);
  const totals = {};
  keys.forEach((k) => (totals[k] = 0));
  raw.value.sleeps.forEach((s) => {
    const k = dateKey(s.startTime || s.createDate);
    if (k in totals) {
      totals[k] += hoursBetween(
        s.startTime || s.createDate,
        s.endTime || s.updateDate
      );
    }
  });
  return {
    labels: keys,
    values: keys.map((k) => Number(totals[k]?.toFixed(2) || 0))
  };
});

const napsPerDay = computed(() => {
  if (!raw.value) return { labels: [], values: [] };
  const keys = lastNDaysKeys(14);
  const counts = {};
  keys.forEach((k) => (counts[k] = 0));
  raw.value.sleeps.forEach((s) => {
    const duration = hoursBetween(
      s.startTime || s.createDate,
      s.endTime || s.updateDate
    );
    const isNap = duration < 4; // rough heuristic
    const k = dateKey(s.startTime || s.createDate);
    if (isNap && k in counts) counts[k] += 1;
  });
  return {
    labels: keys,
    values: keys.map((k) => counts[k] || 0)
  };
});

const recentSleeps = computed(() => {
  if (!raw.value) return [];
  const sorted = [...raw.value.sleeps].sort(
    (a, b) =>
      toDate(b.startTime || b.createDate) -
      toDate(a.startTime || a.createDate)
  );
  return sorted.slice(0, 20).map((s) => {
    const start = toDate(s.startTime || s.createDate);
    const end = toDate(s.endTime || s.updateDate);
    const durationH = (end - start) / (1000 * 60 * 60);
    const isNap = durationH < 4;
    return {
      id: s.id,
      date: start.toISOString().slice(0, 10),
      start: start.toTimeString().slice(0, 5),
      end: end.toTimeString().slice(0, 5),
      duration: `${durationH.toFixed(1)} h`,
      type: isNap ? "Nap" : "Night"
    };
  });
});

onMounted(async () => {
  const data = await fetchGrowData();
  raw.value = data;
  loaded.value = true;
});
</script>

