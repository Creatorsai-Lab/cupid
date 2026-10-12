# Evals

Evals measure the **quality** of agent output using **real LLMs**. They are
deliberately separate from `tests/`:

|                | `tests/`                          | `evals/`                                  |
| -------------- | --------------------------------- | ----------------------------------------- |
| Checks         | our code is correct               | the agents' output is good                |
| LLM            | fakes (`FakeLLM`), never real     | real providers, never fakes               |
| Result         | pass / fail, same every run       | scores against a threshold, varies by run |
| Cost           | free, seconds                     | API calls, minutes                        |
| When           | every change, CI                  | before any prompt or model change         |

`uv run pytest` never collects this folder (`testpaths = ["tests"]` in
`pyproject.toml`). Run evals explicitly from `backend/`:

```powershell
uv run pytest evals                 # all evals
uv run pytest evals/studio          # one agent
```

## Layout

```
evals/
  conftest.py        real providers, result recording   (added with the first eval)
  datasets/          golden inputs, one *.jsonl per eval (versioned in git)
  results/           scored outputs per run             (gitignored)
  research/          research agent evals
  studio/            studio evals (director, specialists)
```

## Rules

1. **Datasets are versioned.** Changing a dataset is a reviewed change, like code.
2. **Score, don't match.** Use rubric or programmatic scores with thresholds,
   never exact-text comparison.
3. **Record every run** in `results/` (inputs, outputs, scores, model, prompt
   version) so runs can be compared.
4. **Start small.** About 20 real prompts per agent catches most regressions;
   grow the dataset from real failures.
