import { z } from "zod";
import { DataLoader, ContentItem } from "./data-loader.ts";

export const CatalogSearchSchema = z.object({
  query: z.string().describe("Search query"),
  type: z.string().optional().describe("Filter by content type"),
  category: z.string().optional().describe("Filter by category"),
  difficulty: z.string().optional().describe("Filter by difficulty"),
  limit: z.number().optional().default(15).describe("Max results"),
});

export const FindByTechniqueSchema = z.object({
  technique: z.string().describe("Method/technique name"),
  type: z.string().optional().describe("Filter by content type"),
});

export const CompareItemsSchema = z.object({
  names: z.array(z.string()).min(2).max(5).describe("Item names to compare"),
});

export const LearningPathSchema = z.object({
  from_concept: z.string().describe("Starting concept"),
  to_concept: z.string().describe("Target concept"),
  audience: z.string().optional().describe("Audience level"),
});

export const ConceptGraphSchema = z.object({
  concept: z.string().describe("Concept or package to explore"),
  depth: z.number().optional().default(1).describe("Hops to traverse (1-3)"),
});

function formatItemCompact(item: ContentItem): string {
  const cat = item.category ? ` | ${item.category}` : "";
  const score = item.model_score !== undefined ? ` (score: ${item.model_score.toFixed(3)})` : "";
  return `- **${item.name}** [${item.type}${cat}] — ${(item.description || "").slice(0, 120)}${score}`;
}

export function catalogSearch(loader: DataLoader, input: z.infer<typeof CatalogSearchSchema>): string {
  const results = loader.searchText(input.query, { type: input.type, category: input.category, difficulty: input.difficulty, limit: input.limit });
  if (results.length === 0) return `No results for "${input.query}"`;
  return `Found ${results.length} results for "${input.query}":\n` + results.map(formatItemCompact).join("\n");
}

export function findByTechnique(loader: DataLoader, input: z.infer<typeof FindByTechniqueSchema>): string {
  const results = loader.findByTechnique(input.technique, input.type);
  if (results.length === 0) return `No items found for "${input.technique}"`;
  return `Items related to "${input.technique}":\n` + results.map(item => {
    const parts = [formatItemCompact(item)];
    if (item.deep_metadata?.methods) {
      const matching = item.deep_metadata.methods.filter(m => m.name.toLowerCase().includes(input.technique.toLowerCase()));
      if (matching.length) parts.push(`  Methods: ${matching.map(m => m.name + " — " + m.description).join("; ")}`);
    }
    return parts.join("\n");
  }).join("\n");
}

export function compareItems(loader: DataLoader, input: z.infer<typeof CompareItemsSchema>): string {
  const items: ContentItem[] = [];
  const notFound: string[] = [];
  for (const name of input.names) {
    const item = loader.findByNameFuzzy(name);
    if (item) items.push(item); else notFound.push(name);
  }
  if (items.length < 2) return `Not enough items found. Missing: ${notFound.join(", ")}`;
  const parts: string[] = [`## Comparison: ${items.map(i => i.name).join(" vs ")}\n`];
  if (notFound.length) parts.push(`(Not found: ${notFound.join(", ")})\n`);
  for (const item of items) {
    parts.push(`\n**${item.name}** [${item.type}]`);
    parts.push(`- ${item.description || "No description"}`);
    parts.push(`- Category: ${item.category || "N/A"}, Difficulty: ${item.difficulty || "N/A"}, Score: ${item.model_score?.toFixed(3) || "N/A"}`);
    if (item.deep_metadata) {
      const dm = item.deep_metadata;
      if (dm.strengths?.length) parts.push(`- Strengths: ${dm.strengths.join("; ")}`);
      if (dm.limitations?.length) parts.push(`- Limitations: ${dm.limitations.join("; ")}`);
      if (dm.methods?.length) parts.push(`- Methods: ${dm.methods.map(m => m.name).join(", ")}`);
    }
  }
  // Head-to-head comparison notes
  const hasDeep = items.filter(i => i.deep_metadata?.comparison_notes);
  for (const item of hasDeep) {
    for (const other of items) {
      if (other === item) continue;
      const note = item.deep_metadata!.comparison_notes![other.name || ""];
      if (note) parts.push(`\n**${item.name} vs ${other.name}**: ${note}`);
    }
  }
  return parts.join("\n");
}

export function learningPath(loader: DataLoader, input: z.infer<typeof LearningPathSchema>): string {
  const targetItems = loader.searchText(input.to_concept, { limit: 30 });
  const fromItems = loader.searchText(input.from_concept, { limit: 10 });
  const pathItems: ContentItem[] = [];
  pathItems.push(...fromItems.filter(i => i.difficulty === "beginner").slice(0, 2));
  pathItems.push(...targetItems.filter(i => i.difficulty === "intermediate" && !pathItems.includes(i)).slice(0, 3));
  pathItems.push(...targetItems.filter(i => !pathItems.includes(i)).slice(0, 3));
  const filtered = input.audience ? pathItems.filter(i => !i.audience || i.audience.includes(input.audience!)) : pathItems;
  const finalItems = filtered.length > 0 ? filtered : pathItems;
  if (finalItems.length === 0) return `No path from "${input.from_concept}" to "${input.to_concept}"`;
  const parts = [`## Learning Path: ${input.from_concept} -> ${input.to_concept}\n`];
  finalItems.forEach((item, i) => {
    parts.push(`### Step ${i + 1}: ${item.name} [${item.type}]`);
    parts.push(item.description || "");
    parts.push(`Difficulty: ${item.difficulty || "N/A"}`);
    if (item.url) parts.push(`URL: ${item.url}`);
    parts.push("");
  });
  return parts.join("\n");
}

export function conceptGraph(loader: DataLoader, input: z.infer<typeof ConceptGraphSchema>): string {
  const depth = Math.min(input.depth || 1, 3);
  const visited = new Set<string>();
  const edges: string[] = [];
  function explore(concept: string, d: number) {
    if (d > depth || visited.has(concept.toLowerCase())) return;
    visited.add(concept.toLowerCase());
    const byName = loader.findByNameFuzzy(concept);
    const bySearch = loader.searchText(concept, { limit: 10 });
    const all = new Map<string, ContentItem>();
    if (byName) all.set(byName.name || "", byName);
    for (const item of bySearch) all.set(item.name || "", item);
    for (const [name, item] of all) {
      if (item.deep_metadata?.relationships) {
        for (const rel of item.deep_metadata.relationships) {
          edges.push(`${name} --[${rel.type}]--> ${rel.target}${rel.note ? " (" + rel.note + ")" : ""}`);
          if (d < depth) explore(rel.target, d + 1);
        }
      }
      for (const rc of (item.related_concepts || []).slice(0, 5)) {
        if (!visited.has(rc.toLowerCase())) {
          edges.push(`${name} --[related]--> ${rc}`);
          if (d < depth) explore(rc, d + 1);
        }
      }
    }
  }
  explore(input.concept, 0);
  if (edges.length === 0) return `No graph for "${input.concept}"`;
  const unique = [...new Set(edges)];
  return `## Concept Graph: ${input.concept} (depth: ${depth})\n${visited.size} nodes, ${unique.length} edges\n\n` + unique.slice(0, 50).join("\n");
}
