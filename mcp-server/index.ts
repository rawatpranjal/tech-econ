#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { DataLoader } from "./data-loader.ts";
import { CatalogSearchSchema, FindByTechniqueSchema, CompareItemsSchema, LearningPathSchema, ConceptGraphSchema, catalogSearch, findByTechnique, compareItems, learningPath, conceptGraph } from "./tools.ts";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, "..", "data");
const loader = new DataLoader(DATA_DIR);

const server = new McpServer({ name: "tech-econ-catalog", version: "1.0.0" });

server.tool("catalog_search", "Search the tech-econ.com content catalog across all types.", CatalogSearchSchema.shape, async ({ query, type, category, difficulty, limit }) => ({ content: [{ type: "text" as const, text: catalogSearch(loader, { query, type, category, difficulty, limit }) }] }));

server.tool("find_by_technique", "Find items implementing a specific method/technique.", FindByTechniqueSchema.shape, async ({ technique, type }) => ({ content: [{ type: "text" as const, text: findByTechnique(loader, { technique, type }) }] }));

server.tool("compare_items", "Compare 2-5 items side-by-side.", CompareItemsSchema.shape, async ({ names }) => ({ content: [{ type: "text" as const, text: compareItems(loader, { names }) }] }));

server.tool("learning_path", "Build a learning path between concepts.", LearningPathSchema.shape, async ({ from_concept, to_concept, audience }) => ({ content: [{ type: "text" as const, text: learningPath(loader, { from_concept, to_concept, audience }) }] }));

server.tool("concept_graph", "Explore relationships around a concept.", ConceptGraphSchema.shape, async ({ concept, depth }) => ({ content: [{ type: "text" as const, text: conceptGraph(loader, { concept, depth }) }] }));

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}
main().catch(console.error);
