import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: BASE_URL });

export const analizarZona = (coordenadas) =>
  api.post('/api/v1/analizar', coordenadas);

export const obtenerEscenarios = (zonaId) =>
  api.get(`/api/v1/escenarios/${zonaId}`);

export const listarZonasMock = () =>
  api.get('/api/v1/mock/zonas');

export default api;
