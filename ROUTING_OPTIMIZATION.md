# Hybrid Routing 优化方案（按优先级排序）

## 目标与计分回顾

- **总分** = 难度加权（easy 20% / medium 30% / hard 50%）× 各难度 level_score，level_score = **0.60×F1 + 0.15×time_score + 0.25×on_device_ratio**。
- **time_score** = max(0, 1 - avg_time_ms / 500)；on_device 比例越高、F1 越高、时延越低越好。
- **约束**：不能修改 `generate_hybrid(messages, tools, default_threshold)` 的入参与返回值；仅能改其内部逻辑及 `generate_cactus` 的 prompt/参数。

---

## 基线 vs 当前：不要动 prompt

- **基线**：原始 Cactus prompt（两句话 + Example），**不要改**。任何加长/改写 prompt 的尝试（包括「tool router」等）都导致 F1 或总分变差。
- **当前推荐**：保持 `main.py` 里 Cactus 为：
  ```text
  "System: You are an OS assistant. Use the provided tools by outputting JSON. "
  "Example: {\"function_calls\": [{\"name\": \"set_dnd\", \"arguments\": {\"status\": true}}]}"
  ```
- **结论**：优化只做 **routing（阈值、Strategy 1/2）**，不做 prompt 实验。

---

## 根据 benchmark 结果：明确要优化什么

参考一次典型 run（easy F1=0.80, medium F1=0.80, hard F1=0.55, on-device 47%, TOTAL 51.8%）：

| 现象 | 案例（F1=0 或偏低） | 优化方向 |
|------|---------------------|----------|
| **本地对 timer/reminder 经常错** | timer_5min, reminder_meeting, reminder_among_four, timer_among_three, timer_and_music, timer_music_reminder | 不调 prompt。可考虑：这些 case 若走本地且 confidence 不高，更倾向 fallback 到 cloud（例如对含 set_timer/create_reminder 的 tools 略提高阈值或单独分支）。 |
| **hard 多 call 掉 F1** | message_and_weather, alarm_and_weather, search_and_message, alarm_and_reminder, weather_and_music, message_weather_alarm, search_message_weather 等 F1=0.50~0.67 | 多步 call 本地易漏/错。优先用 **routing**：多 tool 或长句时阈值/Strategy 2 微调，让易错子集多走 cloud，其余尽量 on-device。 |
| **on-device 47%** | 一半走 cloud，时延和 on_device_ratio 有空间 | 在 **不伤 F1** 前提下微调：收窄 Strategy 2（少一点「直接上云」）、略降 3+ tools 的 threshold，让更多「本地能对」的 case 留本地。 |
| **时间** | avg time ~1150ms，fallback 时含 local+cloud | 若赛制允许，fallback 时 total_time 只计 cloud；否则只靠「少 fallback」降时延。 |

**优先做且可验证的**：  
1) 收窄 Strategy 2（例如 >40 词、或复合且 len(tools)>2 才 bypass）；  
2) 仅将 3+ tools 的 dynamic_threshold 从 0.85 调到 0.78；  
3) 不改 prompt，每次只改一项并跑 `python benchmark.py` 对比 F1 / on-device / TOTAL SCORE。

---

## 已尝试且回退的改动（避免再犯）

| 改动 | 结果 | 教训 |
|------|------|------|
| 加长 Cactus system prompt（规则 + tool 名单 + 多句说明） | easy F1 0.80→0.60，hard F1 0.62→0.58，整体 F1 下降 | 小模型对长 prompt 敏感，易跑偏或格式错 |
| 大幅降低阈值（1→0.40, 2→0.55, 3→0.65, 4+→0.72）+「有效 call 即留本地」 | on-device 47%→40%，总时延上升，总分变差 | 过度信任本地输出，误留错误 call；fallback 逻辑变化导致更多走 cloud |

---

## 优化方案（按优先级）

### P0：低风险、建议优先做

1. **微调 Strategy 2 触发条件（收窄 syntactic bypass）**
   - **做法**：仅在「句长 > 40 词」或「出现复合词且 len(tools) > 2」时直接上云；当前为 >35 词或 (复合且 len(tools)>1)。
   - **目的**：减少中等长度、2–3 个 tool 的 case 被误判为「复杂」而直接走 cloud，提高 on-device 且可能略降时延。
   - **验证**：跑 `python benchmark.py`，看 medium/hard 的 on-device 与 F1 是否提升或至少不降。

2. **仅下调 3+ tools 的阈值（保守）**
   - **做法**：`len(tools) >= 3` 时把 `dynamic_threshold` 从 0.85 改为 **0.78**；1 tool 仍 0.50，2 tools 仍 0.75。
   - **目的**：在不大幅放宽信任的前提下，略增 on-device 比例。
   - **验证**：跑 benchmark，重点看 medium/hard 的 on-device 与 F1。

---

### P1：中风险、需跑 benchmark 验证

3. **Cactus prompt 极简增强（只加一句）**
   - **做法**：在现有短 prompt 后只加一句，例如："Output JSON with \"function_calls\" array; each call must use one of the provided tool names only."
   - **目的**：减少 tool name 写错（提升 F1），又不拉长 prompt。
   - **风险**：仍可能影响小模型行为，需对比前后 F1（尤其 easy）。

4. **「有效 call」留本地（保守版）**
   - **做法**：定义「有效」= `function_calls` 非空且每个 `name` 在 `tools` 中。仅当 **confidence >= dynamic_threshold - 0.08** 且有效时，才用「有效」放宽留本地（即 confidence 略低于阈值但有效则仍留本地）；否则沿用原逻辑（仅 confidence >= threshold 且有 calls 才留本地）。
   - **目的**：避免仅因置信度略低就把正确 call 交给 cloud，提高 on-device 且不显著牺牲 F1。
   - **风险**：放宽 0.08 若过大可能留下错误 call，建议用 0.05–0.08 做 A/B。

5. **Strategy 1 收窄（减少误判「深度认知」）**
   - **做法**：仅在同时满足「含 cognition 关键词」且「句长 > 15 词」或「len(tools) > 3」时走 cognition escaping；避免极短句（如 "explain"）直接上云。
   - **目的**：benchmark 多为短指令，减少因偶发词触发的上云，提高 on-device。
   - **验证**：看 easy 是否更多走本地且 F1 不降。

---

### P2：需实验或影响面较大

6. **Fallback 时不计入 local 时延**
   - **做法**：fallback 到 cloud 时，返回的 `total_time_ms` 只计 cloud 耗时，不加 `local.get("total_time_ms")`（或仅在做分析时记录 local 耗时）。
   - **目的**：总分里的 time 只反映「用户实际等到的」耗时，避免「本地+云」双倍惩罚；若赛制明确要求含 local 则跳过。
   - **注意**：需确认 benchmark / submit 是否期望 total_time_ms 包含 local。

7. **Cactus 输出解析增强**
   - **做法**：从 `raw_str` 中提取 JSON 时，若首轮 regex 得到多段 `{...}`，尝试按顺序解析并取第一个含合法 `function_calls` 的对象；或对常见格式错误做 1–2 条简单修复再 parse。
   - **目的**：减少因格式小问题导致「无 call → fallback」，提升 on-device 与 F1。
   - **风险**：可能掩盖模型真实表现，需对比解析成功率与 F1。

8. **按词数/工具数选择「先本地」或「直接云」**
   - **做法**：例如当「len(tools) >= 5 且 word_count > 25」时直接上云，其余一律先走 Cactus。用数据验证 5/25 的 cutoff 是否优于当前 Strategy 2。
   - **目的**：在真正复杂的子集上省一次本地调用，降低总时延。
   - **风险**：cutoff 设不好会伤 F1 或 on-device，需多次跑 benchmark 调参。

---

### P3：仅当 P0–P2 做完仍有空间时考虑

9. **Cactus 的 max_tokens / stop_sequences 微调**
   - **做法**：在保证能输出完整 JSON 的前提下，略增 max_tokens（如 64→80）或微调 stop，观察 F1 与延迟。
   - **风险**：可能增加幻觉或时延，需逐项测。

10. **Gemini system instruction 与 benchmark 对齐**
    - **做法**：将 Gemini 的 system 改为更贴近「工具调用助手」、少提 DND/meetings 等，观察 cloud 分支的 F1。
    - **目的**：提升 fallback 路径正确率；主要影响走 cloud 的 case。

---

## 建议执行顺序

1. 先做 **P0-1** 和 **P0-2**，各跑一次完整 benchmark，记录 F1 / on-device / avg time / TOTAL SCORE。
2. 若 P0 稳定有收益，再试 **P1-3**（prompt 一句）、**P1-4**（有效 call 保守放宽）、**P1-5**（Strategy 1 收窄），每次只改一项并对比。
3. P2/P3 作为后续迭代选项，在本地与 submit 上做 A/B 验证后再决定是否保留。

---

## 如何验证

- 每次改动后：`python benchmark.py`，记录 Summary 与 TOTAL SCORE。
- 若某次改动导致 F1 或 on-device 明显下降（如 F1 降 >0.03 或 on-device 降 >5%），优先回退该改动再试下一项。
