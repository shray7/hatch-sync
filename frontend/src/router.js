import { createRouter, createWebHistory } from "vue-router";
import DashboardView from "./views/DashboardView.vue";
import FeedingsView from "./views/FeedingsView.vue";
import DiapersView from "./views/DiapersView.vue";
import WeightView from "./views/WeightView.vue";
import PhotosView from "./views/PhotosView.vue";
import VideosView from "./views/VideosView.vue";
import AdminView from "./views/AdminView.vue";
const routes = [
  { path: "/", name: "dashboard", component: DashboardView },
  { path: "/feedings", name: "feedings", component: FeedingsView },
  { path: "/diapers", name: "diapers", component: DiapersView },
  { path: "/weight", name: "weight", component: WeightView },
  { path: "/photos", name: "photos", component: PhotosView },
  { path: "/videos", name: "videos", component: VideosView },
  { path: "/admin", name: "admin", component: AdminView }
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
});

export default router;

