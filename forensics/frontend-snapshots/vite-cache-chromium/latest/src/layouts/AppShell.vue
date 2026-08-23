<script setup lang="ts">
import AppSidebar from '../components/core/AppSidebar.vue'
import AppTopbar from '../components/core/AppTopbar.vue'
</script>

<template>
  <div class="app-shell">
    <AppSidebar />
    <main class="content">
      <AppTopbar />
      <section class="page-wrap">
        <NuxtPage />
      </section>
    </main>
  </div>
</template>
