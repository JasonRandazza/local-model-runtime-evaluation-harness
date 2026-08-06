# Approach 3 Evidence Closure Review — 2026-08-05

**Decision:** `REVIEWED_UNSEALED` — historical collection completed, but the
evidence is not eligible for retroactive managed sealing.

## Scope

This review covers the Gemma recipe `gemma-freeform-native-triple-v1` executed
through the retained low-level `lmre-approach3` surface on 2026-07-24:

| Collector | Local evidence directory |
| --- | --- |
| preference | `results/preference/gemma-4-12b-qat-preference-20260724-221046` |
| RAG oracle | `results/rag/gemma-4-12b-qat-rag-20260724-221912` |
| RAG keyword | `results/rag/gemma-4-12b-qat-rag-20260724-222023` |
| overhead | `results/overhead/overhead-20260724-222140` |

The exact association between the recipe and these four directories is
preserved in the read-only sibling-archive session handoff. The local result
directories were inspected without modification.

## Collector Findings

- Preference collection finished without an early stop. Each of the three
  cells has six successful answers and no recorded request error (18/18
  successful collection records). The directory has no review, judgment,
  tally, or product-level summary, so this review does not infer a preference
  winner.
- Oracle RAG and keyword RAG each finished without an early stop. Each mode
  has six successful answers for every cell and no recorded request error
  (18/18 successful collection records per mode). No new score or ranking was
  derived during this review.
- Overhead finished without an early stop. Direct oMLX recorded 9/9 successful,
  contract-valid measured observations, while its Osaurus-routed leg remained
  honestly `N/A` because the exact routed model ID was absent. Direct and
  routed OptiQ both recorded 9/9 successful, contract-valid observations.
  The historical OptiQ medians were about `2.006s` direct and `2.017s` routed
  (`+0.011s`), with median TTFT about `0.317s` direct and `0.334s` routed
  (`+0.017s`).

## Why It Cannot Be Retroactively Sealed

These collector directories predate the managed evidence contract. They do
not contain:

- an immutable plan or plan hash;
- adopted-policy linkage or bounded run identity;
- hashes for the recipe, cells, suites, pairs, or machine profile;
- an exact runtime lifecycle journal or cleanup proof;
- an execution-time checksum manifest covering the evidence set.

Creating a checksum file now would prove only the bytes observed during this
review, not their execution-time integrity. Copying the directories into a
managed bundle or invoking the current sealer would invent provenance that did
not exist during execution. The historical directories therefore remain
`REVIEWED_UNSEALED`; they are not promoted to `PASS` and are not accepted by
the sealed-results browser.

## Review-Time Fingerprints

These SHA-256 values identify the non-log files inspected during this review.
They are review-time fingerprints only, not an execution-time seal.

| Relative file | SHA-256 |
| --- | --- |
| `preference/...-221046/answers/jang_4m__osaurus.json` | `a7981707005c1a2d8c344f1d2a617bdd7dfb161603c23c49bf40e719c8e3340a` |
| `preference/...-221046/answers/optiq_4bit__optiq.json` | `89737ba3e93132fef0eca81822fb0eff4f86f38522dba5f7fc0b1ac36db69e31` |
| `preference/...-221046/answers/oq4_fp16__omlx.json` | `e9cbfe420072e644cc72ab346bbde2e3f796e6b62d28fdba52443ea6cb2062b0` |
| `preference/...-221046/raw.json` | `412caf68cdb904918c615e7af840476bd5ed877d5380b4047c8b2cc47469973b` |
| `rag/...-221912/answers/jang_4m__osaurus.json` | `80d381180ee9b2aa09837ecc6f394538212c12eddcb13448ad4cedc5430b5bd9` |
| `rag/...-221912/answers/optiq_4bit__optiq.json` | `a15d92b3d1f2d4c9bf898333e73da98283b577c89235eeaf3548fa1ce373cea2` |
| `rag/...-221912/answers/oq4_fp16__omlx.json` | `5e154567b433d8f0b4af1f174e9012c73f70923a5f7d11e4e789d3ca75fad24e` |
| `rag/...-221912/raw.json` | `5272092e08c23e6ad249c4f4fe9fb8e8ed4da80f2c1abfe6d76a9a98c879cab2` |
| `rag/...-222023/answers/jang_4m__osaurus.json` | `528254ce282dcc19c3a5dfa28b38f9e2a2d88fb112a83b1e679a9426576a42c1` |
| `rag/...-222023/answers/optiq_4bit__optiq.json` | `84e55bbba7c06df4bb9f74c8536d540c92bd93d895f2e011cd0733aef5888629` |
| `rag/...-222023/answers/oq4_fp16__omlx.json` | `baf1d8ae839c634e82018d01d11e2dff5d7843fd3884cefde25747f29dfb9863` |
| `rag/...-222023/raw.json` | `824d3ff5ddb2107838d13049a685c8247612507a0b3cb77a5203dd0f7894e3c3` |
| `overhead/...-222140/raw.json` | `4ba9c9de378307e4b620b0b373ca8902955d7af3ffca12de9a87fc7af39752e3` |
| `overhead/...-222140/report.md` | `7a1eadf254a4fbf3992c64a2f4f62efb79aed6b11c2ad5a1b8432843794c2993` |

## Managed Successors

Current product proof comes from immutable managed evidence instead:

- `run-20260731-051843-04302b` seals the exact three-cell native plan as
  `PASS` for preflight, matrix, preference, both RAG modes, oMLX overhead,
  cleanup, and evidence integrity. Its OptiQ overhead result remained `N/A`.
- `run-20260806-004836-920a93` seals the managed free-binding oMLX lane and
  direct-versus-Osaurus overhead as terminal `PASS`.
- `run-20260806-012734-936521` seals the managed free-binding OptiQ lane and
  direct-versus-Osaurus overhead as terminal `PASS`.

All three bundles passed `lmre report` verification during this review. The
two current free-binding runs preserve exact lifecycle ownership and checksum
manifests; together they close the previously missing oMLX and OptiQ overhead
acceptance paths without rewriting historical output.

## Closure

The Approach 3 evidence-review debt is closed with a negative seal decision:
the old collector output remains useful historical evidence, but it will stay
unsealed. Future evidence that needs a product seal must use `lmre plan
--binding`, followed by the managed run/resume path. No new live execution is
required for this closure.
