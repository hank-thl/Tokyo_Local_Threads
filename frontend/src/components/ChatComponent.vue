<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { io } from 'socket.io-client'
import { fetchDocuments } from '@/services/api'

const SOCKET_URL =
  import.meta.env.VITE_SOCKET_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  'http://localhost:5000'

const STORAGE_KEY = 'tokyo_local_threads_session_id'

const router = useRouter()
const isOpen = ref(false)
const inputText = ref('')
const isLoading = ref(false)
const isConnected = ref(false)
const chatBodyRef = ref(null)
const socket = ref(null)
const sessionId = ref('')
const lastAiText = ref('')
const spotLinks = ref([])
const loadingDots = ref('.')
let loadingTimer = null
let spotLinksPromise = null
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

const normalizeLinkChar = (char) => {
  const charMap = {
    寿: '壽',
    浅: '淺',
    総: '總',
    舗: '舖',
  }

  return charMap[char] || char
}

const normalizeLinkName = (name) => {
  return [...escapeHtml(name).replace(/[\s　]+/g, '')].map(normalizeLinkChar).join('')
}

const buildNameVariants = (name) => {
  const trimmedName = name.trim()
  const compactName = trimmedName.replace(/[\s　]+/g, '')
  const variants = new Set([trimmedName, compactName])

  // Gemini 有時會把「淺草雷門店」拆成「淺草 雷門店」，這裡補常見地名斷詞。
  compactName
    .replace(/(淺草)(雷門)/g, '$1 $2')
    .replace(/(上野)(御徒町)/g, '$1 $2')
    .split('\n')
    .forEach((variant) => variants.add(variant))

  return [...variants].filter((variant) => normalizeLinkName(variant).length >= 2)
}

const buildSpotLinks = async () => {
  try {
    const documents = await fetchDocuments({ limit: 100 })
    mergeSpotLinkDocuments(documents)
  } catch (error) {
    console.error('無法建立聊天景點連結索引', error)
  }
}

const ensureSpotLinksReady = () => {
  if (!spotLinksPromise) {
    spotLinksPromise = buildSpotLinks()
  }

  return spotLinksPromise
}

const mergeSpotLinkDocuments = (documents) => {
  const links = [...spotLinks.value, ...buildLinksFromDocuments(documents)]

  const dedupedLinks = []
  links.forEach((link) => {
    const isDuplicated = dedupedLinks.some(
      existingLink => existingLink.id === link.id && existingLink.normalizedName === link.normalizedName
    )
    if (!isDuplicated) {
      dedupedLinks.push(link)
    }
  })

  spotLinks.value = dedupedLinks.sort((a, b) => b.normalizedName.length - a.normalizedName.length)
}

const isLinkNameWhitespace = (char) => {
  return /[\s　]/.test(char)
}

const matchSpotAt = (escapedText, startIndex, spot) => {
  if (isLinkNameWhitespace(escapedText[startIndex])) {
    return null
  }

  let textIndex = startIndex
  let nameIndex = 0

  while (textIndex < escapedText.length && nameIndex < spot.normalizedName.length) {
    const currentChar = escapedText[textIndex]

    if (isLinkNameWhitespace(currentChar)) {
      textIndex += 1
      continue
    }

    if (normalizeLinkChar(currentChar) !== spot.normalizedName[nameIndex]) {
      return null
    }

    textIndex += 1
    nameIndex += 1
  }

  if (nameIndex !== spot.normalizedName.length) {
    return null
  }

  return {
    spot,
    endIndex: textIndex,
  }
}

const buildLinksFromDocuments = (documents) => {
  const links = []

  documents.forEach((document) => {
    if (document.category !== 'restaurant') return

    const id = document._id || document.id
    const names = [document.name?.zh, document.name?.jp, document.name].filter(
      name => typeof name === 'string' && name
    )
    if (!id || names.length === 0) return

    names.forEach((name) => {
      buildNameVariants(name).forEach((variant) => {
        links.push({
          name,
          normalizedName: normalizeLinkName(variant),
          id,
        })
      })
    })
  })

  return links
}

const linkSpotNames = (escapedText, sources = []) => {
  const sourceLinks = buildLinksFromDocuments(sources)
  const links = [...sourceLinks, ...spotLinks.value].sort(
    (a, b) => b.normalizedName.length - a.normalizedName.length
  )
  let output = ''
  let index = 0

  while (index < escapedText.length) {
    const match = links
      .map((spot) => matchSpotAt(escapedText, index, spot))
      .find(Boolean)

    if (match) {
      const matchedText = escapedText.slice(index, match.endIndex)
      output += `<a href="/spot/${match.spot.id}" data-spot-id="${match.spot.id}" class="chat-spot-link">${matchedText}</a>`
      index = match.endIndex
    } else {
      output += escapedText[index]
      index += 1
    }
  }

  return output
}

const formatMessage = (text, sources = []) => {
  return linkSpotNames(escapeHtml(text), sources)
    .replace(/^### (.+)$/gm, '<div class="chat-heading">$1</div>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^\* (.+)$/gm, '<div class="chat-list-item">• $1</div>')
    .replace(/^- (.+)$/gm, '<div class="chat-list-item">• $1</div>')
    .replace(/\n/g, '<br>')
}

const extractIntroText = (text) => {
  return text.split(/\n\s*\n/)[0] || text
}

const extractClosingText = (text) => {
  const blocks = text.split(/\n\s*\n/).filter(Boolean)
  return blocks.length > 1 ? blocks[blocks.length - 1] : ''
}

const handleMessageClick = (event) => {
  const link = event.target.closest('[data-spot-id]')
  if (!link) return

  event.preventDefault()
  router.push({
    name: 'spot-detail',
    params: {
      spotId: link.dataset.spotId,
    },
  })
}

const openRecommendation = (recommendation) => {
  router.push({
    name: 'spot-detail',
    params: {
      spotId: recommendation.id,
    },
  })
}

const normalizeSources = (sources = []) => {
  const normalizedSources = []

  sources.forEach((source) => {
    if (source.category !== 'restaurant') return

    const id = source._id || source.id
    const nameZh = source.name?.zh || ''
    const nameJp = source.name?.jp || ''
    const displayName = nameZh || nameJp
    if (!id || !displayName) return

    const isDuplicated = normalizedSources.some((item) => item.id === id)
    if (isDuplicated) return

    normalizedSources.push({
      id,
      name: displayName,
      category: source.category || '',
    })
  })

  return normalizedSources
}

const normalizeRecommendations = (recommendations = []) => {
  return recommendations
    .filter((item) => item.id && item.name)
    .map((item) => ({
      id: item.id,
      name: item.name,
      nameJp: item.name_jp || '',
      reason: item.reason || '可作為台東區在地美食體驗選擇。',
      sdgTags: item.sdg_tags || [],
      crowdLevel: item.crowd_level || 3,
      crowdReason: item.crowd_reason || '',
    }))
}

const pushAiMessage = async (text, sources = [], recommendations = []) => {
  if (!text) return
  if (text === lastAiText.value) {
    isLoading.value = false
    return
  }

  await ensureSpotLinksReady()

  if (sources.length > 0) {
    mergeSpotLinkDocuments(sources)
  }

  messages.value.push({
    sender: 'ai',
    text,
    sources: normalizeSources(sources),
    recommendations: normalizeRecommendations(recommendations),
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
  socket.value.on('ai_response', async (data) => {
    await pushAiMessage(
      data?.answer || data?.message || 'AI 回覆格式有誤，請稍後再試。',
      data?.sources || [],
      data?.recommendations || []
    )
  })

  // 相容目前後端 sockets/chat.py 使用的 ai_message 事件。
  socket.value.on('ai_message', async (data) => {
    await pushAiMessage(
      data?.answer || data?.message || 'AI 回覆格式有誤，請稍後再試。',
      data?.sources || [],
      data?.recommendations || []
    )
  })
}

const sendMessage = async () => {
  const message = inputText.value.trim()
  if (!message || isLoading.value) return

  if (!socket.value || !isConnected.value) {
    messages.value.push({
      sender: 'ai',
      text: '目前尚未連上後端 AI 服務，請確認 Flask SocketIO 伺服器已啟動。',
    })
    return
  }

  await ensureSpotLinksReady()

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

const startLoadingDots = () => {
  if (loadingTimer) return

  loadingTimer = window.setInterval(() => {
    loadingDots.value = loadingDots.value.length >= 3 ? '.' : `${loadingDots.value}.`
  }, 500)
}

const stopLoadingDots = () => {
  if (!loadingTimer) return

  window.clearInterval(loadingTimer)
  loadingTimer = null
  loadingDots.value = '.'
}

watch(messages, scrollToBottom, { deep: true })
watch(isLoading, scrollToBottom)
watch(isLoading, (loading) => {
  if (loading) {
    startLoadingDots()
  } else {
    stopLoadingDots()
  }
})

onMounted(() => {
  sessionId.value = getOrCreateSessionId()
  connectSocket()
  ensureSpotLinksReady()
})

onUnmounted(() => {
  stopLoadingDots()
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

        <div ref="chatBodyRef" class="flex-1 overflow-y-auto bg-gray-50 p-5" @click="handleMessageClick">
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
                <template v-else>
                  <div v-if="msg.recommendations?.length" class="chat-message-content">
                    <p v-html="formatMessage(extractIntroText(msg.text), msg.sources || [])"></p>

                    <div class="mt-4 space-y-4">
                      <article
                        v-for="recommendation in msg.recommendations"
                        :key="recommendation.id"
                        class="border-t border-gray-100 pt-3 first:border-t-0 first:pt-0"
                      >
                        <button
                          type="button"
                          class="text-left text-base font-bold text-green-700 underline decoration-green-200 underline-offset-4 transition-colors hover:text-green-800"
                          @click.stop="openRecommendation(recommendation)"
                        >
                          {{ recommendation.name }}
                        </button>
                        <p
                          v-if="recommendation.nameJp && recommendation.nameJp !== recommendation.name"
                          class="mt-0.5 text-xs italic tracking-wide text-gray-400"
                        >
                          {{ recommendation.nameJp }}
                        </p>

                        <p class="mt-2">
                          <span class="font-semibold text-gray-800">推薦理由：</span>{{ recommendation.reason }}
                        </p>
                        <p class="mt-1">
                          <span class="font-semibold text-gray-800">永續標籤：</span>
                          <span v-if="recommendation.sdgTags.length">
                            {{ recommendation.sdgTags.map(tag => `#${tag}`).join(' ') }}
                          </span>
                          <span v-else>暫無標籤</span>
                        </p>
                        <p class="mt-1">
                          <span class="font-semibold text-gray-800">擁擠度：</span>
                          {{ recommendation.crowdLevel }}/5<span v-if="recommendation.crowdReason">，{{ recommendation.crowdReason }}</span>
                        </p>
                      </article>
                    </div>

                    <p
                      v-if="extractClosingText(msg.text)"
                      class="mt-4"
                      v-html="formatMessage(extractClosingText(msg.text), msg.sources || [])"
                    ></p>
                  </div>
                  <span v-else class="chat-message-content" v-html="formatMessage(msg.text, msg.sources || [])"></span>
                </template>
              </div>
            </div>

            <div v-if="isLoading" class="flex justify-start">
              <div
                class="max-w-[88%] rounded-2xl rounded-tl-sm border border-gray-100 bg-white px-4 py-2.5 text-sm leading-relaxed text-gray-600 shadow-sm"
              >
                <img
                  src="/icons/cat_walk.webp"
                  alt=""
                  class="mr-1.5 inline h-5 w-5 align-[-0.2em] object-contain"
                />
                <span>正在穿梭淺草與上野的巷弄...為您編織舒適的在地脈絡{{ loadingDots }}</span>
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

:deep(.chat-spot-link) {
  font-weight: 700;
  color: #047857;
  text-decoration: underline;
  text-underline-offset: 3px;
}

:deep(.chat-spot-link:hover) {
  color: #065f46;
}
</style>
