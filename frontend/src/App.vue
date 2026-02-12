<template>
  <div class="min-h-screen flex flex-col">
    <header
      class="border-b border-rose-950/30 bg-slate-950/90 backdrop-blur sticky top-0 z-10"
    >
      <div
        class="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 md:py-4"
      >
        <div class="flex items-center gap-2">
          <div
            class="flex h-8 w-8 items-center justify-center rounded-lg bg-rose-400 text-white font-bold shadow-sm"
          >
            HG
          </div>
          <div class="flex flex-col">
            <span class="text-sm font-semibold leading-tight">
              Hatch Grow Analytics
            </span>
            <span class="text-xs text-slate-400 leading-tight">
              Uma's diapers, feedings, sleep, weight & photos
            </span>
          </div>
        </div>
        <nav class="hidden gap-4 text-sm md:flex">
          <RouterLink
            v-for="link in links"
            :key="link.to"
            :to="link.to"
            class="rounded-full px-3 py-1 text-slate-300 hover:bg-slate-800"
            active-class="bg-rose-400 text-white"
          >
            {{ link.label }}
          </RouterLink>
        </nav>
        <button
          class="inline-flex items-center justify-center rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 md:hidden"
          @click="showMobileNav = !showMobileNav"
        >
          Menu
        </button>
      </div>
      <nav
        v-if="showMobileNav"
        class="border-t border-slate-800 bg-slate-950/95 px-4 py-2 md:hidden"
      >
        <div class="flex flex-col gap-1 text-sm">
          <RouterLink
            v-for="link in links"
            :key="link.to"
            :to="link.to"
            class="rounded-lg px-3 py-2 text-slate-300 hover:bg-slate-800"
            active-class="bg-rose-400 text-white"
            @click="showMobileNav = false"
          >
            {{ link.label }}
          </RouterLink>
        </div>
      </nav>
    </header>

    <main class="mx-auto flex w-full max-w-6xl flex-1 min-h-0 overflow-y-auto px-4 py-4 md:py-6">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { RouterLink, RouterView } from "vue-router";

const showMobileNav = ref(false);

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/feedings", label: "Feedings" },
  { to: "/diapers", label: "Diapers" },
  { to: "/sleep", label: "Sleep" },
  { to: "/weight", label: "Weight" },
  { to: "/photos", label: "Photos" }
];
</script>

