import axios from "axios";

const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function fetchHealth() {
  const res = await axios.get(`${apiBase}/health`, { timeout: 15000 });
  return res.data;
}
