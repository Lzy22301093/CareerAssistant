# CareerAssistant 项目指南

## 联网搜索规则（重要）

**禁止使用内置 WebSearch 工具**，它在当前环境下不可用。

需要搜索网页时，必须使用以下方式之一：
- Firecrawl MCP 工具：`mcp__firecrawl__firecrawl_search`
- Firecrawl CLI：`npx firecrawl-cli search "关键词" --limit N`

需要抓取网页内容时，使用：
- Firecrawl MCP 工具：`mcp__firecrawl__firecrawl_scrape`
- Firecrawl CLI：`npx firecrawl-cli scrape "URL"`
