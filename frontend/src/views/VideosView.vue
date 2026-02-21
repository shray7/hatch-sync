<template>
  <div class="flex w-full flex-col gap-4">
    <section class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 class="text-xl font-semibold tracking-tight text-rose-200/90 md:text-2xl">
          Videos
        </h1>
        <p class="mt-1 text-sm text-slate-400">
          Videos from Hatch Grow and uploads.
          <span v-if="loaded && sortedVideos.length > 0" class="text-rose-300/90">
            {{ sortedVideos.length }} video{{ sortedVideos.length === 1 ? '' : 's' }}.
          </span>
        </p>
      </div>
      <router-link
        v-if="isAdmin"
        to="/admin"
        class="self-start rounded-lg border border-slate-600 bg-slate-800 px-3 py-1.5 text-sm font-medium text-slate-200 hover:bg-slate-700"
      >
        Admin
      </router-link>
    </section>

    <section
      v-if="rateLimitedStale"
      class="rounded-xl border border-amber-900/40 border-slate-800 bg-amber-950/30 p-3"
    >
      <p class="text-sm text-amber-200/90">Rate limited; showing cached data.</p>
      <p class="mt-1 text-xs text-slate-400">Refresh in a few minutes for the latest.</p>
    </section>

    <section v-if="error" class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70 p-4">
      <p class="text-sm text-rose-300">{{ error }}</p>
      <p v-if="is404" class="mt-2 text-xs text-slate-400">
        Restart the API so the /grow/photos endpoint is available.
      </p>
    </section>

    <section
      v-else-if="loaded"
      class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
    >
      <div
        v-for="video in sortedVideos"
        :key="video.createDate + (mediaUrl(video) || '')"
        class="flex flex-col overflow-hidden rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70"
      >
        <div class="relative aspect-video w-full overflow-hidden bg-slate-800">
          <video
            v-if="mediaUrl(video) && !failedVideos.has(video.createDate)"
            :src="mediaUrl(video)"
            class="h-full w-full object-contain"
            controls
            playsinline
            preload="metadata"
            @error="onVideoError(video)"
          />
          <div
            v-else-if="failedVideos.has(video.createDate)"
            class="flex h-full w-full flex-col items-center justify-center gap-1 p-4 text-center text-xs text-slate-400"
          >
            <span>Video unavailable</span>
          </div>
          <div
            v-else
            class="flex h-full w-full items-center justify-center p-4 text-xs text-slate-500"
          >
            No URL
          </div>
        </div>
        <div class="flex items-center justify-between gap-2 px-3 py-2">
          <span class="text-xs text-slate-400">{{ formatDate(video.createDate) }}</span>
          <button
            v-if="isAdmin"
            type="button"
            class="rounded px-2 py-1 text-xs text-rose-300 hover:bg-rose-950/40 hover:text-rose-200"
            :disabled="deletingId === video.photoKey"
            @click="deleteVideo(video)"
          >
            {{ deletingId === video.photoKey ? "Deleting…" : "Delete" }}
          </button>
        </div>
      </div>
    </section>

    <section v-if="loaded && sortedVideos.length === 0" class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70 p-8 text-center">
      <p class="text-sm text-slate-400">No videos yet. Upload from Admin or add in the Hatch Grow app.</p>
    </section>

    <section v-if="!loaded && !error" class="flex items-center justify-center py-16">
      <p class="text-sm text-slate-400">Loading videos…</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { fetchAuthMe } from "../api/auth";
import { deletePhoto, fetchPhotos } from "../api/grow";
import { formatDateTimePST } from "../utils/pst";

const allMedia = ref([]);
const loaded = ref(false);
const error = ref(null);
const failedVideos = ref(new Set());
const rateLimitedStale = ref(false);
const isAdmin = ref(false);
const deletingId = ref(null);

function mediaUrl(item) {
  if (!item?.photoKey || !item?.babyId) return null;
  const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";
  const params = new URLSearchParams({
    baby_id: String(item.babyId),
    key: item.photoKey
  });
  return `${apiBase}/photos/image?${params.toString()}`;
}

function isVideo(item) {
  return (item?.mediaType || item?.media_type || "").toLowerCase() === "video";
}

function onVideoError(video) {
  if (video?.createDate) failedVideos.value.add(video.createDate);
  failedVideos.value = new Set(failedVideos.value);
}

const is404 = computed(() => {
  return error.value && (
    (typeof error.value === "string" && error.value.toLowerCase().includes("not found")) ||
    (typeof error.value === "string" && error.value.includes("404"))
  );
});

const sortedVideos = computed(() => {
  const list = allMedia.value.filter(isVideo);
  list.sort((a, b) => new Date(b.createDate || 0) - new Date(a.createDate || 0));
  return list;
});

function formatDate(dateStr) {
  return formatDateTimePST(dateStr);
}

async function deleteVideo(video) {
  const key = video?.photoKey;
  if (!key) return;
  deletingId.value = key;
  try {
    await deletePhoto(key);
    allMedia.value = allMedia.value.filter((m) => (m?.photoKey || m?.photo_key) !== key);
  } catch (e) {
    error.value = e.response?.data?.detail ?? e.message ?? "Failed to delete video.";
  } finally {
    deletingId.value = null;
  }
}

onMounted(async () => {
  try {
    await fetchAuthMe();
    isAdmin.value = true;
  } catch (_) {
    isAdmin.value = false;
  }
  try {
    const data = await fetchPhotos();
    if (data?.rateLimitedStale) rateLimitedStale.value = true;
    const list = data?.photos ?? data?.payload?.photos ?? [];
    allMedia.value = Array.isArray(list) ? list : [];
  } catch (e) {
    const detail = e.response?.data?.detail ?? e.message;
    error.value = typeof detail === "string" ? detail : "Failed to load videos.";
  } finally {
    loaded.value = true;
  }
});
</script>
