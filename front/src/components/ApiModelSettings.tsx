import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type {
  Category,
  CategoryPayload,
  MineruSettingsPayload,
  ModelSettingsPayload
} from "../types/paper";

type Props = {
  open: boolean;
  onClose: () => void;
  categories: Category[];
  onCollectionChanged: () => Promise<void>;
};

type SettingsTab = "api" | "categories" | "mineru";

const providerDefaults = {
  openai: {
    base_url: "https://api.openai.com/v1",
    model: "gpt-4o-mini"
  },
  anthropic: {
    base_url: "https://api.anthropic.com",
    model: "claude-3-5-sonnet-latest"
  }
};

function createDraftCategory(seed: number): CategoryPayload {
  return {
    id: `category_${seed}`,
    name: `新类别 ${seed}`,
    folder: `新类别_${seed}`,
    why: "",
    advantages: "",
    disadvantages: ""
  };
}

export function ApiModelSettings({ open, onClose, categories, onCollectionChanged }: Props) {
  const [activeTab, setActiveTab] = useState<SettingsTab>("api");
  const [form, setForm] = useState<ModelSettingsPayload>({
    provider: "openai",
    api_key: "",
    base_url: providerDefaults.openai.base_url,
    model: providerDefaults.openai.model,
    temperature: 0.2,
    max_tokens: 4096
  });
  const [configured, setConfigured] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [categoryList, setCategoryList] = useState<Category[]>(categories);
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(categories[0]?.id ?? null);
  const [categoryForm, setCategoryForm] = useState<CategoryPayload | null>(categories[0] ?? null);
  const [categoryMessage, setCategoryMessage] = useState("");
  const [categorySaving, setCategorySaving] = useState(false);
  const [mineruForm, setMineruForm] = useState<MineruSettingsPayload>({
    api_token: "",
    api_base_url: "https://mineru.net",
    backend: "pipeline",
    lang: "ch",
    api_timeout: 600
  });
  const [mineruConfigured, setMineruConfigured] = useState(false);
  const [mineruSaving, setMineruSaving] = useState(false);
  const [mineruMessage, setMineruMessage] = useState("");

  useEffect(() => {
    if (!open) return;

    setActiveTab("api");
    setCategoryMessage("");
    setMineruMessage("");

    api.getModelSettings().then((settings) => {
      setForm((current) => ({
        ...current,
        provider: settings.provider,
        base_url: settings.base_url,
        model: settings.model,
        temperature: settings.temperature,
        max_tokens: settings.max_tokens
      }));
      setConfigured(settings.api_key_configured);
    });

    api.getMineruSettings().then((settings) => {
      setMineruForm((current) => ({
        ...current,
        api_base_url: settings.api_base_url,
        backend: settings.backend,
        lang: settings.lang,
        api_timeout: settings.api_timeout
      }));
      setMineruConfigured(settings.api_token_configured);
    });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    setCategoryList(categories);
    setSelectedCategoryId((current) => {
      if (current && categories.some((item) => item.id === current)) return current;
      return categories[0]?.id ?? null;
    });
  }, [categories, open]);

  const selectedCategory = useMemo(
    () => categoryList.find((item) => item.id === selectedCategoryId) ?? null,
    [categoryList, selectedCategoryId]
  );

  useEffect(() => {
    if (!selectedCategory) {
      setCategoryForm(null);
      return;
    }
    setCategoryForm({
      id: selectedCategory.id,
      name: selectedCategory.name,
      folder: selectedCategory.folder,
      why: selectedCategory.why,
      advantages: selectedCategory.advantages,
      disadvantages: selectedCategory.disadvantages
    });
  }, [selectedCategory]);

  if (!open) return null;

  const onProviderChange = (provider: "openai" | "anthropic") => {
    setForm((current) => ({
      ...current,
      provider,
      base_url: providerDefaults[provider].base_url,
      model: providerDefaults[provider].model
    }));
  };

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      await api.saveModelSettings(form);
      setConfigured(true);
      setForm((current) => ({ ...current, api_key: "" }));
      setMessage("模型配置已保存到后端 .env。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveMineru = async (event: React.FormEvent) => {
    event.preventDefault();
    setMineruSaving(true);
    setMineruMessage("");
    try {
      const summary = await api.saveMineruSettings(mineruForm);
      setMineruConfigured(summary.api_token_configured);
      setMineruForm((current) => ({ ...current, api_token: "" }));
      setMineruMessage("MinerU 配置已保存到后端 .env，后续上传的 PDF 将自动走云端解析。");
    } catch (error) {
      setMineruMessage(error instanceof Error ? error.message : "保存失败");
    } finally {
      setMineruSaving(false);
    }
  };

  const handleAddCategory = async () => {
    const seed = Date.now();
    const draft = createDraftCategory(seed);
    setCategorySaving(true);
    setCategoryMessage("");
    try {
      const nextCategories = await api.createCategory(draft);
      setCategoryList(nextCategories);
      setSelectedCategoryId(draft.id);
      setCategoryForm(draft);
      setCategoryMessage("新类别已创建，可以继续修改详细参数。");
      await onCollectionChanged();
    } catch (error) {
      setCategoryMessage(error instanceof Error ? error.message : "创建类别失败");
    } finally {
      setCategorySaving(false);
    }
  };

  const handleDeleteCategory = async () => {
    if (!selectedCategoryId) return;
    setCategorySaving(true);
    setCategoryMessage("");
    try {
      await api.deleteCategory(selectedCategoryId);
      const nextCategories = await api.getCategories();
      setCategoryList(nextCategories);
      setSelectedCategoryId(nextCategories[0]?.id ?? null);
      setCategoryMessage("类别已删除，并已同步更新论文分类。");
      await onCollectionChanged();
    } catch (error) {
      setCategoryMessage(error instanceof Error ? error.message : "删除类别失败");
    } finally {
      setCategorySaving(false);
    }
  };

  const handleSaveCategory = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedCategoryId || !categoryForm) return;

    setCategorySaving(true);
    setCategoryMessage("");
    try {
      await api.updateCategory(selectedCategoryId, categoryForm);
      const nextCategories = await api.getCategories();
      setCategoryList(nextCategories);
      setSelectedCategoryId(categoryForm.id);
      setCategoryMessage("类别信息已保存到 papers.json。");
      await onCollectionChanged();
    } catch (error) {
      setCategoryMessage(error instanceof Error ? error.message : "保存类别失败");
    } finally {
      setCategorySaving(false);
    }
  };

  return (
    <div className="overlay" role="dialog" aria-modal="true">
      <div className="modal-card settings-modal-card">
        <div className="modal-head">
          <div>
            <p className="eyebrow">Settings Workspace</p>
            <h2>项目设置</h2>
          </div>
          <button className="hero-action-btn" type="button" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="settings-shell">
          <aside className="settings-sidebar">
            <button
              className={`settings-nav-btn ${activeTab === "api" ? "active" : ""}`}
              type="button"
              onClick={() => setActiveTab("api")}
            >
              API Key 设置
            </button>
            <button
              className={`settings-nav-btn ${activeTab === "categories" ? "active" : ""}`}
              type="button"
              onClick={() => setActiveTab("categories")}
            >
              设置类别
            </button>
            <button
              className={`settings-nav-btn ${activeTab === "mineru" ? "active" : ""}`}
              type="button"
              onClick={() => setActiveTab("mineru")}
            >
              PDF 解析
            </button>
          </aside>
          <section className="settings-panel">
            {activeTab === "mineru" ? (
              <form className="settings-form" onSubmit={handleSaveMineru}>
                <div className="category-settings-head">
                  <div>
                    <h3>PDF 解析（MinerU 远程）</h3>
                    <p className="modal-note">
                      配置后所有 PDF 自动走云端解析，适合扫描版、复杂排版或公式密集的论文。未配置时回退到本地解析（PyMuPDF / pypdf）。
                      请先在 <a href="https://mineru.net" target="_blank" rel="noreferrer">mineru.net</a> 注册并获取 API Token。
                    </p>
                  </div>
                </div>
                <label className="search-field">
                  <span className="search-label">API Token</span>
                  <input
                    type="password"
                    value={mineruForm.api_token}
                    placeholder={mineruConfigured ? "已配置，可输入新 Token 覆盖" : "请输入 MinerU API Token"}
                    onChange={(event) => setMineruForm({ ...mineruForm, api_token: event.target.value })}
                  />
                </label>
                <label className="search-field">
                  <span className="search-label">服务地址</span>
                  <input
                    value={mineruForm.api_base_url}
                    onChange={(event) => setMineruForm({ ...mineruForm, api_base_url: event.target.value })}
                  />
                </label>
                <label className="search-field">
                  <span className="search-label">解析后端</span>
                  <select
                    value={mineruForm.backend}
                    onChange={(event) => setMineruForm({ ...mineruForm, backend: event.target.value as "pipeline" | "vlm" })}
                  >
                    <option value="pipeline">pipeline（通用版，速度快）</option>
                    <option value="vlm">vlm（VLM 版，复杂版面更强）</option>
                  </select>
                </label>
                <label className="search-field">
                  <span className="search-label">语言</span>
                  <input
                    value={mineruForm.lang}
                    placeholder="如 ch / en / auto"
                    onChange={(event) => setMineruForm({ ...mineruForm, lang: event.target.value })}
                  />
                </label>
                <label className="search-field">
                  <span className="search-label">单次解析超时（秒）</span>
                  <input
                    type="number"
                    min={60}
                    value={mineruForm.api_timeout}
                    onChange={(event) => setMineruForm({ ...mineruForm, api_timeout: Number(event.target.value) })}
                  />
                </label>
                <div className="modal-actions">
                  <button className="hero-action-btn hero-network-btn" disabled={mineruSaving} type="submit">
                    {mineruSaving ? "保存中..." : "保存配置"}
                  </button>
                </div>
                <p className="search-status">
                  {mineruMessage || `当前状态：${mineruConfigured ? "MinerU Token 已配置" : "尚未配置 MinerU Token，将使用本地解析"}`}
                </p>
              </form>
            ) : activeTab === "api" ? (
              <form className="settings-form" onSubmit={onSubmit}>
                <label className="search-field">
                  <span className="search-label">Provider</span>
                  <select value={form.provider} onChange={(event) => onProviderChange(event.target.value as "openai" | "anthropic")}>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                  </select>
                </label>
                <label className="search-field">
                  <span className="search-label">API Key</span>
                  <input
                    type="password"
                    value={form.api_key}
                    placeholder={configured ? "已配置，可输入新 Key 覆盖" : "请输入 API Key"}
                    onChange={(event) => setForm({ ...form, api_key: event.target.value })}
                    required
                  />
                </label>
                <label className="search-field">
                  <span className="search-label">Base URL</span>
                  <input value={form.base_url} onChange={(event) => setForm({ ...form, base_url: event.target.value })} />
                </label>
                <label className="search-field">
                  <span className="search-label">Model</span>
                  <input value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })} />
                </label>
                <label className="search-field">
                  <span className="search-label">Temperature</span>
                  <input
                    type="number"
                    min={0}
                    max={2}
                    step={0.1}
                    value={form.temperature}
                    onChange={(event) => setForm({ ...form, temperature: Number(event.target.value) })}
                  />
                </label>
                <label className="search-field">
                  <span className="search-label">Max Tokens</span>
                  <input
                    type="number"
                    min={1}
                    value={form.max_tokens}
                    onChange={(event) => setForm({ ...form, max_tokens: Number(event.target.value) })}
                  />
                </label>
                <div className="modal-actions">
                  <button className="hero-action-btn hero-network-btn" disabled={saving} type="submit">
                    {saving ? "保存中..." : "保存配置"}
                  </button>
                </div>
                <p className="search-status">{message || `当前状态：${configured ? "API Key 已配置" : "尚未配置 API Key"}`}</p>
              </form>
            ) : (
              <div className="category-settings">
                <div className="category-settings-head">
                  <div>
                    <h3>类别设置</h3>
                    <p className="modal-note">管理类别名称、文件夹和说明信息；删除类别时会同步更新 papers.json 中论文的分类字段。</p>
                  </div>
                  <div className="category-actions">
                    <button className="hero-action-btn" disabled={categorySaving} type="button" onClick={handleAddCategory}>
                      添加类别
                    </button>
                    <button className="hero-action-btn" disabled={!selectedCategoryId || categorySaving} type="button" onClick={handleDeleteCategory}>
                      删除类别
                    </button>
                  </div>
                </div>
                <div className="category-chip-grid">
                  {categoryList.map((category) => (
                    <button
                      className={`category-chip-card ${selectedCategoryId === category.id ? "active" : ""}`}
                      key={category.id}
                      type="button"
                      onClick={() => setSelectedCategoryId(category.id)}
                    >
                      <span>{category.name}</span>
                    </button>
                  ))}
                </div>
                {categoryForm ? (
                  <form className="settings-form category-form" onSubmit={handleSaveCategory}>
                    <label className="search-field">
                      <span className="search-label">类别名称</span>
                      <input value={categoryForm.name} onChange={(event) => setCategoryForm({ ...categoryForm, name: event.target.value })} />
                    </label>
                    <label className="search-field">
                      <span className="search-label">类别 ID</span>
                      <input value={categoryForm.id} onChange={(event) => setCategoryForm({ ...categoryForm, id: event.target.value })} />
                    </label>
                    <label className="search-field">
                      <span className="search-label">文件夹名</span>
                      <input value={categoryForm.folder} onChange={(event) => setCategoryForm({ ...categoryForm, folder: event.target.value })} />
                    </label>
                    <label className="search-field">
                      <span className="search-label">为什么需要这一类</span>
                      <textarea rows={4} value={categoryForm.why} onChange={(event) => setCategoryForm({ ...categoryForm, why: event.target.value })} />
                    </label>
                    <label className="search-field">
                      <span className="search-label">优点</span>
                      <textarea rows={4} value={categoryForm.advantages} onChange={(event) => setCategoryForm({ ...categoryForm, advantages: event.target.value })} />
                    </label>
                    <label className="search-field">
                      <span className="search-label">缺点</span>
                      <textarea rows={4} value={categoryForm.disadvantages} onChange={(event) => setCategoryForm({ ...categoryForm, disadvantages: event.target.value })} />
                    </label>
                    <div className="modal-actions">
                      <button className="hero-action-btn hero-network-btn" disabled={categorySaving} type="submit">
                        {categorySaving ? "保存中..." : "保存类别"}
                      </button>
                    </div>
                    <p className="search-status">{categoryMessage || "点击上方类别方框可切换当前编辑类别。"}</p>
                  </form>
                ) : (
                  <p className="search-status">当前还没有类别，可先添加一个新类别。</p>
                )}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
