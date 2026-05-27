---
aliases:
  - "Documentation Design"
  - "文件設計規範"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/documentation
status: stable
owner: docs-team
audience: team
scope: "文件設計規範索引：Standards / Zensical Native Style / Macro Style / Micro Style / Maintenance / Domain Extensions"
version: v2.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Documentation Design

文件設計規範索引，確保文件的一致性與可維護性（對齊本專案 `Native zh-TW Build` 架構）。

!!! info "How to read this section"
    先看 `Standards` 與 `Macro/Micro Style` 建立共通語法，再看 `Maintenance` 與 `Domain Extensions`。這頁是 documentation design 的入口，不是把每份子規範再重寫一次。

## Page Map

| 先讀什麼 | 目的 |
| --- | --- |
| Standards | 定義文件分類、frontmatter、核心邊界 |
| Macro Style / Information Layout | 決定頁面編排、資訊分層、overview/index 節奏 |
| Zensical Native Style | 決定 repo-local Zensical 原生文件節奏與呈現方式 |
| Micro Style / Writing & Visual Elements | 決定語氣、段落、admonitions、tabs 等元件使用 |
| Maintenance | 定義來源樹、更新流程、build/check |
| Domain Extensions | 對特定類型文件補更多專用寫法 |

## 快速參考

| 規範 | 說明 | Agent Rule |
|------|------|------------|
| [Standards](standards.md) | Diataxis + Frontmatter + 核心規則 | [#agent-rule](standards.md#agent-rule) |
| [Zensical Native Style](zensical-native-style.md) | 專案內 Zensical-native 寫作節奏與呈現方式 | [#agent-rule](zensical-native-style.md#agent-rule) |
| [Macro Style / Information Layout](information-layout.md) | 頁面資訊分層、視覺節奏、overview/index 編排 | [#agent-rule](information-layout.md#agent-rule) |
| [Micro Style / Writing & Visual Elements](style.md) | 語氣、段落寫法與 Admonitions/Tabs/Mermaid 等元件使用 | [#agent-rule](style.md#agent-rule) |
| [Maintenance](maintenance.md) | 單語來源樹 + Frontmatter 更新 + Zensical 檢查 | [#agent-rule](maintenance.md#agent-rule) |
| [Explanation Physics](explanation-physics.md) | Explanation/Physics 教學定位、章節骨架與跨文件引用規則 | [#agent-rule](explanation-physics.md#agent-rule) |
| [Page Reference Specs](page-reference-specs.md) | App frontend pages 技術文件的固定骨架、命名與驗收規則 | [#agent-rule](page-reference-specs.md#agent-rule) |

## 層級分工

| 規範 | 負責什麼 | 不負責什麼 |
|------|----------|------------|
| Standards | 文件分類、metadata、核心約束 | 頁面編排、語氣細節 |
| Zensical Native Style | 目前契約優先、happy path、examples、Zensical-native 呈現節奏 | Diataxis 邊界、build 維護流程 |
| Macro Style / Information Layout | 宏觀頁面編排、overview/index 規則、閱讀節奏 | 用字選擇、元件語法細節 |
| Micro Style / Writing & Visual Elements | 語氣、段落寫法、Admonitions/Tabs/Mermaid 等元件使用 | Diataxis 邊界、build 維護流程 |
| Maintenance | 單語來源樹、frontmatter 更新、build/check 流程 | 文件內容本身的結構設計 |
| Page Reference Specs | App frontend page 規格的固定骨架與驗收方式 | 其他類型文件的通用編排 |

!!! tip "Read order"
    若你只想快速把一頁寫對，通常的順序是 `Standards -> Zensical Native Style -> Macro Style -> Micro Style -> 該領域的 extension page`。

## Domain Extensions

這一層收錄和特定文件領域強相關的補充規範。它們不是 `Documentation Design` 的基礎規則，但會在特定內容類型中提供更細的寫法。

| 規範 | 用途 |
|------|------|
| [Page Reference Specs](page-reference-specs.md) | App frontend pages 的固定骨架、命名與驗收方式 |
| [Explanation Physics](explanation-physics.md) | Physics explanation 的敘事骨架、引用與邊界 |
| [Circuit Diagrams](../../../how-to/contributing/circuit-diagrams.md) | Schemdraw → SVG 的圖表寫作與輸出流程 |

## 正式術語

本專案在文件層的站點架構，正式名稱為：

- `Native zh-TW Build`

此術語代表：

- 使用單一設定檔：`zensical.toml`
- 使用單一 build，輸出到 `/`
- 編輯來源為 `docs/`，建置前產生 `docs/docs_zhtw/` staging tree
- 不再維護英文站點與 `.en.md` 對應頁

## Related

- 視覺圖表：
  - [Circuit Diagram Guide](../../../how-to/contributing/circuit-diagrams.md)（Schemdraw → SVG）
- App page specs：
  - [Page Reference Specs](./page-reference-specs.md)

---

## Agent Rule { #agent-rule }

```markdown
## Documentation Design
- **Standards**: Diataxis + Frontmatter/Tags + 核心規則（見 `standards.md`）
- **Zensical Native Style**: 目前契約優先、happy path、examples、Zensical-native 呈現節奏（見 `zensical-native-style.md`）
- **Macro Style / Information Layout**: 宏觀頁面編排、視覺節奏、overview/index 規則（見 `information-layout.md`）
- **Micro Style / Writing & Visual Elements**: 語氣、段落寫法與視覺元素使用（見 `style.md`）
- **Maintenance**: 單語來源樹 + Frontmatter 更新 + Zensical 檢查（見 `maintenance.md`）
- **Explanation Physics**: 教學定位、章節骨架、跨文件引用規範（見 `explanation-physics.md`）
- **Page Reference Specs**: App frontend page 技術文件的固定骨架、命名、引用與驗收規範（見 `page-reference-specs.md`）
- **Architecture Term**: 本專案文件架構的正式名稱是 `Native zh-TW Build`
- 詳細規範請以各子文件為準。
```
