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
  best_for?: string[] | string;
  difficulty?: string;
  audience?: string[];
  model_score?: number;
  related_concepts?: string[];
  semantic_cluster?: string;
  deep_metadata?: DeepMetadata;
  canonical_topics?: string[];
  tfidf_keywords?: string[];
  topic_tags?: string[];
  synthetic_questions?: string[];
  topic?: string;
  subtopic?: string;
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
    const limit = opts?.limit || 15;
    const scored: { item: ContentItem; score: number }[] = [];

    // Tokenize: lowercase, normalize hyphens, split on whitespace
    const normalized = query.toLowerCase().replace(/-/g, " ");
    const allTokens = normalized.split(/\s+/).filter(t => t.length > 0);

    const STOP_WORDS = new Set(["the", "a", "an", "and", "or", "for", "in", "on", "of", "to", "with", "is", "are", "was", "by", "it", "its", "about"]);

    const TYPE_INTENTS: Record<string, string> = {
      package: "packages", packages: "packages", library: "packages", libraries: "packages",
      pip: "packages", npm: "packages", install: "packages", cran: "packages", tool: "packages", tools: "packages",
      paper: "papers", papers: "papers", study: "papers", research: "papers",
      book: "books", books: "books", textbook: "books",
      dataset: "datasets", datasets: "datasets",
      talk: "talks", talks: "talks", video: "talks", lecture: "talks",
      resource: "resources", resources: "resources", tutorial: "resources", guide: "resources",
      career: "career", job: "career", jobs: "career",
      community: "community", forum: "community", newsletter: "community",
    };

    // Separate content tokens from type-intent tokens
    const contentTokens: string[] = [];
    let detectedType: string | null = opts?.type || null; // explicit filter takes precedence
    for (const token of allTokens) {
      if (STOP_WORDS.has(token)) continue;
      if (!opts?.type && TYPE_INTENTS[token]) {
        detectedType = TYPE_INTENTS[token];
      } else {
        contentTokens.push(token);
      }
    }
    const searchTokens = contentTokens.length > 0 ? contentTokens : allTokens.filter(t => !STOP_WORDS.has(t));

    for (const item of this.items) {
      // Hard filters
      if (opts?.type && item.type !== opts.type) continue;
      if (opts?.category && item.category !== opts.category) continue;
      if (opts?.difficulty && item.difficulty !== opts.difficulty) continue;

      // Pre-compute lowercase searchable fields
      const name = (item.name || "").toLowerCase();
      const desc = (item.description || "").toLowerCase();
      const cat = (item.category || "").toLowerCase();
      const tags = (item.tags || []).map(t => t.toLowerCase());
      const bestFor = typeof item.best_for === "string"
        ? item.best_for.toLowerCase()
        : (item.best_for || []).map(b => b.toLowerCase()).join(" ");
      const cluster = (item.semantic_cluster || "").toLowerCase().replace(/-/g, " ");
      const related = (item.related_concepts || []).map(r => r.toLowerCase().replace(/-/g, " "));
      const canonical = (item.canonical_topics || []).map(c => c.toLowerCase().replace(/-/g, " "));
      const tfidf = (item.tfidf_keywords || []).map(k => k.toLowerCase().replace(/-/g, " "));
      const topicTags = (item.topic_tags || []).map(t => t.toLowerCase().replace(/-/g, " "));
      const topic = (item.topic || "").toLowerCase();
      const subtopic = (item.subtopic || "").toLowerCase();
      const syntheticQs = (item.synthetic_questions || []).map(q => q.toLowerCase());

      let totalScore = 0;
      let tokensMatched = 0;

      for (const token of searchTokens) {
        let tokenScore = 0;

        // Name matching
        if (name === token) tokenScore += 20;
        else if (name.includes(token)) tokenScore += 6;

        // Tags
        for (const tag of tags) { if (tag.includes(token)) tokenScore += 5; }

        // TF-IDF keywords
        for (const kw of tfidf) { if (kw.includes(token)) tokenScore += 5; }

        // Canonical topics
        for (const ct of canonical) { if (ct.includes(token)) tokenScore += 5; }

        // Semantic cluster
        if (cluster.includes(token)) tokenScore += 4;

        // Best-for
        if (bestFor.includes(token)) tokenScore += 4;

        // Topic / subtopic (papers)
        if (topic.includes(token)) tokenScore += 4;
        if (subtopic.includes(token)) tokenScore += 4;

        // Related concepts
        for (const rc of related) { if (rc.includes(token)) tokenScore += 3; }

        // Topic tags
        for (const tt of topicTags) { if (tt.includes(token)) tokenScore += 3; }

        // Description
        if (desc.includes(token)) tokenScore += 2;

        // Category
        if (cat.includes(token)) tokenScore += 2;

        // Synthetic questions (light weight, break on first match)
        for (const sq of syntheticQs) { if (sq.includes(token)) { tokenScore += 1; break; } }

        if (tokenScore > 0) tokensMatched++;
        totalScore += tokenScore;
      }

      // Skip items with no keyword relevance
      if (totalScore === 0) continue;

      // All-terms-present bonus: 50% boost when every search token matches
      if (searchTokens.length > 1 && tokensMatched === searchTokens.length) {
        totalScore *= 1.5;
      }

      // Full phrase bonus
      const phraseQuery = searchTokens.join(" ");
      if (searchTokens.length > 1) {
        if (name.includes(phraseQuery)) totalScore += 10;
        if (desc.includes(phraseQuery)) totalScore += 3;
      }

      // Type-intent bonus: multiplicative so it proportionally rewards relevant items
      if (detectedType && item.type === detectedType) {
        totalScore *= 1.3;
      }

      // Model score as tiebreaker only (max 0.5 points)
      if (item.model_score) {
        totalScore += item.model_score * 0.5;
      }

      scored.push({ item, score: totalScore });
    }

    return scored.sort((a, b) => b.score - a.score).slice(0, limit).map(s => s.item);
  }

  findByTechnique(technique: string, type?: string): ContentItem[] {
    const q = technique.toLowerCase();
    return this.items.filter(item => {
      if (type && item.type !== type) return false;
      const bf = typeof item.best_for === "string" ? [item.best_for] : (item.best_for || []);
      const text = [item.name, item.description, ...(item.tags || []), ...bf].join(" ").toLowerCase();
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
