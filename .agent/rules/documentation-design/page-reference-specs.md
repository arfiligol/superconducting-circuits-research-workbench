## Page Reference Specs
- **Type**: App frontend page 技術文件必須寫成 Page Reference Spec，不是需求文件、散文或實作筆記
- **Diataxis**: 這類文件屬於 `Reference`
- **Now-only**: 只寫當前正式頁面契約；不要寫舊版/legacy/migration 歷史
- **Title alignment**: 文件 `title` 與 H1 必須優先對齊 sidebar / nav label；route 另寫在 frontmatter `route` 與正文 identity
- **Observed input**: 其他 Agent 抽出的 page context、截圖整理、現有 UI inventory 只能當輸入材料，不能直接當正式 spec
- **Normalization**: 輸入材料必須重新整理成 8 個固定區塊；`Unknown from current page context` 不得直接留在正式 SoT
- **Current product wins**: 若目前產品已要求 task management、result recovery、research workflow 等能力，正式 spec 必須納入，不受舊畫面限制
- **Fixed sections**: 必須包含 8 個區塊：
  1. Purpose
  2. User Goal
  3. Layout Structure
  4. Component Inventory
  5. Data & State Contract
  6. Interaction Flows
  7. Visual Rules
  8. Acceptance Checklist
- **Optional sections**: `Related Contracts`、`Runtime Notes` 只在需要時加入
- **Focus**: 先寫 page purpose、layout、components、state、flows、acceptance；不要先寫框架細節
- **Do not include**: framework 實作細節、repository/service 類名、pixel 級 CSS、歷史背景
- **Naming**: 新頁面優先使用 `docs/reference/app/frontend/pages/<route-name>.md`，並與 sidebar IA 對齊
