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
      class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6"
    >
      <StatCard
        label="Feedings today"
        :value="feedingsToday"
        sub="Today"
        :animate-count="true"
        class="animate-fade-slide-up delay-75"
      />
      <StatCard
        label="Last feeding"
        :value="lastFeedingFormatted"
        class="animate-fade-slide-up delay-150"
      />
      <StatCard
        label="7-day avg feedings"
        :value="sevenDayAvgFeedingsFormatted"
        sub="Per day"
        class="animate-fade-slide-up delay-200"
      />
      <StatCard
        label="Avg feeding duration"
        :value="avgFeedingDurationFormatted"
        sub="Last 7 days"
        class="animate-fade-slide-up delay-300"
      />
      <StatCard
        label="Avg between feedings"
        :value="avgBetweenFeedingsFormatted"
        sub="Last 7 days"
        class="animate-fade-slide-up delay-500"
      />
      <StatCard
        label="Most active period"
        :value="mostActivePeriod"
        sub="Last 14 days"
        class="animate-fade-slide-up delay-500"
      />
    </section>

    <section
      v-if="loaded"
      class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
    >
      <TimeSeriesChart
        class="animate-fade-slide-up"
        title="Feedings per day"
        :labels="feedingsPerDay.labels.map(shortChartLabel)"
        :data="feedingsPerDay.values"
        :moving-average-window="7"
        :x-axis-rotation="45"
      />
      <TimeSeriesChart
        class="animate-fade-slide-up"
        title="Total volume per day (g)"
        :labels="volumePerDay.labels.map(shortChartLabel)"
        :data="volumePerDay.values"
        :moving-average-window="7"
        :x-axis-rotation="45"
      />
      <TimeSeriesChart
        class="animate-fade-slide-up"
        title="Total duration per day (hr)"
        :labels="durationPerDay.labels.map(shortChartLabel)"
        :data="durationPerDay.values"
        :moving-average-window="7"
        :x-axis-rotation="45"
      />
      <ColumnChart
        class="animate-fade-slide-up"
        title="Method breakdown (last 14 days)"
        :labels="methodBreakdown.labels"
        :data="methodBreakdown.values"
        :backgroundColor="methodBreakdown.colors"
      />
      <ColumnChart
        class="animate-fade-slide-up"
        title="Feeding time (by time of day)"
        :labels="timeByPeriod.labels"
        :data="timeByPeriod.values"
        :backgroundColor="timeByPeriod.colors"
        horizontal
      />
      <ColumnChart
        v-if="sourceBreakdown.labels.length > 0"
        class="animate-fade-slide-up"
        title="Source breakdown (last 14 days)"
        :labels="sourceBreakdown.labels"
        :data="sourceBreakdown.values"
        :backgroundColor="sourceBreakdown.colors"
        horizontal
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
import {
  dateKey,
  formatDatePST,
  formatTimePST,
  lastNDaysKeysPST,
  shortChartLabel,
  todayKeyPST,
  toDate
} from "../utils/pst";
import ColumnChart from "../components/ColumnChart.vue";
import StatCard from "../components/StatCard.vue";
import TimeSeriesChart from "../components/TimeSeriesChart.vue";

const raw = ref(null);
const loaded = ref(false);

const lastNDaysKeys = (n) => lastNDaysKeysPST(n);
const todayKey = computed(() => todayKeyPST());
const sevenDayKeysSet = computed(() => new Set(lastNDaysKeys(7)));

const feedingsToday = computed(() => {
  if (!raw.value) return 0;
  const dKey = todayKey.value;
  return raw.value.feedings.filter(
    (f) => dateKey(f.startTime || f.createDate) === dKey
  ).length;
});

const lastFeedingFormatted = computed(() => {
  if (!raw.value?.feedings?.length) return "–";
  const sorted = [...raw.value.feedings].sort(
    (a, b) => toDate(b.startTime || b.createDate) - toDate(a.startTime || a.createDate)
  );
  const last = toDate(sorted[0].startTime || sorted[0].createDate);
  const now = Date.now();
  const diffMs = now - last.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMin / 60);
  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ${diffMin % 60}m ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
});

const sevenDayAvgFeedingsFormatted = computed(() => {
  if (!raw.value) return "–";
  const keys = lastNDaysKeys(7);
  let total = 0;
  raw.value.feedings.forEach((f) => {
    const k = dateKey(f.startTime || f.createDate);
    if (keys.includes(k)) total += 1;
  });
  const avg = total / 7;
  return avg % 1 === 0 ? String(avg) : avg.toFixed(1);
});

const avgFeedingDurationFormatted = computed(() => {
  if (!raw.value?.feedings?.length) return "–";
  const keys = sevenDayKeysSet.value;
  let totalSec = 0;
  let count = 0;
  raw.value.feedings.forEach((f) => {
    const k = dateKey(f.startTime || f.createDate);
    if (!keys.has(k)) return;
    const dur = f.durationInSeconds || 0;
    if (dur > 0) {
      totalSec += dur;
      count += 1;
    }
  });
  if (count === 0) return "–";
  const avgMin = totalSec / count / 60;
  return avgMin < 1 ? "<1 min" : `${Math.round(avgMin)} min`;
});

const avgBetweenFeedingsFormatted = computed(() => {
  if (!raw.value?.feedings?.length) return "–";
  const keys = sevenDayKeysSet.value;
  const sorted = [...raw.value.feedings]
    .filter((f) => keys.has(dateKey(f.startTime || f.createDate)))
    .map((f) => toDate(f.startTime || f.createDate).getTime())
    .sort((a, b) => a - b);
  if (sorted.length < 2) return "–";
  let totalHr = 0;
  for (let i = 1; i < sorted.length; i++) {
    totalHr += (sorted[i] - sorted[i - 1]) / (1000 * 60 * 60);
  }
  const avgHr = totalHr / (sorted.length - 1);
  if (avgHr < 1) return `${Math.round(avgHr * 60)} min`;
  return `${avgHr.toFixed(1)} h`;
});

const mostActivePeriod = computed(() => {
  if (!raw.value) return "–";
  const tp = timeByPeriod.value;
  if (!tp.values?.length) return "–";
  const maxIdx = tp.values.indexOf(Math.max(...tp.values));
  return timeOfDayBuckets[maxIdx]?.shortLabel ?? tp.labels[maxIdx] ?? "–";
});

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

const keys14 = computed(() => (raw.value ? lastNDaysKeys(14) : []));
const keys14Set = computed(() => new Set(keys14.value));

const methodColors = { Bottle: "rgba(251, 113, 133, 0.8)", Nursing: "rgba(253, 164, 175, 0.8)" };
const methodBreakdown = computed(() => {
  if (!raw.value) return { labels: [], values: [], colors: [] };
  const keys = keys14Set.value;
  const counts = {};
  raw.value.feedings.forEach((f) => {
    const k = dateKey(f.startTime || f.createDate);
    if (!keys.has(k)) return;
    const m = (f.method || "Other").trim() || "Other";
    counts[m] = (counts[m] || 0) + 1;
  });
  const entries = Object.entries(counts).filter(([, c]) => c > 0).sort((a, b) => b[1] - a[1]);
  return {
    labels: entries.map(([m]) => m),
    values: entries.map(([, c]) => c),
    colors: entries.map(([m]) => methodColors[m] || "rgba(148, 163, 184, 0.8)")
  };
});

// Time-of-day buckets (6-hour segments); shortLabel for stat display
const timeOfDayBuckets = [
  { label: "Night (12am–6am)", shortLabel: "Night", start: 0, end: 6, color: "rgba(100, 116, 139, 0.8)" },
  { label: "Morning (6am–12pm)", shortLabel: "Morning", start: 6, end: 12, color: "rgba(251, 191, 36, 0.7)" },
  { label: "Afternoon (12pm–6pm)", shortLabel: "Afternoon", start: 12, end: 18, color: "rgba(251, 113, 133, 0.8)" },
  { label: "Evening (6pm–12am)", shortLabel: "Evening", start: 18, end: 24, color: "rgba(148, 163, 184, 0.7)" }
];
const timeByPeriod = computed(() => {
  if (!raw.value) return { labels: [], values: [], colors: [] };
  const keys = keys14Set.value;
  const counts = timeOfDayBuckets.map(() => 0);
  raw.value.feedings.forEach((f) => {
    const k = dateKey(f.startTime || f.createDate);
    if (!keys.has(k)) return;
    const h = toDate(f.startTime || f.createDate).getHours();
    const idx = timeOfDayBuckets.findIndex((b) => h >= b.start && h < b.end);
    if (idx >= 0) counts[idx] += 1;
  });
  return {
    labels: timeOfDayBuckets.map((b) => b.label),
    values: counts,
    colors: timeOfDayBuckets.map((b) => b.color)
  };
});

const durationPerDay = computed(() => {
  if (!raw.value) return { labels: [], values: [] };
  const keys = lastNDaysKeys(14);
  const totals = {};
  keys.forEach((k) => (totals[k] = 0));
  raw.value.feedings.forEach((f) => {
    const k = dateKey(f.startTime || f.createDate);
    if (k in totals) totals[k] += (f.durationInSeconds || 0) / 3600;
  });
  return {
    labels: keys,
    values: keys.map((k) => Math.round((totals[k] || 0) * 10) / 10)
  };
});

const sourceBreakdown = computed(() => {
  if (!raw.value) return { labels: [], values: [], colors: [] };
  const keys = keys14Set.value;
  const counts = {};
  raw.value.feedings.forEach((f) => {
    const k = dateKey(f.startTime || f.createDate);
    if (!keys.has(k)) return;
    const s = (f.source || "").trim();
    if (!s) return;
    counts[s] = (counts[s] || 0) + 1;
  });
  const entries = Object.entries(counts).filter(([, c]) => c > 0).sort((a, b) => b[1] - a[1]);
  const pickColor = (s) => {
    const lower = s.toLowerCase();
    if (lower.includes("left")) return "rgba(251, 113, 133, 0.8)";
    if (lower.includes("right")) return "rgba(253, 164, 175, 0.8)";
    return "rgba(148, 163, 184, 0.8)";
  };
  return {
    labels: entries.map(([s]) => s),
    values: entries.map(([, c]) => c),
    colors: entries.map(([s]) => pickColor(s))
  };
});

const recentFeedings = computed(() => {
  if (!raw.value) return [];
  const sorted = [...raw.value.feedings].sort(
    (a, b) =>
      toDate(b.startTime || b.createDate) - toDate(a.startTime || a.createDate)
  );
  return sorted.slice(0, 20).map((f) => {
    const dateStr = f.startTime || f.createDate;
    const date = formatDatePST(dateStr);
    const time = formatTimePST(dateStr);
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

