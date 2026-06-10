<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { io } from 'socket.io-client'

const SOCKET_URL =
  import.meta.env.VITE_SOCKET_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  'http://localhost:5000'

const STORAGE_KEY = 'tokyo_local_threads_session_id'

const isOpen = ref(false)
const inputText = ref('')
const isLoading = ref(false)
const isConnected = ref(false)
const chatBodyRef = ref(null)
const socket = ref(null)
const sessionId = ref('')
const lastAiText = ref('')
const messages = ref([
  {
    sender: 'ai',
    text: '您好！我是共生東京 AI 永續旅伴。告訴我你想去的地方或旅行偏好，我會用人潮避雷針幫你找出台東區更永續的替代選擇。',
  },
])

const getOrCreateSessionId = () => {
  const existingSessionId = localStorage.getItem(STORAGE_KEY)
  if (existingSessionId) {
    return existingSessionId
  }

  const newSessionId = `session_${Date.now()}_${crypto.randomUUID()}`
  localStorage.setItem(STORAGE_KEY, newSessionId)
  return newSessionId
}

const scrollToBottom = async () => {
  await nextTick()
  if (!chatBodyRef.value) return

  chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
}

const escapeHtml = (text) => {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

const formatMessage = (text) => {
  return escapeHtml(text)
    .replace(/^### (.+)$/gm, '<div class="chat-heading">$1</div>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^\* (.+)$/gm, '<div class="chat-list-item">• $1</div>')
    .replace(/^- (.+)$/gm, '<div class="chat-list-item">• $1</div>')
    .replace(/\n/g, '<br>')
}

const pushAiMessage = (text) => {
  if (!text) return
  if (text === lastAiText.value) {
    isLoading.value = false
    return
  }

  messages.value.push({
    sender: 'ai',
    text,
  })
  lastAiText.value = text
  isLoading.value = false
}

const connectSocket = () => {
  socket.value = io(SOCKET_URL, {
    transports: ['websocket', 'polling'],
  })

  socket.value.on('connect', () => {
    isConnected.value = true
  })

  socket.value.on('disconnect', () => {
    isConnected.value = false
  })

  socket.value.on('connect_error', () => {
    isConnected.value = false
    isLoading.value = false
  })

  // 依照本階段規格監聽 ai_response，讀取 answer 欄位。
  socket.value.on('ai_response', (data) => {
    pushAiMessage(data?.answer || data?.message || 'AI 回覆格式有誤，請稍後再試。')
  })

  // 相容目前後端 sockets/chat.py 使用的 ai_message 事件。
  socket.value.on('ai_message', (data) => {
    pushAiMessage(data?.answer || data?.message || 'AI 回覆格式有誤，請稍後再試。')
  })
}

const sendMessage = () => {
  const message = inputText.value.trim()
  if (!message || isLoading.value) return

  if (!socket.value || !isConnected.value) {
    messages.value.push({
      sender: 'ai',
      text: '目前尚未連上後端 AI 服務，請確認 Flask SocketIO 伺服器已啟動。',
    })
    return
  }

  messages.value.push({
    sender: 'user',
    text: message,
  })

  socket.value.emit('user_message', {
    message,
    session_id: sessionId.value,
  })

  inputText.value = ''
  isLoading.value = true
}

watch(messages, scrollToBottom, { deep: true })
watch(isLoading, scrollToBottom)

onMounted(() => {
  sessionId.value = getOrCreateSessionId()
  connectSocket()
})

onUnmounted(() => {
  socket.value?.disconnect()
})
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
      <section
        v-if="isOpen"
        class="mb-4 flex h-[560px] w-[390px] flex-col overflow-hidden rounded-2xl border border-gray-100 bg-white shadow-2xl"
      >
        <header class="flex items-center justify-between bg-green-700 px-5 py-4 text-white">
          <div>
            <h3 class="text-lg font-bold tracking-wide">AI 永續旅伴</h3>
            <p class="text-sm text-green-100">
              {{ isConnected ? '已連線至共生東京 RAG' : '正在連線後端服務' }}
            </p>
          </div>
          <button
            type="button"
            class="text-2xl leading-none text-white hover:text-green-100"
            aria-label="關閉聊天視窗"
            @click="isOpen = false"
          >
            &times;
          </button>
        </header>

        <div ref="chatBodyRef" class="flex-1 overflow-y-auto bg-gray-50 p-5">
          <div class="flex flex-col gap-4">
            <div
              v-for="(msg, index) in messages"
              :key="index"
              :class="['flex', msg.sender === 'user' ? 'justify-end' : 'justify-start']"
            >
              <div
                :class="[
                  'max-w-[82%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm',
                  msg.sender === 'user'
                    ? 'rounded-tr-sm bg-green-600 text-white'
                    : 'rounded-tl-sm border border-gray-100 bg-white text-gray-800',
                ]"
              >
                <span v-if="msg.sender === 'user'">{{ msg.text }}</span>
                <span v-else class="chat-message-content" v-html="formatMessage(msg.text)"></span>
              </div>
            </div>

            <div v-if="isLoading" class="flex justify-start">
              <div
                class="max-w-[88%] rounded-2xl rounded-tl-sm border border-gray-100 bg-white px-4 py-2.5 text-sm leading-relaxed text-gray-600 shadow-sm"
              >
                ⚡ AI 永續旅伴正在查閱台東區避雷針大數據...
              </div>
            </div>
          </div>
        </div>

        <form class="flex gap-2 border-t border-gray-100 bg-white p-4" @submit.prevent="sendMessage">
          <input
            v-model="inputText"
            type="text"
            placeholder="輸入您的旅遊需求..."
            class="flex-1 rounded-full border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
          />
          <button
            type="submit"
            :disabled="isLoading || !inputText.trim()"
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-green-600 text-white shadow-sm transition-colors hover:bg-green-700 disabled:cursor-not-allowed disabled:bg-gray-300"
            aria-label="送出訊息"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke-width="2"
              stroke="currentColor"
              class="ml-1 h-5 w-5"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
              />
            </svg>
          </button>
        </form>
      </section>
    </transition>

    <button
      v-if="!isOpen"
      type="button"
      class="flex h-16 w-16 items-center justify-center rounded-full bg-green-600 text-white shadow-2xl transition-all hover:scale-105 hover:bg-green-700"
      aria-label="開啟 AI 永續旅伴"
      @click="isOpen = true"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke-width="1.5"
        stroke="currentColor"
        class="h-8 w-8"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"
        />
      </svg>
    </button>
  </div>
</template>

<style scoped>
:deep(.chat-message-content strong) {
  font-weight: 700;
  color: #111827;
}

:deep(.chat-heading) {
  margin-top: 0.75rem;
  margin-bottom: 0.35rem;
  font-weight: 700;
  color: #166534;
}

:deep(.chat-heading:first-child) {
  margin-top: 0;
}

:deep(.chat-list-item) {
  margin-top: 0.25rem;
  padding-left: 0.15rem;
}
</style>
