import { API_BASE_URL } from "./config";
import type {
  Category,
  CategoryPayload,
  GraphPayload,
  MineruSettingsPayload,
  MineruSettingsSummary,
  ModelSettingsPayload,
  ModelSettingsSummary,
  Paper,
  PapersResponse,
  UploadTask
} from "../types/paper";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getPapers: () => request<PapersResponse>("/api/papers"),
  getPaper: (paperId: string) => request<Paper>(`/api/papers/${paperId}`),
  getGraph: () => request<GraphPayload>("/api/graph"),
  getCategories: () => request<Category[]>("/api/categories"),
  createCategory: (payload: CategoryPayload) =>
    request<Category[]>("/api/categories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }),
  updateCategory: (categoryId: string, payload: CategoryPayload) =>
    request<Category>(`/api/categories/${categoryId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }),
  deleteCategory: (categoryId: string) =>
    request<{ ok: boolean }>(`/api/categories/${categoryId}`, {
      method: "DELETE"
    }),
  getModelSettings: () => request<ModelSettingsSummary>("/api/settings/model"),
  saveModelSettings: (payload: ModelSettingsPayload) =>
    request<ModelSettingsSummary>("/api/settings/model", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }),
  getMineruSettings: () => request<MineruSettingsSummary>("/api/settings/mineru"),
  saveMineruSettings: (payload: MineruSettingsPayload) =>
    request<MineruSettingsSummary>("/api/settings/mineru", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }),
  uploadPapers: async (files: File[], references: string[]) => {
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    references.forEach((reference) => formData.append("references", reference));
    return request<{ task_id: string; status: string }>("/api/papers/upload", {
      method: "POST",
      body: formData
    });
  },
  getTask: (taskId: string) => request<UploadTask>(`/api/papers/tasks/${taskId}`)
};
