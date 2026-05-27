## Project Basics
- Project Basics 定義 current platform 的使命、範疇、heavy-development 階段、技術棧與結構。
- Current development mode is Heavy Development / No Compatible Fallback; prioritize stabilizing the current product over preserving backward-compatible fallback paths.
- 任何影響整體協作與架構一致性的變更，必須先更新本區。
- 目前 UI 方向為 Next.js，API 方向為 FastAPI，compute plane 方向為 Julia Runner，Notebook 是研究 cockpit。
- backend 的責任邊界與內部藍圖由 `backend-architecture.md` 定義。
- 舊的 command workflow、retired Python UI runtime、separate queue worker runtime 與 Python in-process Julia runtime 視為 migration legacy，不應再成為新功能的預設落點。
