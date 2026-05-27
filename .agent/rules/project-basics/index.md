## Project Basics
- Project Basics 定義 current platform 的使命、範疇、heavy-development 階段、技術棧與結構。
- Current development mode is Heavy Development / No Compatible Fallback; prioritize stabilizing the current product over preserving backward-compatible fallback paths.
- 任何影響整體協作與架構一致性的變更，必須先更新本區。
- 目前 UI 方向為 Next.js，API 方向為 FastAPI，CLI 必須保留且與核心能力一致。
- backend 的責任邊界與內部藍圖由 `backend-architecture.md` 定義。
- 舊的 NiceGUI 程式碼視為 migration legacy，不應再成為新功能的預設落點。
