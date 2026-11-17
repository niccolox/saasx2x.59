Files in this folder:

| File | Made by | Committed |
| --- | --- | --- |
| `dashboard.schema.json` | `uv run saasx2x schema > web/src/generated/dashboard.schema.json` | Yes. `tests/test_web.py` fails when it differs from the Pydantic model. |
| `dashboard.ts` | `npm run gen` (runs before `dev`, `build`, `test`, `typecheck`) | No. It is in `.gitignore`, so it cannot drift from the JSON. |

Do not edit either file by hand.
