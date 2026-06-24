import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const setAuthToken = (token) => {
  if (token) axios.defaults.headers.common.Authorization = `Bearer ${token}`;
  else delete axios.defaults.headers.common.Authorization;
};

// Multi-Entity (F0-B): konteks entitas aktif dikirim via header X-Entity-Id.
// Nilai "all" = mode oversight lintas-PT (hanya dihormati untuk role admin/manager).
export const setActiveEntity = (entityId) => {
  if (entityId) axios.defaults.headers.common["X-Entity-Id"] = entityId;
  else delete axios.defaults.headers.common["X-Entity-Id"];
};

export default axios;