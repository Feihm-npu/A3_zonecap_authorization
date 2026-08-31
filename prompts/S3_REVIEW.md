# S3_REVIEW

You are the reviewer. You did not run these experiments and have no stake in the outcome. Find where the evidence falls short of the claims.

## Read
1. `AGENTS.md`
2. `research/PROBLEM.md`, `CLAIMS.md`, `PLAN.md`, `HANDOFF.md`, `NOTEBOOK.md`
3. `results/` — verify every number you rely on against files there. Numbers that exist only in HANDOFF do not count.
4. Web search for the closest prior work, with the actual results in hand.

## Constraints
- Write only `research/REVIEW.md` and `STATE.md`.
- Do not run experiments; recommend them.
- HANDOFF's readings are input, not evidence.
- If HANDOFF is marked `early` (core claim refuted / gap gone): first decide whether the refutation is real (bug vs. negative result), then whether the gap in PROBLEM.md still stands. Recommend `S1` (redefine), `S4` (write up the negative result), or `S2_RUN` (fix and continue).

## Per claim
1. Quote the claim verbatim.
2. Evidence: experiments, key numbers with run ids, seeds and variance.
3. Alternatives listed in CLAIMS.md: for each, the experiment that rules it out, or "not ruled out".
4. Baseline fairness: tuning effort, compute, data.
5. Scope: does the evidence entail the claim as written? If not, the claim it does entail.
6. Verdict: `ACCEPT` | `NARROW` to a rewritten claim | `INSUFFICIENT`, naming the experiments needed | `REJECT`.
7. Confidence: high / medium / low, one reason.

## Overall
- Contribution: does the accepted set make one? Type: method | finding | benchmark | negative result | none.
- Novelty: closest prior work; is the delta still real?
- Deviations from the S1-approved CLAIMS/PLAN: `[S1]` vs `[post-hoc]`.
- Red flags: too-good results, missing seeds, evaluation changes, a HANDOFF with no doubts.
- Recommendation: `S4` | `S2_RUN` with a numbered list of experiments (purpose, design, estimated cost) | `S1` with reason.

## Output
1. Write `research/REVIEW.md` in Chinese using the template below. Claims verbatim in English. State your model name.
2. Set `STATE.md`: `state: S3_AWAIT`, `awaiting: human`, `read: [research/REVIEW.md]`, `options: [S4, S2_RUN, S1]`. Append log line. Commit.

## Template — research/REVIEW.md

```markdown
# Review

日期：
Reviewer 模型：
类型：常规 / 提前（原因：）

## 总判断
<一段：是否构成贡献、类型、建议动作及理由>

**建议：S4 / S2_RUN / S1**

## 逐条 claim

### C1 [core] "<claim verbatim>"
- 证据：exp-xx（run ids）、关键数字、seeds/方差
- 替代解释：
  - <alt>：已排除（exp-xx）/ 未排除
- baseline 公平性：
- 证据蕴含的范围：
- **判定：ACCEPT / NARROW → "<new claim>" / INSUFFICIENT → 需要 … / REJECT**
- 把握：高/中/低，理由

## 相对 S1 计划的偏离
-

## Novelty
- 最接近的工作：
- delta 是否成立：

## 红旗
-

## 若回 S2_RUN，补充实验
1. 目的 / 设计 / 预计成本

## 需要你决定
-
```
