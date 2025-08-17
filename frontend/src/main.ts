import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import { router } from './router';
import { installAuthInterceptors } from './plugins/authClient';

const app = createApp(App);
app.use(createPinia());
installAuthInterceptors();
app.use(router).mount('#app');
