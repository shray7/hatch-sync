<template>
  <div
    class="rounded-xl border border-rose-950/20 border-slate-800 bg-slate-900/70 p-4 shadow-sm flex flex-col gap-1"
  >
    <div class="text-xs uppercase tracking-wide text-slate-400">
      {{ label }}
    </div>
    <div class="text-2xl font-semibold">{{ value }}</div>
    <div v-if="sub" class="text-xs text-slate-500">
      {{ sub }}
    </div>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], required: true },
  sub: { type: String, default: "" }
});
</script>

