type Props = {
  keyword: string;
  open: boolean;
  onToggle: () => void;
  onChange: (value: string) => void;
};

export function PaperSearchPanel({ keyword, open, onToggle, onChange }: Props) {
  return (
    <>
      <button className="hero-action-btn" type="button" aria-expanded={open} onClick={onToggle}>
        论文搜索
      </button>
      {open ? (
        <div className="hero-search-panel">
          <div className="search-controls">
            <label className="search-field">
              <span className="search-label">关键词</span>
              <input
                type="search"
                placeholder="例如：fed / prompt / fairness / 2024 / McMahan"
                value={keyword}
                onChange={(event) => onChange(event.target.value)}
              />
            </label>
            <button className="search-clear" type="button" onClick={() => onChange("")}>
              清空
            </button>
          </div>
          <p className="search-status" aria-live="polite">
            {keyword ? `当前按关键词“${keyword}”筛选。` : "输入关键词后会按简称、标题、作者、年份、会议和方向实时筛选。"}
          </p>
        </div>
      ) : null}
    </>
  );
}
