import { useCallback, useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { api } from "./api/client";
import { KnowledgeMapPage } from "./pages/KnowledgeMapPage";
import { NetworkPage } from "./pages/NetworkPage";
import { PaperDetailPage } from "./pages/PaperDetailPage";
import type { PapersResponse } from "./types/paper";

export default function App() {
  const [data, setData] = useState<PapersResponse | null>(null);

  const refresh = useCallback(async () => {
    const next = await api.getPapers();
    setData(next);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<KnowledgeMapPage data={data} refresh={refresh} />} />
        <Route path="/network" element={<NetworkPage data={data} />} />
        <Route path="/paper/:paperId" element={<PaperDetailPage />} />
      </Routes>
    </BrowserRouter>
  );
}
