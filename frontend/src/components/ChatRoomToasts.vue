<template>
  <transition-group
    name="toast"
    tag="div"
    class="fixed right-4 bottom-4 z-[1000] flex flex-col gap-2"
  >
    <div
      v-for="t in toasts"
      :key="t.id"
      :class="[
        'rounded-xl border px-3.5 py-2.5 text-sm min-w-[200px] max-w-[320px] flex items-start gap-2 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.35),_0_2px_6px_rgba(0,0,0,0.25)] bg-white dark:bg-neutral-900 border-neutral-200 dark:border-neutral-800 transition-colors',
        t.type === 'error' ? 'border-red-500' : '',
      ]"
    >
      <span class="flex-1 leading-tight text-sm">{{ t.message }}</span>
      <button
        class="bg-transparent border-0 text-base leading-none px-1 hover:opacity-80"
        @click="dismissToast(t.id)"
      >
        x
      </button>
    </div>
  </transition-group>
</template>

<script setup lang="ts">
defineProps<{
  toasts: { id: string; message: string; type: string }[];
  dismissToast: (id: string) => void;
}>();
</script>
