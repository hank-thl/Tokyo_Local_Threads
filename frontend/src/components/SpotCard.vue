<script setup>
defineProps({
  spot: {
    type: Object,
    required: true
  }
})

defineEmits(['open-modal'])
</script>

<template>
  <div 
    class="flex overflow-hidden bg-white border border-gray-100 rounded-xl shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 cursor-pointer"
    @click="$emit('open-modal')"
  >
    <div class="w-[40%] h-64">
      <img :src="spot.image" :alt="spot.name" class="w-full h-full object-cover" />
    </div>
    
    <div class="w-[60%] p-6 flex flex-col justify-between">
      <div>
        <h3 class="text-2xl font-bold text-gray-800 mb-2">{{ spot.name }}</h3>
        <p class="text-gray-600 mb-5 leading-relaxed line-clamp-3">{{ spot.description }}</p>
      </div>
      
      <div class="flex flex-wrap gap-2">
        <span 
          v-for="(tag, index) in spot.tags" 
          :key="index"
          class="px-3 py-1 text-sm font-medium text-green-700 bg-green-50 rounded-full"
        >
          # {{ tag }}
        </span>
      </div>
    </div>
  </div>
</template>