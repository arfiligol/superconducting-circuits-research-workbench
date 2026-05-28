---
aliases:
  - "Documentation Information Layout"
  - "文件資訊編排"
  - "Macro Style"
  - "Information Layout"
tags:
  - diataxis/reference
  - audience/team
  - sot/true
  - topic/documentation
status: stable
owner: docs-team
audience: team
scope: "Macro Style / Information Layout：文件資訊分層、視覺節奏與 overview/index 頁的版面編排規範"
version: v0.3.0
last_updated: 2026-03-13
updated_by: team
---

# Macro Style / Information Layout

本文件定義 `Documentation Style` 的宏觀層，處理文件頁面的資訊編排規則。目標不是讓頁面更花，而是讓資訊落在正確的視覺層級，避免讀者一打開就看到文字牆或誤判頁面結構。

!!! info "對應的 Micro Style"
    本頁負責頁面節奏、容器分工與 overview/index 的呈現方式。
    語氣、段落寫法與元件語法則回到 [Micro Style / Writing & Visual Elements](./style.md) 查看。

---

## 核心原則

| 原則 | 說明 |
|------|------|
| 一節只回答一個問題 | 每個段落或小節應只處理一個主題，避免在同一區塊同時講目的、流程、例外與驗收。 |
| 先分層，再加密度 | 先把頁面切成清楚層級，再決定是否用表格、tabs 或 admonitions。不要先堆資訊再回頭補樣式。 |
| 容器必須有語意 | 表格、tabs、admonitions、摺疊區塊都必須對應明確用途，不能只為了讓畫面看起來比較豐富。 |
| 先掃讀，再細讀 | 頁面應允許讀者先靠標題、短導言、表格抓住骨架，再決定是否展開次要細節。 |
| Sidebar 與正文分工不同 | Sidebar 負責站點導覽；正文負責頁面解釋。不要把 sidebar 結構原樣複製到正文。 |
| 分組不是頁面 | `Workspace`、`Definition`、`Simulation Workbench` 這類 IA 分組必須明確標示為分組，不可寫得像缺少連結的獨立頁。 |

!!! tip "判斷標準"
    如果一段內容搬進不同視覺容器後，讀者更容易判斷「它是規格、對照、提醒，還是次要細節」，就代表編排方向是對的。

---

## 頁面節奏

建議先建立以下閱讀節奏，再視內容調整：

1. 頁面定位：標題 + 1 至 2 句導言。
2. 第一層骨架：用小節清楚分開不同問題。
3. 結構化事實：用表格、清單或 tabs 呈現穩定資訊。
4. 補充強調：只在必要處加入 admonitions 或可摺疊細節。
5. 收尾區塊：放 Related、驗收條件或 Agent Rule。

!!! info "預設閱讀路徑"
    讀者應該能只看標題、導言、表格標題，就先抓住頁面 60% 到 70% 的內容，再決定要不要深入閱讀正文。

---

## 容器選擇

| 容器 | 適合放什麼 | 不適合放什麼 |
|------|------------|--------------|
| 正文段落 | 正常說明、導言、短結論 | 長串規格、平行比較、反覆提醒 |
| 表格 | 穩定規格、欄位定義、分類對照 | 長篇解釋、故事式背景 |
| Tabs | 同層級變體、平行分類、情境切換 | 有先後順序的流程 |
| Admonitions | 需要語意強調的提醒、建議、風險、驗證 | 一般說明、每個小節的標準開場 |
| `???` | 次要細節、進階補充、邊界情境 | 主流程的核心定義 |
| Page Map / Link List | 真正存在的子頁入口 | 分組標籤、尚未存在的頁面名稱 |

!!! warning "避免容器濫用"
    不要把表格當成萬用格式，也不要為了拆掉文字牆就把整頁塞進 admonitions。容器越多，越需要確保每一種容器都在做不同工作。

---

## Overview 與 Index 頁規則

Overview / Index 頁最容易把 sidebar 結構原樣複製進正文，導致讀者誤以為分組本身也是一頁文件。這類頁面應優先做成「頁面地圖」，不是「導覽樹複寫」。

=== "應該做"

    - 先用短導言說明本區收錄什麼。
    - 用分組標題整理 IA，但每個分組下只列真正存在的文件頁。
    - 若分組名稱本身不是頁面，明確標記它只是分組。
    - 在每個連結後補一句簡短 focus，讓讀者知道應該去那頁查什麼。

=== "避免做"

    - 在正文重現一份和 sidebar 幾乎一模一樣的樹。
    - 讓分組標籤看起來像漏掉連結的頁面。
    - 同時出現 `Sections`、`Topics`、`Page Map` 三套重複結構。
    - 用長條列把整區頁面列完，卻沒有交代每頁責任。

!!! success "Overview 頁的正確狀態"
    讀者應能分辨：
    1. 哪些是分組。
    2. 哪些是真正存在的頁面。
    3. 每一頁大致負責什麼。

---

## 常見反模式

| 反模式 | 問題 | 建議修正 |
|--------|------|----------|
| 文字牆 | 讀者無法快速抓住頁面主題與層次 | 先拆成更小的小節，再決定哪些資訊適合進表格或 tabs |
| 裝飾性 admonitions | 框很多，但沒有明確語意差異 | 只保留真正需要強調的提醒，把一般說明移回正文 |
| 分組假裝成頁面 | 讀者會誤以為缺頁或 broken link | 分組標題只作為 IA label，連結只列實際文件 |
| 導覽樹複製貼上 | sidebar 與正文重複，畫面密度高但資訊量沒有增加 | 正文改寫成 page map 或責任摘要 |
| 一節混太多事 | 同時講定位、流程、邊界、例外，難以掃讀 | 把內容拆到不同小節，各自回答單一問題 |

---

## Related

- [Documentation Style](./style.md)
- [Documentation Standards](./standards.md)
- [Page Reference Specs](./page-reference-specs.md)

---

## Agent Rule { #agent-rule }

```markdown
## Macro Style / Information Layout
- 每個小節只回答一個主要問題；先建立資訊分層，再增加內容密度
- 正文、表格、tabs、admonitions、摺疊區塊都必須有明確語意，不可裝飾性使用
- 頁面應支援先掃讀再細讀：標題、導言、表格標題應能先傳達主要骨架
- Sidebar 是導覽；正文不是 sidebar 複寫
- Overview / Index 頁只列真正存在的頁面連結；IA 分組必須明確標示為分組，不可寫得像獨立頁
- 避免文字牆、容器濫用、分組假裝成頁面、以及重複的 `Sections/Topics/Page Map`
```
