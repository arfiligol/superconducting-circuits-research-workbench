---
aliases:
  - About
  - 介紹
tags:
  - diataxis/explanation
  - audience/user
  - topic/project-overview
status: draft
owner: team
audience: user
scope: 從受眾、學習路徑與產品定位角度介紹本平台。
version: v0.3.0
last_updated: 2026-03-13
updated_by: team
title: 介紹
template: marketing.html
---

<section class="sc-marketing-page sc-marketing-page--about">
  <div class="sc-marketing-hero">
    <p class="sc-marketing-eyebrow">Superconducting Quantum Circuits Platform</p>
    <h1>把超導量子電路研究，整合成同一個平台。</h1>
    <p class="sc-marketing-lead">
      這個平台對應的是 chip iteration flow 中 fabrication 之外的主體：
      design、simulation、measurement、comparison 與 feedback。它同時整理兩條分析主軸：
      一條用 S/Y/Z Matrix 串起 layout simulation、circuit simulation 與 measurement；
      另一條從 circuit definition 走向量子化後的 Hamiltonian 描述，處理超導量子電路真正和傳統 photonics 分開的那一段。
    </p>
    <div class="sc-marketing-pills">
      <span>S / Y / Z Matrix</span>
      <span>Circuit Definition / Hamiltonian</span>
      <span>Design / Simulation / Measurement</span>
      <span>Comparison / Feedback</span>
    </div>
  </div>

  <div class="sc-marketing-band">
    <p>
      這不是只展示頁面與指令的文件站。這裡描述的是一個研究平台：
      研究者可以從 circuit definition 出發，接到 simulation、量測資料、結果比較與回饋修正，
      中間不需要在不同工具之間反覆手動對照語意。
    </p>
  </div>

  <section class="sc-marketing-section">
    <div class="sc-marketing-section__header">
      <p class="sc-marketing-kicker">Core Positioning</p>
      <h2>這個平台處理的，是 fabrication 之前與之後最常被拆散的那條研究鏈。</h2>
      <p>
        在超導量子電路研究裡，design、verification simulation 與 measurement
        經常各自有工具、各自有格式、各自有分析口徑。真正困難的地方不是少一個功能，
        而是缺少一個能把這三段接起來、又能往量子化模型延伸的共同系統。
      </p>
    </div>
    <div class="sc-feature-grid sc-feature-grid--compact">
      <article class="sc-feature-card">
        <h3>統一分析語言</h3>
        <p>以 S、Y、Z Matrix 作為重要入口，讓 layout simulation、circuit simulation 與 measurement 可以放在同一個分析框架裡閱讀。</p>
      </article>
      <article class="sc-feature-card">
        <h3>雙主軸分析</h3>
        <p>平台同時承接 network-level 的 S/Y/Z 分析，以及 circuit definition 到 Hamiltonian 的量子化分析，不把它們拆成兩個產品。</p>
      </article>
      <article class="sc-feature-card">
        <h3>量子化延伸</h3>
        <p>當 S/Y/Z 不足以描述量子化後的超導電路表現時，平台能往上接到等效模型、Hamiltonian 與像 pyEPR 這類從 layout simulation 萃取量子資訊的技術路線。</p>
      </article>
      <article class="sc-feature-card">
        <h3>統一比對依據</h3>
        <p>把 trace、result、dataset 與 provenance 保存為可回看的研究資產，讓 comparison 與 feedback 有明確的依據。</p>
      </article>
    </div>
  </section>

  <section class="sc-marketing-section">
    <div class="sc-marketing-section__header">
      <p class="sc-marketing-kicker">Iteration Flow</p>
      <h2>平台對應的是晶片迭代流程中，fabrication 之外的閉環。</h2>
      <p>
        研究從 design target 與 circuit definition 出發，經過 simulation 驗證、measurement 分析與 comparison，
        再把結果回饋到下一輪設計。這一頁描述的就是那條工作流本身，而不是單一頁面功能。
      </p>
    </div>
    <div class="sc-flow-grid">
      <article class="sc-flow-step">
        <span class="sc-flow-step__index">01</span>
        <h3>Design</h3>
        <p>從 target、system parameter、circuit parameter 到 circuit definition，固定研究對象與設計語意。</p>
      </article>
      <article class="sc-flow-step">
        <span class="sc-flow-step__index">02</span>
        <h3>Simulation</h3>
        <p>把 layout 與 circuit simulation 接到同一個分析座標，理解模型、參數與驗證結果之間如何映射。</p>
      </article>
      <article class="sc-flow-step">
        <span class="sc-flow-step__index">03</span>
        <h3>Measurement</h3>
        <p>把量測資料帶回相同的分析語言，讓實驗結果與模擬結果能直接比較，而不是停留在不同格式的報表。</p>
      </article>
      <article class="sc-flow-step">
        <span class="sc-flow-step__index">04</span>
        <h3>Comparison & Feedback</h3>
        <p>把 comparison、trace、result 與 provenance 保存下來，讓下一輪 design 修正有清楚依據。</p>
      </article>
    </div>
  </section>

  <section class="sc-marketing-section">
    <div class="sc-marketing-section__header">
      <p class="sc-marketing-kicker">Physics Backbone</p>
      <h2>Explanation 承接的是完整的理解鏈，而不只是工具操作。</h2>
      <p>
        平台的另一個核心，是讓使用者知道自己正在分析什麼。Explanation 的角色不是替功能頁補充背景，
        而是帶使用者先理解 S/Y/Z 的網路分析，再進到 circuit definition、等效電路、量子化與 Hamiltonian。
        這條路線的存在，就是因為超導量子電路不只需要傳統 network response，還需要理解量子化後的物理表現。
      </p>
    </div>
    <div class="sc-value-grid">
      <article class="sc-value-card">
        <h3>S / Y / Z Matrix</h3>
        <p>理解不同表示法之間怎麼轉換、什麼時候該用哪一種語言讀 simulation 與量測結果，並把 layout、circuit、measurement 放進同一個 comparison frame。</p>
      </article>
      <article class="sc-value-card">
        <h3>Circuit Definition</h3>
        <p>把分析對象固定成可重複使用的電路結構，而不是每次重新翻譯圖、參數與 netlist。</p>
      </article>
      <article class="sc-value-card">
        <h3>Hamiltonian Path</h3>
        <p>在需要時跳脫純 S/Y/Z 表示，接到更高層的電路模型與 Hamiltonian 層級模擬，處理量子化後才會出現的超導電路問題。</p>
      </article>
      <article class="sc-value-card">
        <h3>Quantum-Specific Interpretation</h3>
        <p>平台不是一般 photonics workflow 的翻版；它必須能說明「量子」這件事如何改變模型、分析目標與模擬方法。</p>
      </article>
    </div>
  </section>

  <section class="sc-marketing-section">
    <div class="sc-marketing-section__header">
      <p class="sc-marketing-kicker">Platform Boundary</p>
      <h2>這個平台聚焦 design-to-measurement 的分析整合，不承擔 fabrication integration。</h2>
    </div>
    <div class="sc-audience-grid">
      <article class="sc-audience-card">
        <h3>本平台</h3>
        <p>處理 circuit definition、simulation、measurement、comparison、trace、result 與分析理解，讓研究迭代本身可以被整合與重建。</p>
      </article>
      <article class="sc-audience-card">
        <h3>Lab-Chip-Data-Hub</h3>
        <p>承接 fabrication 側的整合，並接收這個平台產出的研究資料與分析結果，兩者分工不同，但資料可以銜接。</p>
      </article>
      <article class="sc-audience-card">
        <h3>分界的價值</h3>
        <p>把 fabrication 與 design-to-measurement analysis 拆開，才能讓平台邊界清楚、能力定義清楚、開源策略也清楚。</p>
      </article>
    </div>
  </section>

  <section class="sc-marketing-section">
    <div class="sc-marketing-section__header">
      <p class="sc-marketing-kicker">Reading Paths</p>
      <h2>你可以從工作流、物理理解或規格查詢三種角度進入這個平台。</h2>
    </div>
    <div class="sc-path-grid">
      <a class="sc-path-card" href="../">
        <h3>先看整體輪廓</h3>
        <p>從首頁開始，先掌握 design、simulation、measurement 與 docs 的入口分布。</p>
      </a>
      <a class="sc-path-card" href="../tutorials/">
        <h3>從工作流進入</h3>
        <p>從 Tutorials 走一遍 circuit definition、simulation 與結果分析，理解平台怎麼串起研究任務。</p>
      </a>
      <a class="sc-path-card" href="../explanation/">
        <h3>從物理主幹進入</h3>
        <p>從 Explanation 進去，沿著 S/Y/Z、等效模型與 Hamiltonian 這條路理解分析到底在做什麼。</p>
      </a>
      <a class="sc-path-card" href="../reference/">
        <h3>直接查契約</h3>
        <p>從 Reference 進去，查 CLI、資料格式、UI 契約與 guardrails，確認系統如何保持一致。</p>
      </a>
    </div>
  </section>

</section>
