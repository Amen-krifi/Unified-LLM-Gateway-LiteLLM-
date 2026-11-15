# Router rule: simple vs complex

## Rule (v2)
A question is **complex** if:
- it has more than 25 words, OR
- it contains one of these whole words/phrases: compare, analyze, analyse,
  explain, why, write code, write a, recommend, design, step by step,
  evaluate, assess, propose, describe, plan, outline, create, should,
  how would, strategy, risks, trade-off

Otherwise it is **simple**.

## Results on the 100-question benchmark
| Version | Accuracy |
|---|---|
| v1 (first keywords) | 79% |
| v2 (more keywords + whole-word matching) | 95% |
| v3 (35-word limit, if you tested it) | __% |

## Bug found and fixed
The keyword "plan" matched inside "planet". Fixed with whole-word matching.

## Remaining errors
- Q34, 54, 74, 94: simple questions wrapped in long chit-chat, wrongly marked complex.
- Q58: complex question with no keyword, wrongly marked simple.

## Limits
A keyword + length rule cannot understand meaning. It is fast and free,
but fooled by wording. A future improvement would be a small classifier
model, at the cost of extra latency.