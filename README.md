# rag-lab

Three ways to give a language model knowledge it does not have, compared on the same data:

- **RAG** — retrieve the relevant chunks and put only them into the prompt;
- **CAG** — put the whole corpus into the context and reuse a warmed key-value cache;
- **KAG** — build a knowledge graph and answer from its facts.

The result is one table: method × model → answer quality, latency, tokens.

## Setup of the experiment

- **Domain:** Spanish La Liga, season 2025/26 — Barcelona, Real Madrid, Atlético Madrid. The models below
  were trained before this season, so they cannot answer from memory.
- **Corpus:** English Wikipedia — the league season page and the clubs' season pages. Tables (squads,
  transfers, scores) are parsed from the page markup, because the plain-text export drops them.
  The corpus is downloaded by a script and is not stored in this repository.
- **Models:** `qwen2.5:3b` and `qwen2.5:7b`, local, through Ollama. Embeddings and the reranker are local too.
- **Questions:** two kinds — "find a fact" (RAG, CAG) and "connect facts" (KAG). Answers that can be
  checked exactly (score, scorer, club) are compared with the reference directly, without an LLM judge.
- **Corpus gate:** before the comparison, a model without context must answer under 20 % of the questions
  correctly, and over 70 % when given the right chunk. Otherwise the domain is replaced.

## RAG pipeline

Semantic chunking, hybrid search (BM25 + dense vectors), a local cross-encoder reranker, answers
grounded strictly in the retrieved context with citations to the source page, evaluation and query logs.

Out of scope, because they do not change the comparison: task queues, a metadata database, access
control, answer caching, streaming, a UI, and paid models.

## Status

Started 30.10.2026. Nothing is measured yet.

## Data and license

Code — [MIT](LICENSE). Text of the corpus — [Wikipedia](https://en.wikipedia.org/), licensed under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); any published excerpt keeps that license
and a link to the source page.
