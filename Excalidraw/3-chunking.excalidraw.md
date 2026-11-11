---
excalidraw-plugin: parsed
tags: [excalidraw]
---

# Chunking decisions: code-verified source and exact output

The diagram traces `rag/index/chunker.py` at `max_chunk_size = 2000`. A-G are existing source blocks, not arbitrary cuts. The complete source and passages below are generated and checked with `chunk_markdown`. Repeated prose and example log lines are synthetic, not an operational runbook.

## Actual decision order

1. Headings create independent sections containing only their own body, ending at the next heading, including a child. Empty sections and configured excluded subtrees produce no passage.
2. A trimmed section of at most 2,000 characters is emitted unchanged. No block splitting or packing happens, and it never merges with another section.
3. An oversized section is parsed into Markdown blocks. Fitting paragraphs, lists, fences and tables stay intact; only an oversized block is split further. Pieces are packed in reading order when `len(previous) + 2 + len(next) <= 2000`, with exactly `\n\n` between them.
4. Heading-only packed pieces are discarded. All surviving passages retain their section path; there is no cross-heading merge or overlap.

## Steps: packing whole paragraphs

A is the existing 71-character paragraph, not a cut selected by the chunker. Its internal line break does not end the paragraph; the next blank line does. B and C are also existing paragraphs, of 1337 and 1214 characters. None is oversized.

The whole section is **2636** characters: heading (8), A (71), B (1337), C (1214), and six separator characters. The packer combines heading+A+B into **1420**, then moves C whole into **1214** because `1420 + 2 + 1214 = 2636 > 2000`. It leaves 580 characters unused rather than cutting a fitting paragraph to fill the gap.

| Previous | Next piece | Candidate | Decision |
| --- | --- | --- | --- |
| - | heading 8 | - | Start |
| 8 | A 71 | 81 | Append |
| 81 | B 1337 | 1420 | Append |
| 1420 | C 1214 | 2636 | New passage |

The cut is the blank line before C, not character 2,000. Zero-based half-open source ranges are `[0, 1420)` for passage 1, `[1420, 1422)` for the consumed separator, and `[1422, 2636)` for passage 2.

## Validation and Verify: no cross-heading merge

Validation states the expected account in a 46-character passage. Verify makes its own 111-character passage. Both fit unchanged, but remain separate even though combining them would use only 159 characters. An empty parent would produce no passage, while remaining in its child's path. A short fact can help identify a useful note; generic descriptions may add noise. Embeddings include the section path and shared introductory context, not just the body.

## Troubleshooting: split first, then pack

The section has **2669** characters: heading (18), F (2615), G (32), and four separator characters. F is one oversized fenced block with 42 body lines, each 61 characters.

Each piece reserves 12 characters for the opening ` ```text `, closing marker and their newlines. Its body budget is **2000 - 12 = 1988**.

- Lines 01-32: `32 * 61 + 31 = 1983` body characters; with wrappers, **1995**.
- Adding line 33 needs `1983 + 1 + 61 = 2045 > 1988`. Cut at the newline **before example 33**.
- Lines 33-42: `10 * 61 + 9 = 619` body characters; with wrappers, **631**.

Original body ranges `[0, 1983)` and `[1984, 2603)` become F1 and F2. The newline at offset 1983 is consumed. Both pieces receive their own opening and closing fences.

**Intermediate pieces are not final passages:** the packer receives `[heading:18, F1:1995, F2:631, G:32]`.

| Previous | Next piece | Candidate | Decision |
| --- | --- | --- | --- |
| - | heading 18 | - | Start |
| 18 | F1 1995 | 2015 | New packed piece |
| 1995 | F2 631 | 2628 | New packed piece |
| 631 | G 32 | 665 | Append |

Raw packed lengths are `[18, 1995, 665]`. The heading-only piece is discarded, leaving passage 5 (**F1, 1995**) and passage 6 (**F2 + two newlines + G, 665**). The heading path is retained in metadata. G follows the closing fence and does not become a separate passage.

## Why this strategy

The limit is a ceiling, not a fill target. The chunker preserves existing paragraphs and Markdown structure instead of slicing every 2,000 characters. PR #12 removed tiny-neighbor merging so passages keep their own heading ownership. This is a structural/readability tradeoff, not proof of universally better retrieval.

The recommended 2,000-character cap is configurable. Search separately returns at most 10 hits with `score >= max(0.25, best_score - 0.20)`; these retrieval settings do not affect which passages are generated.

## Source: `notes/aws-keys.md`

````markdown
---
type: runbook
---

# Rotate AWS access keys

Replace IAM credentials in a fictional workload without
interrupting traffic.

Tags: #AWS #runbook #aws

## Steps

Obtain the workload owner's approval and record the maintenance
window.

Create a second access key while the current key remains active. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement.

Deploy the replacement credential to each workload that uses this IAM user. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement.

## Validation

Expected account: 123456789012.

### Verify

Run `aws sts get-caller-identity` with the replacement key.
Check the AWS account and IAM user ARN.

## Troubleshooting

```text
example 01: caller=expected policy=denied credential=current!
example 02: caller=expected policy=denied credential=current!
example 03: caller=expected policy=denied credential=current!
example 04: caller=expected policy=denied credential=current!
example 05: caller=expected policy=denied credential=current!
example 06: caller=expected policy=denied credential=current!
example 07: caller=expected policy=denied credential=current!
example 08: caller=expected policy=denied credential=current!
example 09: caller=expected policy=denied credential=current!
example 10: caller=expected policy=denied credential=current!
example 11: caller=expected policy=denied credential=current!
example 12: caller=expected policy=denied credential=current!
example 13: caller=expected policy=denied credential=current!
example 14: caller=expected policy=denied credential=current!
example 15: caller=expected policy=denied credential=current!
example 16: caller=expected policy=denied credential=current!
example 17: caller=expected policy=denied credential=current!
example 18: caller=expected policy=denied credential=current!
example 19: caller=expected policy=denied credential=current!
example 20: caller=expected policy=denied credential=current!
example 21: caller=expected policy=denied credential=current!
example 22: caller=expected policy=denied credential=current!
example 23: caller=expected policy=denied credential=current!
example 24: caller=expected policy=denied credential=current!
example 25: caller=expected policy=denied credential=current!
example 26: caller=expected policy=denied credential=current!
example 27: caller=expected policy=denied credential=current!
example 28: caller=expected policy=denied credential=current!
example 29: caller=expected policy=denied credential=current!
example 30: caller=expected policy=denied credential=current!
example 31: caller=expected policy=denied credential=current!
example 32: caller=expected policy=denied credential=current!
example 33: caller=expected policy=denied credential=current!
example 34: caller=expected policy=denied credential=current!
example 35: caller=expected policy=denied credential=current!
example 36: caller=expected policy=denied credential=current!
example 37: caller=expected policy=denied credential=current!
example 38: caller=expected policy=denied credential=current!
example 39: caller=expected policy=denied credential=current!
example 40: caller=expected policy=denied credential=current!
example 41: caller=expected policy=denied credential=current!
example 42: caller=expected policy=denied credential=current!
```

Retry with the corrected policy.

## Notes

## References

Example reference text: not indexed.

### Provider docs

This child is excluded too.
````

Shared context: "Replace IAM credentials in a fictional workload without\ninterrupting traffic.".

Shared tags: `["aws", "runbook"]`

### Passage 0: `Rotate AWS access keys` (103 characters)

````markdown
# Rotate AWS access keys

Replace IAM credentials in a fictional workload without
interrupting traffic.
````

### Passage 1: `Rotate AWS access keys > Steps` (1420 characters)

````markdown
## Steps

Obtain the workload owner's approval and record the maintenance
window.

Create a second access key while the current key remains active. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement.
````

### Passage 2: `Rotate AWS access keys > Steps` (1214 characters)

````markdown
Deploy the replacement credential to each workload that uses this IAM user. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement. Keep the old key active until every workload uses the replacement.
````

### Passage 3: `Rotate AWS access keys > Validation` (46 characters)

````markdown
## Validation

Expected account: 123456789012.
````

### Passage 4: `Rotate AWS access keys > Validation > Verify` (111 characters)

````markdown
### Verify

Run `aws sts get-caller-identity` with the replacement key.
Check the AWS account and IAM user ARN.
````

### Passage 5: `Rotate AWS access keys > Troubleshooting` (1995 characters)

````markdown
```text
example 01: caller=expected policy=denied credential=current!
example 02: caller=expected policy=denied credential=current!
example 03: caller=expected policy=denied credential=current!
example 04: caller=expected policy=denied credential=current!
example 05: caller=expected policy=denied credential=current!
example 06: caller=expected policy=denied credential=current!
example 07: caller=expected policy=denied credential=current!
example 08: caller=expected policy=denied credential=current!
example 09: caller=expected policy=denied credential=current!
example 10: caller=expected policy=denied credential=current!
example 11: caller=expected policy=denied credential=current!
example 12: caller=expected policy=denied credential=current!
example 13: caller=expected policy=denied credential=current!
example 14: caller=expected policy=denied credential=current!
example 15: caller=expected policy=denied credential=current!
example 16: caller=expected policy=denied credential=current!
example 17: caller=expected policy=denied credential=current!
example 18: caller=expected policy=denied credential=current!
example 19: caller=expected policy=denied credential=current!
example 20: caller=expected policy=denied credential=current!
example 21: caller=expected policy=denied credential=current!
example 22: caller=expected policy=denied credential=current!
example 23: caller=expected policy=denied credential=current!
example 24: caller=expected policy=denied credential=current!
example 25: caller=expected policy=denied credential=current!
example 26: caller=expected policy=denied credential=current!
example 27: caller=expected policy=denied credential=current!
example 28: caller=expected policy=denied credential=current!
example 29: caller=expected policy=denied credential=current!
example 30: caller=expected policy=denied credential=current!
example 31: caller=expected policy=denied credential=current!
example 32: caller=expected policy=denied credential=current!
```
````

### Passage 6: `Rotate AWS access keys > Troubleshooting` (665 characters)

````markdown
```text
example 33: caller=expected policy=denied credential=current!
example 34: caller=expected policy=denied credential=current!
example 35: caller=expected policy=denied credential=current!
example 36: caller=expected policy=denied credential=current!
example 37: caller=expected policy=denied credential=current!
example 38: caller=expected policy=denied credential=current!
example 39: caller=expected policy=denied credential=current!
example 40: caller=expected policy=denied credential=current!
example 41: caller=expected policy=denied credential=current!
example 42: caller=expected policy=denied credential=current!
```

Retry with the corrected policy.
````

## Other formats use the same decisions

Oversized ordinary text recursively prefers blank lines, line breaks, spaces, then hard character cuts. It does not necessarily cut at the last newline before character 2,000. Lists split at top-level items; oversized items use ordinary text splitting. Tables repeat their first two header lines and split rows at lines/spaces/characters. Fences repeat wrappers and split the body with ordinary text preferences. If wrappers leave no body room, ordinary text splitting is used.

Recognized top-level ATX/setext headings create sections; headings inside code, lists or quotes do not. Frontmatter and introductory Tags: are removed; exclusions match case-insensitively. Heading paths, optional introductory context and tags are separate from the passage-text budget.

%%
# Excalidraw Data

## Text Elements
How a note becomes passages ^DA1hwhfT

Passages locate notes. Read the full note for context. ^zbYAUQCb

Limit: 2,000 characters ^4aAGHOZM

ONE SOURCE NOTE ^By3Lzl0O

GENERATED PASSAGES ^9EUxZ3cA

# Rotate AWS access keys ^KW2mkMC4

description ^cR3tNZ3D

frontmatter + Tags: ^eifIzSA9

Section fits: keep it whole ^19keYbLu

Intro ^pcwilCel

103 chars ^eK5J6r0K

# Rotate AWS access keys ^wlOFoZee

description ^wFG9fg9s

## Steps ^oXWaS8Sv

Whole section: 2,636 chars ^OR5V6V99

A = source paragraph (71 chars) ^0zO0j80J

B = source paragraph (1,337 chars) ^vi2VbUlP

C = source paragraph (1,214 chars) ^dYXgRF9S

Paragraphs fit: merge them ^mlEBfaHn

Heading + A + B = 1,420 chars ^L21fHltw

A + B ^kJBVaZyO

1,420 chars ^vVjoT559

## Steps ^req9LNNB

A  approval ^bNrflYUJ

B  create ^P4MpH9Sg

Next paragraph won't fit: new passage ^qzZM5Iaf

Adding C would reach 2,636 chars (> 2,000).
Keep C whole; leave 580 chars unused. ^V8i5Y14G

C ^ab6yS2fZ

1,214 chars ^jVzUlB9S

C  deploy ^wjXNyeCJ

## Validation ^rTUhA8Ah

D  Account: 123456789012 ^bIgkOl0k

### Verify ^W1683oO3

E  verify identity ^mLaffUCQ

Different headings: keep separate ^m0ugFsrd

A useful short fact stays separate from its check. ^FVSMU8wD

Validation ^IfzBvba4

Validation > Verify ^t5uKAxLW

D ^TnehDx4B

46 chars ^bkRIrzjA

## Validation ^0Ea5U4nf

D  Account: 123456789012 ^Khti2x1Z

E ^BW9o8b7U

111 chars ^geIWkt6J

### Verify ^1u3LRU6p

E  verify identity ^XpYPRWr4

## Notes ^rijGVy9U

## References ^MhA3QyxR

### Provider docs ^6mskSM2o

Empty section: no passage ^z9ystLSl

Excluded headings: no passage ^0azeT0mm

Letters identify source blocks. Matching colors and arrows show where each passage comes from. ^wklyNZor

Only oversized sections: separate blocks, split large blocks, then merge to fit. Never across headings. ^JKzjlGWk

Schematic previews; exact source, passage text, paths and metadata are in Markdown view. ^5i63PDEq

Each heading starts a section. Check that section's size. ^sdOb3evx

Fits: keep the whole section ^aM6MUIBy

Too large: paragraphs / other blocks -> split if needed -> merge to fit ^tJzUi3o4

## Troubleshooting ^TGobs7Te

Section: 2,669 chars ^v9RMv75S

F  one code block | 2,615 chars ^fgHVjhpn

```text ^f54QCXRL

example 01 ... example 32 ^KGU6L93K

CUT before example 33 ^vvTrj4cU

example 33 ... example 42 ^guHUBmqL

``` ^OhxNZ9eM

G  retry paragraph | 32 chars ^bbQYM2Gx

Block too large: split it ^eupeSbzf

Body budget: 2,000 - 12 fence characters = 1,988. ^XJVfroNf

32 lines use 1,983 chars; line 33 would need 2,045. ^23ruX3GE

F1 ^tEv2Lc5v

1,995 chars ^BYimd4WX

F1 ^KkRfUyZ0

```text ^b9NXIPlV

examples 01 - 32 ^NRggxtxt

``` ^KmDXSADz

F2 + G ^B68eDKmB

665 chars ^eQUaZvim

F2 ^PAsAmnLC

```text ^1KuZVmVi

examples 33 - 42 ^ZRUbhMGT

``` ^fPX1gmaH

+ two newlines ^LHNztPCn

G  retry paragraph ^7KAkl7Xv

F2 + two newlines + G = 631 + 2 + 32 = 665. ^io0VFBC4

F1 + 2 + F2 = 2,628: too large to combine. ^l3taHm0F

Heading + 2 + F1 = 2,015: heading-only piece dropped; path retained. ^L4SCIR2F

Paragraphs are separated by blank lines ^J5B4FM6Z

Pieces before merging (not passages yet) ^yWn6Z68S

Heading ^0oyVHHKN

F1 ^r3mfXHwU

F2 ^Vw85K8JV

G ^WacgEl8E

Pieces fit: merge them ^AoXTIKn6

## Drawing
```compressed-json
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
```
%%
