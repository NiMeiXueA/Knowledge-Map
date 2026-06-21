import type { Category, Paper } from "../types/paper";
import { PaperCard } from "./PaperCard";

type Props = {
  categories: Category[];
  papers: Paper[];
  keyword: string;
};

function normalizeText(value: string) {
  return value.toLowerCase().replace(/\s+/g, "");
}

function innovationFocus(paper: Paper) {
  const seed = (paper.idea || paper.summary || paper.title).split(/[，。]/)[0].trim();
  return seed.length > 28 ? `${seed.slice(0, 28)}...` : seed;
}

export function CategoryTimeline({ categories, papers, keyword }: Props) {
  const normalized = normalizeText(keyword);
  const matched = (paper: Paper) => {
    if (!normalized) return true;
    const categoryNames = paper.categories
      .map((id) => categories.find((category) => category.id === id)?.name || id)
      .join(" ");
    const values = [
      paper.short,
      paper.title,
      paper.first_author,
      paper.venue ?? "",
      paper.idea,
      paper.innovation,
      String(paper.year ?? ""),
      categoryNames
    ];
    return values.some((value) => normalizeText(value).includes(normalized));
  };

  const sections = categories
    .map((category) => {
      const currentPapers = papers
        .filter((paper) => paper.categories.includes(category.id) && matched(paper))
        .sort((a, b) => (a.year ?? 9999) - (b.year ?? 9999) || a.short.localeCompare(b.short));
      return { category, papers: currentPapers };
    })
    .filter((item) => item.papers.length > 0);

  if (!sections.length) {
    return (
      <section className="search-empty">
        <h2>没有找到匹配论文</h2>
        <p>当前关键词没有命中结果。可以试试论文简称、作者、年份、会议或更短关键词。</p>
      </section>
    );
  }

  return (
    <div className="category-root">
      {sections.map(({ category, papers: currentPapers }) => {
        const byYear = new Map<number | null, Paper[]>();
        currentPapers.forEach((paper) => {
          const year = paper.year ?? 0;
          const existing = byYear.get(year) || [];
          existing.push(paper);
          byYear.set(year, existing);
        });

        return (
          <section className="category-panel" key={category.id}>
            <div className="category-head">
              <div>
                <p className="eyebrow">{category.name}</p>
                <h2>{category.name}</h2>
                <p>{category.why}</p>
              </div>
              <div className="category-overview">
                <article className="overview-box">
                  <h3>为什么需要这一类</h3>
                  <p>{category.why}</p>
                </article>
                <article className="overview-box">
                  <h3>优点</h3>
                  <p>{category.advantages}</p>
                </article>
                <article className="overview-box">
                  <h3>缺点</h3>
                  <p>{category.disadvantages}</p>
                </article>
              </div>
            </div>
            <div className="timeline">
              {Array.from(byYear.entries()).map(([year, yearPapers]) => (
                <article className="year-branch" key={`${category.id}-${year}`}>
                  <div className="year-head">
                    <span className="year">{year || "未知"}</span>
                    <span className="chip">该年论文：{yearPapers.length} 篇</span>
                    <span className="chip">
                      创新主线：{yearPapers.map((paper) => innovationFocus(paper)).join(" / ")}
                    </span>
                  </div>
                  <div className="innovation-tree">
                    {yearPapers.map((paper) => (
                      <article className="innovation-branch" key={paper.id}>
                        <div className="innovation-label">
                          <span className="innovation-kicker">创新点</span>
                          <strong>{innovationFocus(paper)}</strong>
                        </div>
                        <div className="paper-grid">
                          <PaperCard paper={paper} categories={categories} />
                        </div>
                      </article>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
