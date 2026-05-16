<script setup>
import BannerConponent from '../components/BannerConponent.vue'
import NavConponent from '../components/NavConponent.vue'
import ChatWindow from '../components/ChatWindow.vue'
</script>

<template>
  <main class="bg-gray-50 min-h-screen relative">
    <BannerConponent />
    <NavConponent />
    <ChatWindow />
  </main>
</template>