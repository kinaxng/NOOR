import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'
import { useTheme } from './composables/useTheme'

const app = createApp(App)
app.use(createPinia())
app.use(router)

// Initialize theme from localStorage before mounting
useTheme()

app.mount('#app')
