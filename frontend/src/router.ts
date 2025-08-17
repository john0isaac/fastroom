import {
  createRouter,
  createWebHistory,
  RouteRecordRaw,
  RouteLocationNormalized,
} from 'vue-router';
import { useAuthStore } from './stores/auth';

const Login = () => import('./pages/Login.vue');
const Register = () => import('./pages/Register.vue');
const Profile = () => import('./pages/Profile.vue');
const Rooms = () => import('./pages/Rooms.vue');
const RoomDetail = () => import('./pages/RoomDetail.vue');
const Home = () => import('./pages/Home.vue');

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: Home },
  { path: '/login', name: 'login', component: Login, meta: { guest: true } },
  {
    path: '/register',
    name: 'register',
    component: Register,
    meta: { guest: true },
  },
  {
    path: '/profile',
    name: 'profile',
    component: Profile,
    meta: { auth: true },
  },
  { path: '/rooms', name: 'rooms', component: Rooms, meta: { auth: true } },
  {
    path: '/rooms/:roomName',
    name: 'room',
    component: RoomDetail,
    meta: { auth: true },
    props: true,
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to: RouteLocationNormalized) => {
  const auth = useAuthStore();
  if (!auth.user && auth.access) {
    await auth.fetchProfile();
  }
  if (to.meta.auth && !auth.isAuthed) {
    return { name: 'login', query: { redirect: to.fullPath } };
  }
  if (to.meta.guest && auth.isAuthed) {
    return { name: 'home' };
  }
  return true;
});

export default router;
