<template>
  <div class="flex w-full flex-col gap-4">
    <section>
      <h1 class="text-xl font-semibold tracking-tight text-rose-200/90 md:text-2xl">
        Daily Photos
      </h1>
      <p class="mt-1 text-sm text-slate-400">
        Uma's daily photos from Hatch Grow.
        <span v-if="loaded && sortedPhotos.length > 0" class="text-rose-300/90">
          {{ sortedPhotos.length }} photo{{ sortedPhotos.length === 1 ? '' : 's' }}.
        </span>
      </p>
    </section>

    <section v-if="error" class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70 p-4">
      <p class="text-sm text-rose-300">{{ error }}</p>
      <p v-if="is404" class="mt-2 text-xs text-slate-400">
        Restart the API (e.g. docker-compose up --build) so the /grow/photos endpoint is available.
      </p>
    </section>

    <section
      v-else-if="loaded"
      class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:gap-4"
    >
      <div
        v-for="photo in sortedPhotos"
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
            @error="onImageError($event, photo)"
          />
          <div
            v-else
            class="h-full w-full flex flex-col items-center justify-center text-slate-400 text-xs p-2 gap-1 text-center"
          >
            <span>Image unavailable</span>
            <span class="text-slate-500">Link may have expired. Refresh page for new links.</span>
          </div>
        </a>
        <div
          v-else
          class="aspect-square w-full bg-slate-800 flex items-center justify-center text-slate-500 text-xs p-2"
        >
          No preview URL
        </div>
        <div class="px-2 py-2 text-xs text-slate-400">
          {{ formatDate(photo.createDate) }}
        </div>
      </div>
    </section>

    <section v-if="loaded && sortedPhotos.length === 0" class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70 p-8 text-center">
      <p class="text-sm text-slate-400">No daily photos yet. Add some in the Hatch Grow app.</p>
    </section>

    <section v-if="!loaded && !error" class="flex items-center justify-center py-16">
      <p class="text-sm text-slate-400">Loading photos…</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { fetchPhotos } from "../api/grow";

const photos = ref([]);
const loaded = ref(false);
const error = ref(null);
const failedImages = ref(new Set());

function photoUrl(photo) {
  return photo?.cutDownloadUrl ?? photo?.cut_download_url ?? null;
}

function onImageError(event, photo) {
  if (photo?.createDate) failedImages.value.add(photo.createDate);
  failedImages.value = new Set(failedImages.value);
}

const is404 = computed(() => {
  return error.value && (
    (typeof error.value === "string" && error.value.toLowerCase().includes("not found")) ||
    (typeof error.value === "string" && error.value.includes("404"))
  );
});

const sortedPhotos = computed(() => {
  const list = [...photos.value];
  list.sort((a, b) => new Date(b.createDate || 0) - new Date(a.createDate || 0));
  return list;
});

function formatDate(dateStr) {
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
    const data = await fetchPhotos();
    const list = data?.photos ?? data?.payload?.photos ?? [];
    photos.value = Array.isArray(list) ? list : [];
  } catch (e) {
    const detail = e.response?.data?.detail ?? e.message;
    error.value = typeof detail === "string" ? detail : "Failed to load photos.";
  } finally {
    loaded.value = true;
  }
});
</script>
