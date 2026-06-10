<script setup>
import { computed } from 'vue'

const props = defineProps({
  spot: {
    type: Object,
    default: () => ({})
  },
  isOpen: {
    type: Boolean,
    default: false
  }
})

defineEmits(['close'])

const crowdLevel = computed(() => {
  const level = Number(props.spot.crowdLevel || 1)
  return Math.min(Math.max(level, 1), 5)
})

const crowdIcon = computed(() => {
  if (crowdLevel.value <= 1) {
    return '/icons/crowd-level-1.png'
  }

  if (crowdLevel.value <= 3) {
    return '/icons/crowd-level-2.png'
  }

  return '/icons/crowd-level-3.png'
})

const crowdLabel = computed(() => {
  if (crowdLevel.value <= 1) {
    return '低人潮秘境'
  }

  if (crowdLevel.value <= 3) {
    return '中度人潮'
  }

  return '高人潮區域'
})
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 flex items-center justify-center px-4 bg-black/60" @click.self="$emit('close')">
    <div class="relative w-full max-w-[900px] max-h-[90vh] bg-white rounded-2xl shadow-2xl overflow-y-auto flex flex-col md:flex-row">
      <button @click="$emit('close')" class="absolute top-4 right-5 text-3xl text-gray-400 hover:text-gray-700 z-10">
        &times;
      </button>

      <div class="w-full md:w-[55%] p-6 md:p-8">
        <div class="mb-4">
          <h3 class="text-[1.8rem] font-bold text-gray-900">{{ spot.nameZh || spot.name }}</h3>
          <p
            v-if="spot.nameJp && spot.nameJp !== spot.nameZh"
            class="mt-1 flex items-center gap-2 text-base italic tracking-wide text-gray-500"
          >
            <span class="rounded border border-gray-200 bg-gray-100 px-1.5 py-0.5 text-[0.7rem] font-semibold not-italic tracking-normal text-gray-400">
              JP
            </span>
            <span>{{ spot.nameJp }}</span>
          </p>
        </div>
        <img :src="spot.image" :alt="spot.name" class="w-full h-[260px] object-cover rounded-[14px] mb-4" />
        <p class="text-gray-700 leading-[1.8]">{{ spot.description }}</p>
      </div>

      <div class="w-full md:w-[45%] p-6 md:p-8 bg-gray-50 border-t md:border-t-0 md:border-l border-gray-100">
        <h4 class="text-[1.1rem] font-bold text-[#e60023] mb-2.5">⚡ 觀光人潮避雷針</h4>
        <div class="bg-white border border-gray-100 p-4 rounded-xl text-gray-700 mb-6">
          <div class="flex items-center gap-4">
            <img
              v-if="crowdIcon"
              :src="crowdIcon"
              :alt="crowdLabel"
              class="h-14 w-14 shrink-0 object-contain"
            />
            <div>
              <p class="text-sm font-semibold text-gray-500">擁擠程度 {{ crowdLevel }} / 5</p>
              <p class="mt-1 text-lg font-bold text-gray-900">{{ crowdLabel }}</p>
            </div>
          </div>
          <p class="mt-4 rounded-lg bg-gray-50 p-3 text-sm leading-relaxed text-gray-600">
            {{ spot.crowdReason || '暫無人潮評估' }}
          </p>
        </div>

        <h4 class="text-[1.1rem] font-bold text-[#e60023] mb-2.5">📍 地圖位置</h4>
        <iframe :src="spot.map" class="w-full h-[240px] rounded-xl border-0 mt-2.5" allowfullscreen loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
      </div>
    </div>
  </div>
</template>
