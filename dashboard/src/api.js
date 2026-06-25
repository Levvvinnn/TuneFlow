import axios from "axios";

const BASE = process.env.REACT_APP_ORCHESTRATOR_URL || "";

const api = axios.create({ baseURL: BASE });

export const startRun = (params) => api.post("/runs", params).then((r) => r.data);
export const getRunStatus = (runId) => api.get(`/runs/${runId}/status`).then((r) => r.data);
export const getRunHistory = (runId) => api.get(`/runs/${runId}/history`).then((r) => r.data);
export const compareRuns = (runA, runB) =>
  api.get(`/compare?run_a=${runA}&run_b=${runB}`).then((r) => r.data);
export const listRuns = () => api.get("/runs").then((r) => r.data);
