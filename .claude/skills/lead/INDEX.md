# lead skill 文件索引

本文件是 lead skill 的目录索引，列出所有**已落地**和**已预留槽位**的文件。`install-wow-harness.md` 是 phase B→C transition gate 的占位槽，由 WP-11 在 phase C 填充；在此之前，该槽位必须存在于索引但文件本身不存在。

## 文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| SKILL.md | active | 流程统领主文件（9 个 Gate fail-closed 状态机） |
| INDEX.md | active | 本索引文件 |
| ref-review-sop.md | active | 审查闭环 SOP（TeamCreate 用法、维度矩阵） |
| ref-stages.md | active | 五阶段深度定义（消费方发现门禁清单） |
| install-wow-harness | (TODO WP-11) | install/setup — phase C slot，尚未落地 |

## Phase B→C Transition Gate

`install-wow-harness` 槽位的存在本身就是 phase B → phase C 的转换门：

1. Phase B 的 WP-06（本 skill 的落地者）**必须**把 `install-wow-harness` 这一行保留在 INDEX.md 中。
2. Phase B 的 WP-06 **不得**写入 `lead/install-wow-harness.md` 文件（slot 必须为空，等 WP-11 填充）。
3. Phase C 的 WP-11 **仅允许**往这个 slot 落实 `install-wow-harness.md` 文件内容，不得在 `lead/` 下新增其他同级 `.md`。
4. WP-SEC-1 的 CI 会 `grep -q 'install-wow-harness' INDEX.md` 断言本行存在；缺失 → block merge。

这不是命名洁癖。跨 phase 的 slot reservation 是整个 plan 的唯一强制转换边界——phase B 不满足这一条，phase C 无法开始。

## 不是 final state

本索引不是 final lock。将来允许 crystal-learn 注入的新 invariant 或新的 ref 文件扩充本表；但 `install-wow-harness` 这一行在 WP-11 填充之前**只能以 `(TODO WP-11)` 状态存在，不得删除、不得改名**。
