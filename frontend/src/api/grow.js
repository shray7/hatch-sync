import axios from "axios";

const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function fetchGrowData() {
  const res = await axios.get(`${apiBase}/grow/data`);
  return res.data;
}

export async function fetchPhotos() {
  const res = await axios.get(`${apiBase}/grow/photos`);
  return res.data;
}

