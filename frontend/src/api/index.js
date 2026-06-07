import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json'
  }
});

export const workflows = {
  list: () => api.get('/workflows'),
  get: (id) => api.get(`/workflows/${id}`),
  create: (data) => api.post('/workflows', data),
  update: (id, data) => api.put(`/workflows/${id}`, data),
  delete: (id) => api.delete(`/workflows/${id}`),
  execute: (id) => api.post(`/workflows/${id}/execute`),
  getExecutions: (id) => api.get(`/workflows/${id}/executions`),
  getNodeTypes: () => api.get('/workflows/node-types')
};

export const executions = {
  list: () => api.get('/executions'),
  get: (id) => api.get(`/executions/${id}`),
  getLogs: (id) => api.get(`/executions/${id}/logs`),
  pause: (id) => api.post(`/executions/${id}/pause`),
  resume: (id) => api.post(`/executions/${id}/resume`),
  terminate: (id) => api.post(`/executions/${id}/terminate`)
};

export default api;
