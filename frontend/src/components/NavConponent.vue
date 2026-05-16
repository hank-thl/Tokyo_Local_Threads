<script setup>
import { ref, computed } from 'vue'
import SpotCard from './SpotCard.vue'
import SpotModal from './SpotModal.vue'

const tabs = ref(['全部', '老屋活化', '支持在地商店街', '環境友善', '文化體驗'])
const activeTab = ref('全部')
const isModalVisible = ref(false)
const selectedSpot = ref({})

const spotsData = ref([
  {
    id: 1,
    name: '谷根千老屋咖啡',
    description: '位於谷中銀座附近的傳統老屋改建咖啡廳，保留了昭和時代的建築特色，提供在地烘焙的公平貿易咖啡，讓旅客深入體驗下町風情。',
    access: '搭乘千代田線至「千駄木站」，步行約5分鐘。',
    image: 'https://images.unsplash.com/photo-1528360354687-83ebedab298c?q=80&w=1000&auto=format&fit=crop',
    map: 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3238.9!2d139.76!3d35.72!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2zMzXCsDQzJzEyLjAiTiAxMznCsDQ1JzM2LjAiRQ!5e0!3m2!1szh-TW!2stw!4v1715840000000!5m2!1szh-TW!2stw',
    tags: ['老屋活化', '支持在地商店街']
  },
  {
    id: 2,
    name: '淺草環保文化旅宿',
    description: '距離淺草寺步行十分鐘的環保旅宿，全館使用太陽能與雨水回收系統，並提供周邊深度文化徒步導覽，將客流引導至更具在地故事的街區。',
    access: '搭乘銀座線至「淺草站」，步行約10分鐘。',
    image: 'https://images.unsplash.com/photo-1542051812871-757505937d98?q=80&w=1000&auto=format&fit=crop',
    map: 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3239.1!2d139.79!3d35.71!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2zMzXCsDQyJzM2LjAiTiAxMznCsDQ3JzI0LjAiRQ!5e0!3m2!1szh-TW!2stw!4v1715840000001!5m2!1szh-TW!2stw',
    tags: ['環境友善', '文化體驗']
  }
])

const filteredSpots = computed(() => {
  if (activeTab.value === '全部') {
    return spotsData.value
  }
  return spotsData.value.filter(spot => spot.tags.includes(activeTab.value))
})

const openSpotModal = (spot) => {
  selectedSpot.value = spot
  isModalVisible.value = true
}
</script>

<template>
  <div class="max-w-[900px] mx-auto py-12 px-6">
    <div class="flex flex-wrap justify-center gap-4 mb-10">
      <button
        v-for="tab in tabs"
        :key="tab"
        :class="[
          'px-6 py-2 rounded-full font-medium transition-colors',
          activeTab === tab ? 'bg-green-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
        ]"
        @click="activeTab = tab"
      >
        {{ tab }}
      </button>
    </div>

    <section>
      <div v-if="filteredSpots.length > 0" class="flex flex-col gap-6">
        <SpotCard
          v-for="spot in filteredSpots"
          :key="spot.id"
          :spot="spot"
          @open-modal="openSpotModal(spot)"
        />
      </div>

      <div v-else class="py-20 text-center text-gray-500 text-lg">
        目前該分類下沒有相關景點資料。
      </div>
    </section>

    <!-- 引入彈出詳細資訊視窗 -->
    <SpotModal 
      :is-open="isModalVisible" 
      :spot="selectedSpot" 
      @close="isModalVisible = false" 
    />
  </div>
</template>