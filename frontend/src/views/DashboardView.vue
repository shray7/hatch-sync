<template>
  <div class="flex w-full flex-col gap-6 md:gap-8">
    <section class="border-b border-slate-700/50 pb-6">
      <h1 class="text-2xl font-semibold tracking-tight text-slate-100 md:text-3xl">
        Dashboard
      </h1>
      <p class="mt-2 text-sm text-slate-400 md:text-base">
        Overview of diapers, feedings, and weight over the last 7 days.
      </p>
    </section>

    <section
      v-if="loaded && raw"
      class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5"
    >
      <StatCard
        label="Diapers today"
        :value="todayCounts.diapers"
        :sub="`7-day avg: ${sevenDayAverages.diapers.toFixed(1)}`"
      />
      <StatCard
        label="Feedings today"
        :value="todayCounts.feedings"
        :sub="`7-day avg: ${sevenDayAverages.feedings.toFixed(1)}`"
      />
      <StatCard
        label="Avg between diapers"
        :value="avgDiaperIntervalFormatted"
        sub="Last 7 days"
      />
      <StatCard
        label="Avg between feedings"
        :value="avgFeedingIntervalFormatted"
        sub="Last 7 days"
      />
      <StatCard
        label="Last weight"
        :value="lastWeightFormatted"
        :sub="lastWeightDate"
      />
    </section>

    <section
      v-if="loaded && raw"
      class="grid grid-cols-1 gap-6 lg:grid-cols-3"
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
      <TimeSeriesChart
        v-if="weightOverTime.labels.length > 0"
        title="Weight over time (lb)"
        :labels="weightOverTime.labels"
        :data="weightOverTime.valuesLbs"
      />
    </section>

    <section
      v-if="rateLimitedStale"
      class="rounded-xl border border-amber-800/50 bg-amber-950/20 px-4 py-3"
    >
      <p class="text-sm font-medium text-amber-200">Rate limited; showing cached data.</p>
      <p class="mt-1 text-xs text-slate-400">Hatch temporarily throttled the API. Refresh in a few minutes for fresh data.</p>
    </section>

    <section v-if="dataError" class="rounded-xl border border-rose-900/40 bg-slate-900/50 px-4 py-4">
      <p class="text-sm font-medium text-rose-300">Dashboard data: {{ dataError }}</p>
      <p class="mt-2 text-xs text-slate-400">Check that the API is reachable and HATCH_EMAIL/HATCH_PASSWORD are set. First load can take up to 2 minutes if the API was idle.</p>
    </section>

    <section v-else-if="!loaded" class="flex flex-col items-center justify-center gap-2 py-20">
      <div class="h-8 w-8 animate-spin rounded-full border-2 border-slate-600 border-t-rose-400" />
      <p class="text-sm text-slate-400">Loading live data…</p>
      <p class="text-xs text-slate-500">First load can take up to 2 minutes.</p>
    </section>

    <section class="border-t border-slate-700/50 pt-8">
      <h2 class="text-xl font-semibold tracking-tight text-slate-100 md:text-2xl">
        Media (last 7 days)
      </h2>
      <p class="mt-2 text-sm text-slate-400">
        Recent photos and videos from Hatch Grow and uploads.
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
      class="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:gap-5"
    >
      <div
        v-for="photo in photosLast7Days"
        :key="photo.createDate + (photoUrl(photo) || '')"
        class="flex flex-col overflow-hidden rounded-xl border border-slate-700/50 bg-slate-800/40 shadow-lg transition hover:border-slate-600/60"
      >
        <a
          v-if="photoUrl(photo) && !isVideo(photo)"
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
          v-else-if="photoUrl(photo) && isVideo(photo)"
          class="block aspect-square w-full overflow-hidden bg-slate-800"
        >
          <video
            v-if="!failedImages.has(photo.createDate)"
            :src="photoUrl(photo)"
            class="h-full w-full object-cover"
            controls
            playsinline
            preload="metadata"
            @error="onPhotoError(photo)"
          />
          <div
            v-else
            class="flex h-full w-full flex-col items-center justify-center gap-1 p-2 text-center text-xs text-slate-400"
          >
            <span>Video unavailable</span>
          </div>
        </div>
        <div
          v-else
          class="flex aspect-square w-full items-center justify-center bg-slate-800 p-2 text-xs text-slate-500"
        >
          No preview URL
        </div>
        <div class="px-3 py-2 text-xs text-slate-400">
          {{ formatPhotoDate(photo.createDate) }}
        </div>
      </div>
    </section>

    <section
      v-else-if="photosLoaded && photosLast7Days.length === 0"
      class="rounded-xl border border-slate-700/50 bg-slate-800/30 px-6 py-12 text-center"
    >
      <p class="text-sm text-slate-400">No photos or videos in the last 7 days.</p>
    </section>

    <section v-if="!photosLoaded && !photosError" class="flex items-center justify-center gap-2 py-12">
      <div class="h-5 w-5 animate-spin rounded-full border-2 border-slate-600 border-t-rose-400" />
      <p class="text-sm text-slate-400">Loading media…</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { fetchGrowData, fetchPhotos } from "../api/grow";
import {
  dateKey,
  formatDateTimePST,
  lastNDaysKeysPST,
  todayKeyPST
} from "../utils/pst";
import { formatWeightLbsOz, gramsToLbs } from "../utils/weight";
import StatCard from "../components/StatCard.vue";
import TimeSeriesChart from "../components/TimeSeriesChart.vue";

const raw = ref(null);
const loaded = ref(false);
const dataError = ref(null);
const photos = ref([]);
const photosLoaded = ref(false);
const photosError = ref(null);
const failedImages = ref(new Set());
const rateLimitedStale = ref(false);

function photoUrl(photo) {
  if (!photo?.photoKey || !photo?.babyId) return null;
  const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";
  const params = new URLSearchParams({
    baby_id: String(photo.babyId),
    key: photo.photoKey
  });
  return `${apiBase}/photos/image?${params.toString()}`;
}

function isVideo(photo) {
  return (photo?.mediaType || photo?.media_type || "").toLowerCase() === "video";
}

const todayKey = computed(() => todayKeyPST());

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

const sevenDayAverages = computed(() => {
  if (!raw.value) {
    return { diapers: 0, feedings: 0 };
  }
  const keys = lastNDaysKeysPST(7);
  const perDay = { diapers: {}, feedings: {} };
  keys.forEach((k) => {
    perDay.diapers[k] = 0;
    perDay.feedings[k] = 0;
  });

  raw.value.diapers.forEach((d) => {
    const k = dateKey(d.diaperDate || d.createDate);
    if (k in perDay.diapers) perDay.diapers[k] += 1;
  });
  raw.value.feedings.forEach((f) => {
    const k = dateKey(f.startTime || f.createDate);
    if (k in perDay.feedings) perDay.feedings[k] += 1;
  });

  const avg = (obj) =>
    keys.reduce((sum, k) => sum + (obj[k] || 0), 0) / keys.length || 0;
  return {
    diapers: avg(perDay.diapers),
    feedings: avg(perDay.feedings)
  };
});

/** Average time between diaper changes (hours) over last 7 days. */
const avgDiaperIntervalHours = computed(() => {
  if (!raw.value?.diapers?.length) return null;
  const keys = sevenDayKeysSet.value;
  const sorted = [...raw.value.diapers]
    .filter((d) => keys.has(dateKey(d.diaperDate || d.createDate)))
    .map((d) => new Date(d.diaperDate || d.createDate).getTime())
    .sort((a, b) => a - b);
  if (sorted.length < 2) return null;
  const intervals = [];
  for (let i = 1; i < sorted.length; i++) {
    intervals.push((sorted[i] - sorted[i - 1]) / (1000 * 60 * 60));
  }
  return intervals.reduce((s, h) => s + h, 0) / intervals.length;
});

/** Average time between feedings (hours) over last 7 days. */
const avgFeedingIntervalHours = computed(() => {
  if (!raw.value?.feedings?.length) return null;
  const keys = sevenDayKeysSet.value;
  const sorted = [...raw.value.feedings]
    .filter((f) => keys.has(dateKey(f.startTime || f.createDate)))
    .map((f) => new Date(f.startTime || f.createDate).getTime())
    .sort((a, b) => a - b);
  if (sorted.length < 2) return null;
  const intervals = [];
  for (let i = 1; i < sorted.length; i++) {
    intervals.push((sorted[i] - sorted[i - 1]) / (1000 * 60 * 60));
  }
  return intervals.reduce((s, h) => s + h, 0) / intervals.length;
});

function formatIntervalHours(hours) {
  if (hours == null || !Number.isFinite(hours)) return "–";
  if (hours < 1) return `${(hours * 60).toFixed(0)} m`;
  return `${hours.toFixed(1)} h`;
}

const avgDiaperIntervalFormatted = computed(() =>
  formatIntervalHours(avgDiaperIntervalHours.value)
);
const avgFeedingIntervalFormatted = computed(() =>
  formatIntervalHours(avgFeedingIntervalHours.value)
);

const diapersPerDay = computed(() => {
  if (!raw.value) return { labels: [], values: [] };
  const keys = lastNDaysKeysPST(14);
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
  const keys = lastNDaysKeysPST(14);
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

const weightOverTime = computed(() => {
  if (!raw.value) return { labels: [], values: [], valuesLbs: [] };
  const sorted = [...raw.value.weights].sort(
    (a, b) =>
      new Date(a.weightDate || a.createDate) -
      new Date(b.weightDate || b.createDate)
  );
  return {
    labels: sorted.map((w) => dateKey(w.weightDate || w.createDate)),
    values: sorted.map((w) => w.weight),
    valuesLbs: sorted.map((w) => gramsToLbs(w.weight))
  };
});

const lastWeight = computed(() => {
  if (!raw.value || raw.value.weights.length === 0) return null;
  const sorted = [...raw.value.weights].sort(
    (a, b) =>
      new Date(a.weightDate || a.createDate) -
      new Date(b.weightDate || b.createDate)
  );
  return sorted[sorted.length - 1].weight;
});

const lastWeightFormatted = computed(() =>
  lastWeight.value != null ? formatWeightLbsOz(lastWeight.value) : "–"
);

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

const sevenDayKeysSet = computed(() => new Set(lastNDaysKeysPST(7)));

const photosLast7Days = computed(() => {
  const keys = sevenDayKeysSet.value;
  return [...photos.value]
    .filter((p) => keys.has(dateKey(p.createDate || "")))
    .sort((a, b) => new Date(b.createDate || 0) - new Date(a.createDate || 0));
});

function onPhotoError(photo) {
  if (photo?.createDate) failedImages.value.add(photo.createDate);
  failedImages.value = new Set(failedImages.value);
}

function formatPhotoDate(dateStr) {
  return formatDateTimePST(dateStr);
}

onMounted(() => {
  // Load data and photos in parallel; update UI as each returns (don't wait for both)
  fetchGrowData()
    .then((data) => {
      raw.value = data;
      if (data?.rateLimitedStale) rateLimitedStale.value = true;
    })
    .catch((e) => {
      const detail = e.response?.data?.detail ?? e.message;
      dataError.value = typeof detail === "string" ? detail : "Failed to load data.";
    })
    .finally(() => {
      loaded.value = true;
    });

  fetchPhotos()
    .then((photoData) => {
      if (photoData?.rateLimitedStale) rateLimitedStale.value = true;
      const list = photoData?.photos ?? photoData?.payload?.photos ?? [];
      photos.value = Array.isArray(list) ? list : [];
    })
    .catch((e) => {
      const detail = e.response?.data?.detail ?? e.message;
      photosError.value = typeof detail === "string" ? detail : "Failed to load photos.";
    })
    .finally(() => {
      photosLoaded.value = true;
    });
});
</script>

