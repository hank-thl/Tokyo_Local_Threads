<script setup>
import { ref, computed } from 'vue'
import SpotCard from './SpotCard.vue'
import SpotModal from './SpotModal.vue'
import rawSpotsData from '@data/taito_documents.json'

const tabs = ref(['全部', '老屋活化', '支持在地商店街', '環境友善', '文化體驗'])
const activeTab = ref('全部')
const isModalVisible = ref(false)
const selectedSpot = ref({})

const spotsData = ref(
  rawSpotsData.map((spot, index) => {
    return {
      id: index + 1, // 自動賦予一個流水號 ID (給 Vue 的 v-for :key 使用)
      name: spot.name.zh || spot.name.jp, // 優先顯示中文名稱，沒有就用日文
      description: spot.ui_description.zh || '暫無中文介紹', 
      access: '詳細交通請參考官網', // 爬蟲目前沒抓這項，先給個預設值
      image: spot.image_url || 'https://via.placeholder.com/1000x600?text=No+Image', // 如果沒圖片給個預設圖
      map: spot.google_map_url || '',
      tags: spot.sdg_tags || [] // 直接套用 Gemini 幫我們打好的標籤！
    }
  })
);

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
