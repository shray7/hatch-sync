import { createRouter, createWebHistory } from "vue-router";
import DashboardView from "./views/DashboardView.vue";
import FeedingsView from "./views/FeedingsView.vue";
import DiapersView from "./views/DiapersView.vue";
import SleepView from "./views/SleepView.vue";
import WeightView from "./views/WeightView.vue";
import PhotosView from "./views/PhotosView.vue";

const routes = [
  { path: "/", name: "dashboard", component: DashboardView },
  { path: "/feedings", name: "feedings", component: FeedingsView },
  { path: "/diapers", name: "diapers", component: DiapersView },
  { path: "/sleep", name: "sleep", component: SleepView },
  { path: "/weight", name: "weight", component: WeightView },
  { path: "/photos", name: "photos", component: PhotosView }
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
});

export default router;

