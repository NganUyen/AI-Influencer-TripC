import axios from "axios";

import { getClientPublicEnvValue } from "@/lib/public-env";

const apiClient = axios.create({
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    config.baseURL =
      getClientPublicEnvValue("NEXT_PUBLIC_API_URL") || "http://localhost:3000";

    // Add auth token if available
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized
      localStorage.removeItem("access_token");
      window.location.href = "/ops/login";
    }
    return Promise.reject(error);
  },
);

export default apiClient;
