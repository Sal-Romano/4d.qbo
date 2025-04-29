import axios from 'axios';

// API base URL
const API_BASE_URL = '/api.v1';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 seconds
  headers: {
    'Content-Type': 'application/json',
  },
});

// Future authentication header can be added here
// api.interceptors.request.use(config => {
//   const token = localStorage.getItem('token');
//   if (token) {
//     config.headers.Authorization = `Bearer ${token}`;
//   }
//   return config;
// });

// API endpoints
export const syncService = {
  /**
   * Initiate a manual sync process
   * @param fromDate Optional date to sync from
   * @param debug Whether to save debug files
   */
  initiateSync: async (fromDate?: string, debug: boolean = false) => {
    const params = new URLSearchParams();
    if (fromDate) params.append('from_date', fromDate);
    if (debug) params.append('debug', 'true');
    
    const response = await api.get(`/sync/initiate?${params.toString()}`);
    return response.data;
  },
  
  /**
   * Check API status
   */
  checkStatus: async () => {
    const response = await api.get('/status');
    return response.data;
  }
};

export default api; 