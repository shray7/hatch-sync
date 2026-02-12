<template>
  <div class="flex w-full flex-col gap-4">
    <section>
      <h1 class="text-xl font-semibold tracking-tight text-rose-200/90 md:text-2xl">
        Dashboard
      </h1>
      <p class="mt-1 text-sm text-slate-400">
        Overview of diapers, feedings, sleep and weight over the last 7 days.
      </p>
    </section>

    <section
      v-if="loaded && raw"
      class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
    >
      <StatCard
        label="Diapers today"
        :value="todayCounts.diapers"
        :sub="`Last 7 days avg: ${sevenDayAverages.diapers.toFixed(1)}`"
      />
      <StatCard
        label="Feedings today"
        :value="todayCounts.feedings"
        :sub="`Last 7 days avg: ${sevenDayAverages.feedings.toFixed(1)}`"
      />
      <StatCard
        label="Total sleep today (h)"
        :value="todaySleepHours.toFixed(1)"
        :sub="`Last 7 days avg: ${sevenDayAverages.sleepHours.toFixed(1)}h`"
      />
      <StatCard
        label="Last weight (g)"
        :value="lastWeight"
        :sub="lastWeightDate"
      />
    </section>

    <section
      v-if="loaded && raw"
      class="grid grid-cols-1 gap-4 md:grid-cols-2"
    >
      <TimeSeriesChart
        title="Diapers per day (last 14 days)"
        :labels="diapersPerDay.labels"
        :data="diapersPerDay.values"
      />
      <TimeSeriesChart
        title="Feedings per day (last 14 days)"
        :labels="feedingsPerDay.labels"
        :data="feedingsPerDay.values"
      />
    </section>

    <section v-if="loaded && raw" class="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <TimeSeriesChart
        title="Total sleep per day (hours)"
        :labels="sleepPerDay.labels"
        :data="sleepPerDay.values"
      />
      <TimeSeriesChart
        title="Weight over time (g)"
        :labels="weightOverTime.labels"
        :data="weightOverTime.values"
      />
    </section>

    <section v-if="dataError" class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70 p-4">
      <p class="text-sm text-rose-300">Dashboard data: {{ dataError }}</p>
      <p class="mt-2 text-xs text-slate-400">Check that the API is reachable and HATCH_EMAIL/HATCH_PASSWORD are set. The first load can take up to a minute if the API was idle.</p>
    </section>

    <section v-else-if="!loaded" class="flex items-center justify-center py-16">
      <p class="text-sm text-slate-400">Loading live data…</p>
    </section>

    <section class="mt-6">
      <h2 class="text-lg font-semibold tracking-tight text-rose-200/90 md:text-xl">
        Photos (last 7 days)
      </h2>
      <p class="mt-1 text-sm text-slate-400">
        Daily photos from Hatch Grow.
      </p>
    </section>

    <section
      v-if="photosError"
      class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70 p-4"
    >
      <p class="text-sm text-rose-300">{{ photosError }}</p>
      <p class="mt-2 text-xs text-slate-400">
        Set HATCH_EMAIL and HATCH_PASSWORD for the API to load photos.
      </p>
    </section>

    <section
      v-else-if="photosLoaded && photosLast7Days.length > 0"
      class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:gap-4"
    >
      <div
        v-for="photo in photosLast7Days"
        :key="photo.createDate + (photoUrl(photo) || '')"
        class="flex flex-col overflow-hidden rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70"
      >
        <a
          v-if="photoUrl(photo)"
          :href="photoUrl(photo)"
          target="_blank"
          rel="noopener noreferrer"
          class="block aspect-square w-full overflow-hidden bg-slate-800"
        >
          <img
            v-if="!failedImages.has(photo.createDate)"
            :src="photoUrl(photo)"
            :alt="'Photo ' + photo.createDate"
            class="h-full w-full object-cover"
            loading="lazy"
            @error="onPhotoError(photo)"
          />
          <div
            v-else
            class="flex h-full w-full flex-col items-center justify-center gap-1 p-2 text-center text-xs text-slate-400"
          >
            <span>Image unavailable</span>
            <span class="text-slate-500">Link may have expired.</span>
          </div>
        </a>
        <div
          v-else
          class="flex aspect-square w-full items-center justify-center bg-slate-800 p-2 text-xs text-slate-500"
        >
          No preview URL
        </div>
        <div class="px-2 py-2 text-xs text-slate-400">
          {{ formatPhotoDate(photo.createDate) }}
        </div>
      </div>
    </section>

    <section
      v-else-if="photosLoaded && photosLast7Days.length === 0"
      class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70 p-8 text-center"
    >
      <p class="text-sm text-slate-400">No photos in the last 7 days.</p>
    </section>

    <section v-if="!photosLoaded && !photosError" class="flex items-center justify-center py-8">
      <p class="text-sm text-slate-400">Loading photos…</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { fetchGrowData, fetchPhotos } from "../api/grow";
import StatCard from "../components/StatCard.vue";
import TimeSeriesChart from "../components/TimeSeriesChart.vue";

const raw = ref(null);
const loaded = ref(false);
const dataError = ref(null);
const photos = ref([]);
const photosLoaded = ref(false);
const photosError = ref(null);
const failedImages = ref(new Set());

function dateKey(dateStr) {
  return dateStr.slice(0, 10);
}

function toDate(dateStr) {
  return new Date(dateStr.replace(" ", "T"));
}

function hoursBetween(startStr, endStr) {
  const start = toDate(startStr);
  const end = toDate(endStr);
  return (end - start) / (1000 * 60 * 60);
}

const todayKey = computed(() => {
  const now = new Date();
  return now.toISOString().slice(0, 10);
});

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

const todayCounts = computed(() => {
  if (!raw.value) return { diapers: 0, feedings: 0 };
  const dKey = todayKey.value;
  const diapersToday = raw.value.diapers.filter(
    (d) => dateKey(d.diaperDate || d.createDate) === dKey
  ).length;
  const feedingsToday = raw.value.feedings.filter(
    (f) => dateKey(f.startTime || f.createDate) === dKey
  ).length;
  return { diapers: diapersToday, feedings: feedingsToday };
});

const todaySleepHours = computed(() => {
  if (!raw.value) return 0;
  const dKey = todayKey.value;
  return raw.value.sleeps
    .filter((s) => dateKey(s.startTime || s.createDate) === dKey)
    .reduce(
      (sum, s) =>
        sum + hoursBetween(s.startTime || s.createDate, s.endTime || s.updateDate),
      0
    );
});

const sevenDayAverages = computed(() => {
  if (!raw.value) {
    return { diapers: 0, feedings: 0, sleepHours: 0 };
  }
  const keys = lastNDaysKeys(7);
  const perDay = {
    diapers: {},
    feedings: {},
    sleepHours: {}
  };
  keys.forEach((k) => {
    perDay.diapers[k] = 0;
    perDay.feedings[k] = 0;
    perDay.sleepHours[k] = 0;
  });

  raw.value.diapers.forEach((d) => {
    const k = dateKey(d.diaperDate || d.createDate);
    if (k in perDay.diapers) perDay.diapers[k] += 1;
  });
  raw.value.feedings.forEach((f) => {
    const k = dateKey(f.startTime || f.createDate);
    if (k in perDay.feedings) perDay.feedings[k] += 1;
  });
  raw.value.sleeps.forEach((s) => {
    const k = dateKey(s.startTime || s.createDate);
    if (k in perDay.sleepHours) {
      perDay.sleepHours[k] += hoursBetween(
        s.startTime || s.createDate,
        s.endTime || s.updateDate
      );
    }
  });

  const avg = (obj) =>
    keys.reduce((sum, k) => sum + (obj[k] || 0), 0) / keys.length || 0;
  return {
    diapers: avg(perDay.diapers),
    feedings: avg(perDay.feedings),
    sleepHours: avg(perDay.sleepHours)
  };
});

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

const weightOverTime = computed(() => {
  if (!raw.value) return { labels: [], values: [] };
  const sorted = [...raw.value.weights].sort(
    (a, b) =>
      new Date(a.weightDate || a.createDate) -
      new Date(b.weightDate || b.createDate)
  );
  return {
    labels: sorted.map((w) => dateKey(w.weightDate || w.createDate)),
    values: sorted.map((w) => w.weight)
  };
});

const lastWeight = computed(() => {
  if (!raw.value || raw.value.weights.length === 0) return "-";
  const sorted = [...raw.value.weights].sort(
    (a, b) =>
      new Date(a.weightDate || a.createDate) -
      new Date(b.weightDate || b.createDate)
  );
  return sorted[sorted.length - 1].weight;
});

const lastWeightDate = computed(() => {
  if (!raw.value || raw.value.weights.length === 0) return "";
  const sorted = [...raw.value.weights].sort(
    (a, b) =>
      new Date(a.weightDate || a.createDate) -
      new Date(b.weightDate || b.createDate)
  );
  const d = sorted[sorted.length - 1].weightDate || sorted[sorted.length - 1].createDate;
  return dateKey(d);
});

const sevenDayKeysSet = computed(() => new Set(lastNDaysKeys(7)));

const photosLast7Days = computed(() => {
  const keys = sevenDayKeysSet.value;
  return [...photos.value]
    .filter((p) => keys.has(dateKey(p.createDate || "")))
    .sort((a, b) => new Date(b.createDate || 0) - new Date(a.createDate || 0));
});

function photoUrl(photo) {
  return photo?.cutDownloadUrl ?? photo?.cut_download_url ?? null;
}

function onPhotoError(photo) {
  if (photo?.createDate) failedImages.value.add(photo.createDate);
  failedImages.value = new Set(failedImages.value);
}

function formatPhotoDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr.replace(" ", "T"));
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

onMounted(async () => {
  try {
    const data = await fetchGrowData();
    raw.value = data;
  } catch (e) {
    const detail = e.response?.data?.detail ?? e.message;
    dataError.value = typeof detail === "string" ? detail : "Failed to load data.";
  } finally {
    loaded.value = true;
  }

  try {
    const photoData = await fetchPhotos();
    const list = photoData?.photos ?? photoData?.payload?.photos ?? [];
    photos.value = Array.isArray(list) ? list : [];
  } catch (e) {
    const detail = e.response?.data?.detail ?? e.message;
    photosError.value = typeof detail === "string" ? detail : "Failed to load photos.";
  } finally {
    photosLoaded.value = true;
  }
});
</script>

