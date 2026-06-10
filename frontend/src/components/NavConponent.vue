<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SpotCard from './SpotCard.vue'
import SpotModal from './SpotModal.vue'
import { fetchDocuments, fetchSdgTags } from '@/services/api'

const route = useRoute()
const router = useRouter()
const tabs = ref(['全部'])
const activeTab = ref('全部')
const isModalVisible = ref(false)
const selectedSpot = ref({})
const isLoading = ref(true)
const errorMessage = ref('')
const spotsData = ref([])

const mapDocumentToSpot = (document, index) => {
  return {
    id: document._id || index + 1,
    name: document.name?.zh || document.name?.jp || '未命名景點',
    nameZh: document.name?.zh || '',
    nameJp: document.name?.jp || '',
    description: document.ui_description?.zh || '暫無中文介紹',
    access: '詳細交通請參考官網',
    crowdLevel: document.crowd_level || 1,
    crowdReason: document.crowd_reason || '暫無人潮評估',
    image: document.image_url || 'https://via.placeholder.com/1000x600?text=No+Image',
    map: document.google_map_url || '',
    tags: document.sdg_tags || []
  }
}

const loadData = async () => {
  isLoading.value = true
  errorMessage.value = ''

  try {
    const [documents, sdgTags] = await Promise.all([
      fetchDocuments({ limit: 100 }),
      fetchSdgTags()
    ])

    tabs.value = ['全部', ...sdgTags]
    spotsData.value = documents.map(mapDocumentToSpot)
  } catch (error) {
    console.error(error)
    errorMessage.value = '無法取得景點資料，請確認 Flask 後端是否已啟動。'
  } finally {
    isLoading.value = false
  }
}

const filteredSpots = computed(() => {
  if (activeTab.value === '全部') {
    return spotsData.value
  }
  return spotsData.value.filter(spot => spot.tags.includes(activeTab.value))
})

const syncModalWithRoute = () => {
  const spotId = route.params.spotId
  if (!spotId) {
    isModalVisible.value = false
    selectedSpot.value = {}
    return
  }

  const matchedSpot = spotsData.value.find(spot => spot.id === spotId)
  if (!matchedSpot) return

  selectedSpot.value = matchedSpot
  isModalVisible.value = true
}

const openSpotModal = (spot) => {
  router.push({
    name: 'spot-detail',
    params: {
      spotId: spot.id
    }
  })
}

const closeSpotModal = () => {
  router.push({ name: 'home' })
}

watch(
  () => route.params.spotId,
  syncModalWithRoute
)

onMounted(async () => {
  await loadData()
  syncModalWithRoute()
})
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
      <div v-if="isLoading" class="py-20 text-center text-gray-500 text-lg">
        資料載入中...
      </div>

      <div v-else-if="errorMessage" class="py-20 text-center text-red-500 text-lg">
        {{ errorMessage }}
      </div>

      <div v-else-if="filteredSpots.length > 0" class="flex flex-col gap-6">
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
      @close="closeSpotModal" 
    />
  </div>
</template>
