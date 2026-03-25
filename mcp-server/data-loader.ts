import { readFileSync, readdirSync } from "fs";
import { join } from "path";

export interface DeepMetadata {
  methods?: { name: string; description: string }[];
  relationships?: { target: string; type: string; note?: string }[];
  strengths?: string[];
  limitations?: string[];
  comparison_notes?: Record<string, string>;
  math_level?: string;
  learning_context?: { prerequisites?: string[]; leads_to?: string[] };
}

export interface ContentItem {
  name?: string;
  title?: string;
  description?: string;
  category?: string;
  type?: string;
  url?: string;
  tags?: string[];
  best_for?: string[];
  difficulty?: string;
  audience?: string[];
  model_score?: number;
  related_concepts?: string[];
  semantic_cluster?: string;
  deep_metadata?: DeepMetadata;
  [key: string]: unknown;
}

const CONTENT_FILES: Record<string, string> = {
  packages: "packages.json",
  datasets: "datasets.json",
  resources: "resources.json",
  books: "books.json",
  talks: "talks.json",
  papers: "papers_flat.json",
  career: "career.json",
  community: "community.json",
};

export class DataLoader {
  private items: ContentItem[] = [];
  private byName: Map<string, ContentItem> = new Map();

  constructor(dataDir: string) {
    for (const [type, file] of Object.entries(CONTENT_FILES)) {
      try {
        const raw = JSON.parse(readFileSync(join(dataDir, file), "utf-8"));
        const arr: ContentItem[] = Array.isArray(raw) ? raw : Object.values(raw).flat();
        for (const item of arr) {
          item.type = type;
          item.name = item.name || item.title || "";
          this.items.push(item);
          if (item.name) this.byName.set(item.name.toLowerCase(), item);
        }
      } catch {
        // skip missing files
      }
    }
  }

  get count(): number { return this.items.length; }

  searchText(query: string, opts?: { type?: string; category?: string; difficulty?: string; limit?: number }): ContentItem[] {
    const q = query.toLowerCase();
    const limit = opts?.limit || 15;
    const scored: { item: ContentItem; score: number }[] = [];

    for (const item of this.items) {
      if (opts?.type && item.type !== opts.type) continue;
      if (opts?.category && item.category !== opts.category) continue;
      if (opts?.difficulty && item.difficulty !== opts.difficulty) continue;

      let score = 0;
      const name = (item.name || "").toLowerCase();
      const desc = (item.description || "").toLowerCase();
      const tags = (item.tags || []).map(t => t.toLowerCase());

      if (name.includes(q)) score += 10;
      if (name === q) score += 20;
      if (desc.includes(q)) score += 3;
      for (const tag of tags) { if (tag.includes(q)) score += 5; }
      if (item.best_for) {
        for (const bf of item.best_for) { if (bf.toLowerCase().includes(q)) score += 4; }
      }
      if (item.model_score) score += item.model_score;

      if (score > 0) scored.push({ item, score });
    }

    return scored.sort((a, b) => b.score - a.score).slice(0, limit).map(s => s.item);
  }

  findByTechnique(technique: string, type?: string): ContentItem[] {
    const q = technique.toLowerCase();
    return this.items.filter(item => {
      if (type && item.type !== type) return false;
      const text = [item.name, item.description, ...(item.tags || []), ...(item.best_for || [])].join(" ").toLowerCase();
      if (text.includes(q)) return true;
      if (item.deep_metadata?.methods?.some(m => m.name.toLowerCase().includes(q))) return true;
      return false;
    }).slice(0, 20);
  }

  findByNameFuzzy(name: string): ContentItem | undefined {
    const q = name.toLowerCase();
    const exact = this.byName.get(q);
    if (exact) return exact;
    for (const [key, item] of this.byName) {
      if (key.includes(q) || q.includes(key)) return item;
    }
    return undefined;
  }
}
