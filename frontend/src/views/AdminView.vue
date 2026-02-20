<template>
  <div class="flex w-full flex-col gap-4">
    <section>
      <h1 class="text-xl font-semibold tracking-tight text-rose-200/90 md:text-2xl">
        Admin
      </h1>
      <p class="mt-1 text-sm text-slate-400">
        Run sync and upload or import photos. Sign in with Google to continue.
      </p>
    </section>

    <section
      v-if="authStatus === 'loading'"
      class="flex items-center justify-center rounded-xl border border-slate-800 bg-slate-900/70 py-12"
    >
      <p class="text-sm text-slate-400">Checking sign-in…</p>
    </section>

    <section
      v-else-if="authStatus === 'unauthenticated'"
      class="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-center"
    >
      <p class="text-sm text-slate-400 mb-4">You need to sign in to access admin actions.</p>
      <a
        :href="authLoginUrl"
        class="inline-flex items-center gap-2 rounded-full bg-slate-700 px-4 py-2 text-sm font-medium text-white hover:bg-slate-600"
      >
        Sign in with Google
      </a>
    </section>

    <template v-else-if="authStatus === 'authenticated'">
      <section class="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <p class="text-sm text-slate-400">
          Signed in as <span class="text-rose-200/90">{{ userEmail }}</span>
          <button
            type="button"
            class="ml-2 text-xs text-slate-500 hover:text-slate-300 underline"
            @click="logout"
          >
            Sign out
          </button>
        </p>
      </section>

      <section class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70 p-6">
        <h2 class="text-sm font-semibold text-rose-200/90 mb-3">Actions</h2>
        <div class="flex flex-wrap gap-3">
          <button
            type="button"
            class="rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-500 disabled:opacity-50"
            :disabled="syncing"
            @click="runSync"
          >
            {{ syncing ? "Syncing…" : "Run calendar sync" }}
          </button>
          <label class="rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-medium text-slate-200 cursor-pointer hover:bg-slate-700">
            Upload from device
            <input
              type="file"
              accept="image/*,video/*"
              multiple
              class="hidden"
              @change="onDeviceUpload"
            />
          </label>
          <button
            type="button"
            class="rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-700"
            @click="openGooglePhotosImport"
          >
            Import from Google Photos
          </button>
        </div>
        <p v-if="syncMessage" class="mt-3 text-sm" :class="syncError ? 'text-rose-300' : 'text-slate-400'">
          {{ syncMessage }}
        </p>
        <p v-if="uploadMessage" class="mt-3 text-sm" :class="uploadError ? 'text-rose-300' : 'text-slate-400'">
          {{ uploadMessage }}
        </p>
      </section>

      <section v-if="googlePhotosSection" class="rounded-xl border border-slate-800 bg-slate-900/70 p-6">
        <h2 class="text-sm font-semibold text-rose-200/90 mb-3">Import from Google Photos</h2>
        <template v-if="useUppyPicker">
          <p class="text-sm text-slate-400 mb-3">Pick photos or videos below, then click Upload. Files are sent to the hatch-sync timeline.</p>
          <div :id="uppyContainerId" class="uppy-dashboard-container mt-2"></div>
          <p v-if="uppyUploadMessage" class="mt-2 text-sm" :class="uppyUploadError ? 'text-rose-300' : 'text-slate-400'">{{ uppyUploadMessage }}</p>
        </template>
        <template v-else>
          <p class="text-sm text-slate-400 mb-3">Load your Google Photos library and select items to add to the baby timeline.</p>
          <button
            type="button"
            class="rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-50"
            :disabled="googlePhotosLoading"
            @click="loadGooglePhotos"
          >
            {{ googlePhotosLoading ? "Loading…" : "Load from Google Photos" }}
          </button>
          <p v-if="googlePhotosError" class="mt-2 text-sm text-rose-300">{{ googlePhotosError }}</p>
        </template>
        <div v-if="googlePhotosItems.length > 0 && !useUppyPicker" class="mt-4">
          <div class="flex flex-wrap gap-2 mb-2">
            <label class="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
              <input type="checkbox" :checked="allGooglePhotosSelected" @change="toggleAllGooglePhotos" />
              Select all
            </label>
            <button
              type="button"
              class="rounded-lg bg-rose-600 px-3 py-1 text-sm text-white hover:bg-rose-500 disabled:opacity-50"
              :disabled="selectedGooglePhotosIds.length === 0 || googlePhotosImporting"
              @click="doImportGooglePhotos"
            >
              {{ googlePhotosImporting ? "Importing…" : `Import selected (${selectedGooglePhotosIds.length})` }}
            </button>
          </div>
          <div class="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2 max-h-96 overflow-y-auto">
            <label
              v-for="item in googlePhotosItems"
              :key="item.id"
              class="relative cursor-pointer rounded overflow-hidden border-2 transition-colors"
              :class="selectedGooglePhotosIds.includes(item.id) ? 'border-rose-500' : 'border-transparent'"
            >
              <input
                type="checkbox"
                :value="item.id"
                class="sr-only"
                :checked="selectedGooglePhotosIds.includes(item.id)"
                @change="toggleGooglePhoto(item.id)"
              />
              <img
                v-if="thumbnailUrl(item)"
                :src="thumbnailUrl(item)"
                :alt="item.filename || 'Photo'"
                class="w-full aspect-square object-cover"
              />
              <div v-else class="w-full aspect-square bg-slate-700 flex items-center justify-center text-slate-500 text-xs">
                No preview
              </div>
            </label>
          </div>
          <p v-if="googlePhotosImportMessage" class="mt-2 text-sm" :class="googlePhotosImportError ? 'text-rose-300' : 'text-slate-400'">
            {{ googlePhotosImportMessage }}
          </p>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import Uppy from "@uppy/core";
import Dashboard from "@uppy/dashboard";
import GooglePhotosPicker from "@uppy/google-photos-picker";
import XHRUpload from "@uppy/xhr-upload";
import "@uppy/core/css/style.min.css";
import "@uppy/dashboard/css/style.min.css";
import { getAuthLoginUrl, fetchAuthMe, authLogout, triggerSync, uploadFiles, fetchGooglePhotosList, importFromGooglePhotos } from "../api/auth";


const authStatus = ref("loading");
const userEmail = ref("");
const authLoginUrl = computed(() => getAuthLoginUrl("/admin"));

const syncing = ref(false);
const syncMessage = ref("");
const syncError = ref(false);
const uploadMessage = ref("");
const uploadError = ref(false);
const googlePhotosSection = ref(false);
const googlePhotosLoading = ref(false);
const googlePhotosError = ref("");
const googlePhotosItems = ref([]);
const googlePhotosNextToken = ref(null);
const selectedGooglePhotosIds = ref([]);
const googlePhotosImporting = ref(false);
const googlePhotosImportMessage = ref("");
const googlePhotosImportError = ref(false);
const uppyContainerId = "uppy-google-photos-picker";
const uppyUploadMessage = ref("");
const uppyUploadError = ref(false);
let uppyInstance = null;

const useUppyPicker = computed(() => !!(import.meta.env.VITE_COMPANION_URL && import.meta.env.VITE_GOOGLE_CLIENT_ID));

async function checkAuth() {
  authStatus.value = "loading";
  try {
    const data = await fetchAuthMe();
    userEmail.value = data?.email ?? "";
    authStatus.value = "authenticated";
  } catch (err) {
    if (err.response?.status === 401 || err.response?.status === 403) {
      authStatus.value = "unauthenticated";
    } else {
      authStatus.value = "unauthenticated";
    }
  }
}

async function logout() {
  try {
    await authLogout();
  } catch (_) {}
  userEmail.value = "";
  authStatus.value = "unauthenticated";
}

async function runSync() {
  syncing.value = true;
  syncMessage.value = "";
  syncError.value = false;
  try {
    const result = await triggerSync();
    syncMessage.value = result?.message ?? "Sync completed.";
    if (result?.events_created != null) {
      syncMessage.value = `Created ${result.events_created} event(s).`;
    }
  } catch (err) {
    syncError.value = true;
    syncMessage.value = err.response?.data?.detail ?? err.message ?? "Sync failed.";
  } finally {
    syncing.value = false;
  }
}

async function onDeviceUpload(event) {
  const files = event.target?.files;
  if (!files?.length) return;
  uploadMessage.value = "";
  uploadError.value = false;
  try {
    await uploadFiles(Array.from(files));
    uploadMessage.value = `Uploaded ${files.length} file(s).`;
    event.target.value = "";
  } catch (err) {
    uploadError.value = true;
    uploadMessage.value = err.response?.data?.detail ?? err.message ?? "Upload failed.";
  }
}

function openGooglePhotosImport() {
  googlePhotosSection.value = true;
  nextTick(() => initUppyWhenReady());
}

function initUppyWhenReady() {
  const companionUrl = import.meta.env.VITE_COMPANION_URL;
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
  const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";
  if (!companionUrl || !clientId || uppyInstance) return;
  nextTick(() => {
    const el = document.getElementById(uppyContainerId);
    if (!el) return;
    const uppy = new Uppy({ restrictions: { maxNumberOfFiles: 50 }, autoProceed: false })
      .use(GooglePhotosPicker, { companionUrl, clientId, companionCookiesRule: "same-origin" })
      .use(Dashboard, {
        inline: true,
        target: `#${uppyContainerId}`,
        proudlyDisplayPoweredByUppy: false,
        showProgressDetails: true,
        width: "100%",
        height: 380,
        note: "Pick photos or videos from Google Photos to add to the baby timeline."
      })
      .use(XHRUpload, {
        endpoint: `${apiBase}/admin/upload`,
        fieldName: "files",
        formData: true,
        bundle: false,
        withCredentials: true
      });
    uppy.on("complete", (result) => {
      uppyUploadError.value = (result.failed || []).length > 0;
      const ok = (result.successful || []).length;
      const fail = (result.failed || []).length;
      uppyUploadMessage.value = fail ? `Uploaded ${ok} file(s), ${fail} failed.` : `Uploaded ${ok} file(s) from Google Photos.`;
    });
    uppyInstance = uppy;
  });
}

function thumbnailUrl(item) {
  const base = item?.baseUrl;
  if (!base) return null;
  return base + "=w200-h200";
}

function toggleGooglePhoto(id) {
  const i = selectedGooglePhotosIds.value.indexOf(id);
  if (i >= 0) {
    selectedGooglePhotosIds.value = selectedGooglePhotosIds.value.filter((x) => x !== id);
  } else {
    selectedGooglePhotosIds.value = [...selectedGooglePhotosIds.value, id];
  }
}

const allGooglePhotosSelected = computed(() => {
  const ids = selectedGooglePhotosIds.value;
  const items = googlePhotosItems.value;
  return items.length > 0 && ids.length === items.length;
});

function toggleAllGooglePhotos() {
  if (allGooglePhotosSelected.value) {
    selectedGooglePhotosIds.value = [];
  } else {
    selectedGooglePhotosIds.value = googlePhotosItems.value.map((x) => x.id);
  }
}

async function loadGooglePhotos() {
  googlePhotosLoading.value = true;
  googlePhotosError.value = "";
  try {
    const data = await fetchGooglePhotosList(50, googlePhotosNextToken.value || undefined);
    const items = data?.mediaItems ?? [];
    googlePhotosItems.value = googlePhotosNextToken.value ? [...googlePhotosItems.value, ...items] : items;
    googlePhotosNextToken.value = data?.nextPageToken ?? null;
  } catch (err) {
    googlePhotosError.value = err.response?.data?.detail ?? err.message ?? "Failed to load Google Photos.";
  } finally {
    googlePhotosLoading.value = false;
  }
}

async function doImportGooglePhotos() {
  const ids = selectedGooglePhotosIds.value;
  if (!ids.length) return;
  googlePhotosImporting.value = true;
  googlePhotosImportMessage.value = "";
  googlePhotosImportError.value = false;
  try {
    const result = await importFromGooglePhotos(ids);
    const n = result?.imported ?? 0;
    googlePhotosImportMessage.value = `Imported ${n} item(s).`;
    selectedGooglePhotosIds.value = selectedGooglePhotosIds.value.filter((id) => !ids.includes(id));
  } catch (err) {
    googlePhotosImportError.value = true;
    googlePhotosImportMessage.value = err.response?.data?.detail ?? err.message ?? "Import failed.";
  } finally {
    googlePhotosImporting.value = false;
  }
}

onMounted(() => {
  checkAuth();
});

onBeforeUnmount(() => {
  if (uppyInstance) {
    uppyInstance.close();
    uppyInstance = null;
  }
});
</script>
