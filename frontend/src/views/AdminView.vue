<template>
  <div class="flex w-full flex-col gap-4">
    <section>
      <h1 class="text-xl font-semibold tracking-tight text-rose-200/90 md:text-2xl">
        Admin
      </h1>
      <p class="mt-1 text-sm text-slate-400">
        Run sync and upload photos. Sign in with Google to continue.
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
        </div>
        <p v-if="syncMessage" class="mt-3 text-sm" :class="syncError ? 'text-rose-300' : 'text-slate-400'">
          {{ syncMessage }}
        </p>
        <div v-if="uploading" class="mt-3 flex items-center gap-2 text-sm text-slate-400">
          <span class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-500 border-t-rose-400" />
          {{ uploadProgress }}
        </div>
        <div v-else-if="uploadMessage" class="mt-3 space-y-1">
          <p class="text-sm" :class="uploadError ? 'text-rose-300' : 'text-slate-400'">
            {{ uploadMessage }}
          </p>
          <p v-if="uploadDetails" class="text-xs text-slate-500">{{ uploadDetails }}</p>
        </div>
      </section>

      <section class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70 p-6">
        <h2 class="text-sm font-semibold text-rose-200/90 mb-3">Health</h2>
        <p class="mb-4 text-xs text-slate-400">API, database, Redis, and blob storage status.</p>
        <div v-if="healthLoading" class="flex items-center gap-2 py-4">
          <span class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-500 border-t-rose-400" />
          <span class="text-sm text-slate-400">Checking…</span>
        </div>
        <div v-else-if="healthError" class="text-sm text-rose-300">{{ healthError }}</div>
        <div v-else class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div
            v-for="item in healthItems"
            :key="item.key"
            class="rounded-lg border p-3"
            :class="item.statusClass"
          >
            <div class="flex items-center justify-between">
              <span class="text-sm font-medium text-slate-200">{{ item.label }}</span>
              <span
                class="rounded-full px-2 py-0.5 text-xs font-medium"
                :class="item.badgeClass"
              >{{ item.status }}</span>
            </div>
            <p class="mt-0.5 text-xs text-slate-500">{{ item.description }}</p>
          </div>
        </div>
        <button
          v-if="health"
          type="button"
          class="mt-3 rounded border border-slate-600 px-2 py-1 text-xs text-slate-400 hover:bg-slate-800"
          @click="refreshHealth"
        >
          Refresh
        </button>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { getAuthLoginUrl, fetchAuthMe, authLogout, triggerSync, uploadFiles } from "../api/auth";
import { fetchHealth } from "../api/health";


const authStatus = ref("loading");
const userEmail = ref("");
const authLoginUrl = getAuthLoginUrl("/admin");

const syncing = ref(false);
const syncMessage = ref("");
const syncError = ref(false);
const uploading = ref(false);
const uploadProgress = ref("");
const uploadMessage = ref("");
const uploadDetails = ref("");
const uploadError = ref(false);

const health = ref(null);
const healthLoading = ref(false);
const healthError = ref(null);
const statusConfig = {
  ok: { statusClass: "border-emerald-900/40 bg-emerald-950/20", badgeClass: "bg-emerald-500/20 text-emerald-300" },
  disabled: { statusClass: "border-slate-700/50 bg-slate-900/30", badgeClass: "bg-slate-600/30 text-slate-400" },
  unavailable: { statusClass: "border-rose-900/40 bg-rose-950/20", badgeClass: "bg-rose-500/20 text-rose-300" }
};
const healthItems = computed(() => {
  if (!health.value) return [];
  const h = health.value;
  const cfg = (s) => statusConfig[s] || statusConfig.disabled;
  return [
    { key: "api", label: "API", status: h.api ?? "ok", description: "FastAPI backend", ...cfg(h.api ?? "ok") },
    { key: "redis", label: "Redis", status: h.redis ?? "unknown", description: "Cache", ...cfg(h.redis ?? "disabled") },
    { key: "database", label: "Database", status: h.database ?? "unknown", description: "PostgreSQL", ...cfg(h.database ?? "disabled") },
    { key: "blob", label: "Blob storage", status: h.blob ?? "unknown", description: "Azure (photos & videos)", ...cfg(h.blob ?? "disabled") }
  ];
});

async function refreshHealth() {
  healthLoading.value = true;
  healthError.value = null;
  try {
    health.value = await fetchHealth();
  } catch (e) {
    healthError.value = e.response?.data?.detail ?? e.message ?? "Failed to fetch health";
  } finally {
    healthLoading.value = false;
  }
}

async function checkAuth() {
  authStatus.value = "loading";
  try {
    const data = await fetchAuthMe();
    userEmail.value = data?.email ?? "";
    authStatus.value = "authenticated";
  } catch (err) {
    authStatus.value = "unauthenticated";
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
  const fileList = Array.from(files);
  const names = fileList.map((f) => f.name || "file").join(", ");
  uploadMessage.value = "";
  uploadDetails.value = "";
  uploadError.value = false;
  uploading.value = true;
  uploadProgress.value = `Uploading ${fileList.length} file(s)…`;
  try {
    const result = await uploadFiles(fileList);
    const n = result?.uploaded ?? 0;
    if (n === fileList.length) {
      uploadMessage.value = `Uploaded ${n} file(s).`;
      uploadDetails.value = names;
    } else if (n > 0) {
      uploadMessage.value = `Uploaded ${n} of ${fileList.length} file(s).`;
      uploadDetails.value = names;
    } else {
      uploadError.value = true;
      uploadMessage.value = result?.error ?? "No files were uploaded. Try again or check the browser console.";
      uploadDetails.value = names;
    }
    event.target.value = "";
  } catch (err) {
    uploadError.value = true;
    uploadMessage.value = err.response?.data?.detail ?? err.message ?? "Upload failed.";
    uploadDetails.value = names;
  } finally {
    uploading.value = false;
    uploadProgress.value = "";
  }
}

onMounted(async () => {
  await checkAuth();
  if (authStatus.value === "authenticated") refreshHealth();
});
</script>
