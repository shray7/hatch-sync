import axios from "axios";

const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";

const axiosWithCreds = axios.create({
  baseURL: apiBase,
  withCredentials: true,
  timeout: 15000
});

export function getAuthLoginUrl(nextPath = "/admin") {
  const next = nextPath.startsWith("/") ? nextPath : `/${nextPath}`;
  return `${apiBase}/auth/google?next=${encodeURIComponent(next)}`;
}

export async function fetchAuthMe() {
  const res = await axiosWithCreds.get("/auth/me");
  return res.data;
}

export async function authLogout() {
  const res = await axiosWithCreds.post("/auth/logout");
  return res.data;
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

export async function fetchGooglePhotosList(pageSize = 50, pageToken = null) {
  const params = { pageSize };
  if (pageToken) params.pageToken = pageToken;
  const res = await axiosWithCreds.get("/admin/google-photos/list", { params, timeout: 30000 });
  return res.data;
}

export async function importFromGooglePhotos(mediaItemIds) {
  const res = await axiosWithCreds.post("/admin/google-photos/import", { media_item_ids: mediaItemIds }, { timeout: 120000 });
  return res.data;
}
