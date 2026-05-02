<script setup>
import { ref } from 'vue'

// 將圖片網址宣告為變數，我換了一張有加上參數設定的 Unsplash 東京風景圖，確保能順利載入
const bgImage = ref('https://images.unsplash.com/photo-1549693578-d683be217e58')
</script>

<template>
  <header class="relative flex items-center w-full h-[85vh] pl-[10%] text-white overflow-hidden">
    <img 
      :src="bgImage" 
      alt="共生東京導覽背景" 
      class="absolute inset-0 w-full h-full object-cover z-0"
    />

    <div class="absolute inset-0 bg-gradient-to-r from-black/65 to-black/25 z-0"></div>

    <div class="relative z-10 max-w-[520px]">
      <span class="inline-block px-3.5 py-1.5 mb-4 text-sm tracking-[2px] rounded-full bg-white/15">
        TOKYO TRAVEL GUIDE
      </span>

      <h1 class="my-2.5 text-[3.5rem] tracking-[2px] font-bold">
        東京旅遊導覽
      </h1>

      <p class="mb-[30px] text-[1.2rem] leading-[1.8] text-[#f0f0f0]">
        探索文化 · 景點 · 美食 · 城市魅力
      </p>
    </div>
  </header>
</template>

<style scoped>

</style>
