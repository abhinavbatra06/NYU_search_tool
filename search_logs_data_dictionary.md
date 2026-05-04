# `search_logs` Data Dictionary

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | `uuid` | No | `gen_random_uuid()` | Unique identifier for each log row, auto-generated |
| `question` | `text` | No | — | The exact search query typed by the user |
| `answer` | `text` | No | — | The full LLM-generated answer returned to the user |
| `final_faculty` | `jsonb` | No | — | Array of faculty objects recommended in the response. Each object contains `name`, `faculty_id`, `chunk_type`, `source`, `url`, `paper_title`, `year`, `relevance_score` |
| `retrieved_chunks` | `jsonb` | No | — | Array of search result objects passed to the LLM. Each object contains `content` (the chunk text), `score`, and a nested `faculty` object with the same fields as above |
| `use_hybrid` | `boolean` | Yes | — | Whether the request used hybrid search (semantic + keyword) or pure semantic search |
| `success` | `boolean` | No | `true` | Whether the search completed successfully. `false` rows have empty `answer`, `final_faculty`, and `retrieved_chunks` |
| `error_message` | `text` | Yes | — | The Python exception message. Populated only when `success = false` |
| `error_type` | `text` | Yes | — | The Python exception class name, e.g. `ValueError`, `OpenAIError`. Populated only when `success = false` |
| `timestamp` | `timestamptz` | No | `now()` | UTC timestamp of when the search request completed |

## Notes

- One row is inserted per search request, regardless of whether results were found
- A search that returns zero results is still a `success = true` row — the answer in that case will be the "no results found" message
- `final_faculty` and `retrieved_chunks` are `[]` on failure rows
- The `service_role` key is required for inserts since RLS is enabled with no public insert policy
