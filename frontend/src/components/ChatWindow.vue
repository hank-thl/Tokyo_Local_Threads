<script setup>
import { ref } from 'vue'

const isOpen = ref(false)
const inputText = ref('')
const messages = ref([
  { sender: 'ai', text: '您好！我是共生東京 AI 旅伴。想去淺草但怕人太多嗎？我可以為您推薦周邊具備在地文化且人潮較少的替代景點！' }
])

const sendMessage = () => {
  if (!inputText.value.trim()) return

  messages.value.push({ sender: 'user', text: inputText.value })
  
  const currentText = inputText.value
  inputText.value = ''

  setTimeout(() => {
    messages.value.push({ sender: 'ai', text: `(此為前端模擬回覆) 收到您的需求：「${currentText}」。未來這裡將會串接 WebSocket 回傳的 LangChain RAG 建議！` })
  }, 1000)
}
</script>
<template>
  <div class="fixed bottom-6 right-6 z-50 flex flex-col items-end">
    <transition
      enter-active-class="transition ease-out duration-300"
      enter-from-class="opacity-0 translate-y-5"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition ease-in duration-200"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 translate-y-5"
    >
      <div v-if="isOpen" class="w-[380px] h-[550px] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden mb-4 border border-gray-100">
        <div class="bg-green-600 px-5 py-4 flex justify-between items-center text-white">
          <div>
            <h3 class="font-bold text-lg tracking-wide">AI 永續旅伴</h3>
            <p class="text-green-100 text-sm">為您推薦最佳替代路線</p>
          </div>
          <button @click="isOpen = false" class="text-white hover:text-gray-200 text-2xl leading-none">
            &times;
          </button>
        </div>

        <div class="flex-1 p-5 overflow-y-auto bg-gray-50 flex flex-col gap-4">
          <div 
            v-for="(msg, index) in messages" 
            :key="index"
            :class="['flex', msg.sender === 'user' ? 'justify-end' : 'justify-start']"
          >
            <div 
              :class="[
                'max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed shadow-sm',
                msg.sender === 'user' ? 'bg-green-600 text-white rounded-tr-sm' : 'bg-white text-gray-800 border border-gray-100 rounded-tl-sm'
              ]"
            >
              {{ msg.text }}
            </div>
          </div>
        </div>

        <div class="p-4 bg-white border-t border-gray-100 flex gap-2">
          <input 
            v-model="inputText"
            @keyup.enter="sendMessage"
            type="text" 
            placeholder="輸入您的旅遊需求..." 
            class="flex-1 bg-gray-50 border border-gray-200 rounded-full px-4 py-2.5 text-sm focus:outline-none focus:border-green-500 focus:ring-1 focus:ring-green-500"
          />
          <button 
            @click="sendMessage"
            class="w-10 h-10 bg-green-600 text-white rounded-full flex items-center justify-center hover:bg-green-700 transition-colors shadow-sm shrink-0"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5 ml-1">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
            </svg>
          </button>
        </div>
      </div>
    </transition>

    <button 
      v-if="!isOpen"
      @click="isOpen = true"
      class="w-16 h-16 bg-green-600 text-white rounded-full shadow-2xl flex items-center justify-center hover:bg-green-700 hover:scale-105 transition-all"
    >
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-8 h-8">
        <path stroke-linecap="round" stroke-linejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
      </svg>
    </button>
  </div>
</template>

