<script setup>
defineProps({
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
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 flex items-center justify-center px-4 bg-black/60" @click.self="$emit('close')">
    <div class="relative w-full max-w-[900px] max-h-[90vh] bg-white rounded-2xl shadow-2xl overflow-y-auto flex flex-col md:flex-row">
      <button @click="$emit('close')" class="absolute top-4 right-5 text-3xl text-gray-400 hover:text-gray-700 z-10">
        &times;
      </button>

      <div class="w-full md:w-[55%] p-6 md:p-8">
        <h3 class="text-[1.8rem] font-bold text-gray-900 mb-4">{{ spot.name }}</h3>
        <img :src="spot.image" :alt="spot.name" class="w-full h-[260px] object-cover rounded-[14px] mb-4" />
        <p class="text-gray-700 leading-[1.8]">{{ spot.description }}</p>
      </div>

      <div class="w-full md:w-[45%] p-6 md:p-8 bg-gray-50 border-t md:border-t-0 md:border-l border-gray-100">
        <h4 class="text-[1.1rem] font-bold text-[#e60023] mb-2.5">🚇 如何抵達</h4>
        <p class="bg-[#f6f6f6] p-4 rounded-xl text-gray-700 mb-6">{{ spot.access }}</p>

        <h4 class="text-[1.1rem] font-bold text-[#e60023] mb-2.5">📍 地圖位置</h4>
        <iframe :src="spot.map" class="w-full h-[240px] rounded-xl border-0 mt-2.5" allowfullscreen loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
      </div>
    </div>
  </div>
</template>