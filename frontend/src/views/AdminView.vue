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
        <p v-if="uploadMessage" class="mt-3 text-sm" :class="uploadError ? 'text-rose-300' : 'text-slate-400'">
          {{ uploadMessage }}
        </p>
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { getAuthLoginUrl, fetchAuthMe, authLogout, triggerSync, uploadFiles } from "../api/auth";


const authStatus = ref("loading");
const userEmail = ref("");
const authLoginUrl = getAuthLoginUrl("/admin");

const syncing = ref(false);
const syncMessage = ref("");
const syncError = ref(false);
const uploadMessage = ref("");
const uploadError = ref(false);

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

onMounted(() => {
  checkAuth();
});
</script>
