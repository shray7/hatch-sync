import axios from "axios";

const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";

const TOKEN_KEY = "hatch_session_token";

// Read token from URL (OAuth redirect for mobile; avoids third-party cookie blocking).
(function initTokenFromUrl() {
  if (typeof window === "undefined") return;
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");
  if (token) {
    sessionStorage.setItem(TOKEN_KEY, token);
    params.delete("token");
    const newSearch = params.toString();
    const newUrl =
      window.location.pathname + (newSearch ? "?" + newSearch : "") + window.location.hash;
    window.history.replaceState({}, "", newUrl);
  }
})();

const axiosWithCreds = axios.create({
  baseURL: apiBase,
  withCredentials: true,
  timeout: 15000
});

axiosWithCreds.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function getAxiosWithCreds() {
  return axiosWithCreds;
}

export function getAuthLoginUrl(nextPath = "/admin") {
  const next = nextPath.startsWith("/") ? nextPath : `/${nextPath}`;
  return `${apiBase}/auth/google?next=${encodeURIComponent(next)}`;
}

export async function fetchAuthMe() {
  const res = await axiosWithCreds.get("/auth/me");
  return res.data;
}

export async function authLogout() {
  try {
    await axiosWithCreds.post("/auth/logout");
  } finally {
    sessionStorage.removeItem(TOKEN_KEY);
  }
}

export async function triggerSync() {
  const res = await axiosWithCreds.post("/sync", {}, { timeout: 120000 });
  return res.data;
}

export async function uploadFiles(files) {
  const formData = new FormData();
  for (let i = 0; i < files.length; i++) {
    formData.append("files", files[i]);
  }
  const res = await axiosWithCreds.post("/admin/upload", formData, {
    timeout: 120000,
    headers: { "Content-Type": "multipart/form-data" }
  });
  return res.data;
}

