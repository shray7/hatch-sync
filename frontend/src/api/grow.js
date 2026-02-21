import axios from "axios";
import { getAxiosWithCreds } from "./auth";

const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";
const REQUEST_TIMEOUT_MS = 120000; // 2 min for cold start + Hatch login + data fetch

export async function fetchGrowData() {
  const res = await axios.get(`${apiBase}/grow/data`, { timeout: REQUEST_TIMEOUT_MS });
  return res.data;
}

export async function fetchPhotos() {
  const res = await axios.get(`${apiBase}/grow/photos`, { timeout: REQUEST_TIMEOUT_MS });
  return res.data;
}

export async function deletePhoto(photoKey) {
  const client = getAxiosWithCreds();
  const res = await client.post(`${apiBase}/admin/photos/delete`, { photo_key: photoKey });
  return res.data;
}

