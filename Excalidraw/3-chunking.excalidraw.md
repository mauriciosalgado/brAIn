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

BLANK LINE: C starts the next passage ^EP5SNbDu

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

Obtain the workload owner's approval and record the maintenance
window. ^vV8FKj0V

Paragraphs are separated by blank lines ^J5B4FM6Z

Pieces before merging (not passages yet) ^yWn6Z68S

Heading ^0oyVHHKN

F1 ^r3mfXHwU

F2 ^Vw85K8JV

G ^WacgEl8E

Pieces fit: merge them ^AoXTIKn6

## Drawing
```compressed-json
N4IgLgngDgpiBcIYA8DGBDANgSwCYCd0B3EAGhADcZ8BnbAewDsEAmcm+gV31TkQAswYKDXgB6MQHNsYfpwBGAOlT0AtmIBeNCtlQbs6RmPry6uA4wC0KDDgLFLUTJ2l

H8MTDHQ0YNMWHRJMRZFFgBWRQBmMiRPVRhGMBoEAG1QPAQQABEAQQBGfiJ+ADMAFRjIWEywFDAY5ARIthAIVgAWciI8WQQwvIAORQ6QfhhsSUEENoAGckNJTwRZkBowf

HoAaxgAYXpMenxMgGI8mBYATkj5GPl0VA3Jdc5GXF39w8Q1wxoodHdEmLFbCYTAAZUgi0QHDsMVW6y2AHVuvwEHlFGF2GtNjBwRBISs9hlyE8JoxfMl4Mt6L9UDJWvA8

tNlo8uFAAJK4CkpAC65GKhHiHIQjE4IOJXBeZJoFJFYpWMBguFR5CotAYzHgw1VdCYADkmLxURd+mF+tMZpFyNgaFkPDAakr4MUsD5yPIJbgAKJxBJJVK8kCcKC4dAO1

EAdnObTaLEi4ZmADZpudyDhGBthaLMKn6PdFQhnZhXeBapkABL0IgAAnQVcY9BqVfkMBU8RoVd+0sCvhiB3G2EYWFKpcQFertfrjebrd8He8NG7yT5TDAoOwGj4TWXiQ

AYuhVMD6c0asgwDkcJINSBPMU6irqGBdFhz+Mr2BqTEVIl0APqEL4LK2YgOgnDvgASr4658GsnAwKmv5lmMEx1AyoQYiAtw+Gmm7NPw3jDqeAAyA4Zk6LpwSAhBEARKE

gGONZ1g2MBNi2aizp2C6SD2VovCgmToNMIAAL6kOkjogBo8gAJo5AAqgAits1zkJUfAlqe9SNM09IJimIBdLgPTwH0gzDKM4yTPALDLPMkLLHC2JvAcxwJm08b9MpGF3

A8TwvE5HzgIQjA/H8vqAsCYIQmp0JEisWKIsiqLopi8I4lFmQxUq4ouPwUoUlSNJ0qiTLkCyQYclyAb8vuMD/oB2WSuSmZyj4+ZWfeapMKieQdTqjD6owhrwP08ZtJEe

Txj1IDWranhhmRRYUe6zxej6iSVeQQYhvNE1RjGcaJsm8Hps1QH7HmjqFsWJ60QACvOi5VudobMZOviKFWEHoLgVayMxxRZoxjbFAcVZfjdii9vg/aDpgNGZPdXZce2z

2Nm9NAfV9P1/VWAMgkD/2g+DtSQ9uq5QaiCZk3uB6YEeKm1C+l6ZDed6UA+T6YEzb4fuQ4M/mS+B1VmcygfQEF0BuCAwRR2GIRZKFouEbreB4v6U+QeE0DRxEnQtxZUf

DiCI5xs6o69TEY59XjY6MuOA29uNEyuJMxAOuB8Yg6B5MJonTeJHu0n1TLTCwFTQGp7ioAEjALHA5ANPA5wJtpjTLAZRnWf0mtIZZFxzLHdkpY5ezOYgRwwOcMDFMUWV

efcZV+aXAUV1XNd10CIK4vimWwvFMBIoZKIMsXWzd9FhJ1ySuVNZS5DUncRUMiVIBleynL+nyAq1Y69WUR6eUIKAqmNCJ8ptZa7OdRqzTauqA1Dec0yRG0Cb9HGU0zXa

81XUtHrejAeI61N6BmDC9R0u1oyxnjNMJMek0ykT3udLYl1yJ804KsNQWRQzoCPteGAkg7gQBogiQgUBpb4FgmfLWOsSIFjQdNXiidgJhxEmJTIbR0A5AAOJlgAPIAC0

ACy4cqifFLAnBA5xwyp3gJEKm+lEoMnGuic0kQoxhHGsrEYudFYJjQgXOOSxR47GbsccICZIgwE8rcBuvlXhmM+EFEK/w2ad0iniCeMITGDyMmidCDkx7pShJPGI09D5

zxAAvWkkBirMieOvDaIBqqCl3iLfeK0Il71ao6LU1A+q9F6vfA0fAWCxn6HkC4YRwxWhtN/Nqv83T/zWn6eAPJNpgJ2pGKBB1YFHWvHQgC6TkENIYTdTIxEDxgHgFWNg

IcwZ4UINHfJUMYZDhHCASZMgZlzKZAsv4dwai0EBCuNcUtlHU33IeVgDNTzcxZtXNmqpHy2HuZ8XmIB+a/iFmkuUIFwKQXOTLY6MB5bISStozCasySokvjQ2outSKNMo

sQI2mzsBTJ2aQeZqBFmHJWTxD2zD0DRDYf7TIAAhCAkRCIaEwNMPhoi1LjMkXI2RWdOhKMqeGRQlS2h9AmgMcM6FzLgoZPo7Rtk+D2X7v5Fybk2geRuN5RuDj3jVGcb8

Vx4Uu7BIJN4uKqVfHD38SY8eGVQnZVJLPAqi9YnL3iayCqICUk71Og1XAWT0k5MKVfAp7U/XFMGnwAYTQ2jSKfjU6adS5qjMWk0laACgGtPaaA7abVIH7RgXA46iDhm5

hQfQ+N6laJ8N1J6KsoI+GyTAtsCtuo+GlE9Ks1w6yNKIDLRWqtNa61VgbU2k5iQzkhsviDXcVy6Y3JLW8/Bt4YjPM5jO985C+YrgFn+X5QF/ni0BdBShssEK6IhehKF2

FYWa3wgiwZyLDYbM7ZW6ttb62NubYSz2wE2i+3YYgc4npZLIAEZEVAOQmXVAkSAROKdlhHmmNnRRQ8IzLFFZZPIEr0JSuMYaku6ry6uXcjYlV9i5VOO+FqsKfIIrmpCQ

awJA8uXJSw0EzxFqDXhJtfPQq9rGSOvKhvNpVVt7CzlPYr1LUFSOgUXfLqmoil6hKZTMIYQmThgTOGKNX9Y2oOLctF4SbfRJK2uAiMe1oGHXgYMpBBa43XQ2dwz05awI

5CbVkKst0ciglBDwz0oIW0DjbbROzDmnOehc25jzXmfNk2Hee5JK4abXIDTdGdrN50c1eReHmK7Plru+UJrdYsJYU3gMCgZZIwUoYMV5LC6sLkjEvURa9DDb3tpAIFz0

jnnOufc55uzkXGFEv4mEL95LECB2tOqEOCZQOICjjHIxrKtwtFYJEdCGdh6KqQ0ehkLAZiGKLox0xOGQAVxYDAfoxRBIqzsR6Yjx2a73eKDqjxPdLUHeNcqA7VH9WxTY

9KTD0Sl7cdKgk51/Gt41Tyx6iJx8I6n3YOJhAUapM31k/1eTcj5GRBGiwPIekNP2ms3/RNLSDOdIzd0rNZnc3uuvFZrTxZUAYPfKobBAQ8GeEIagYhtRSHoHIcV/d1D6

tgERUW4s7t33oCm2SjIo2WzjaYCHcM03KItjm4sVl0ZyBHjcpyhDmowgKOQ4rAYe3pUmNu0cYo522jFHjvXHyN3HF3Zt3bp7X3e4+K5WavVnuMnWr+5EgHXGV5r1B6m1

1kOMmNUDzDsRkQz4+uGqjqdyOH58BTitk0/Qce1NmgT+nRPdMk5AYZrpJnek5tK3muUIzC/oMwSznB7OCFEJIWQihVCL3ayvXrZFEviXK5l+JAA0giFgqgNhCO2J+lSs

PxEaVZaabXrAExTTW6wRkihLjCpzgrVEgxd/AULubg7lvwyoEiOgfMV3HcrVu18YKZGAQUd1cx6jsVaPvdQgE/uHvXu/b5QcZ2r0hA6rwg58YR6CabpQ6zzZII5Jwp4B

pp7o645mgrZ9Cxh571L14YTNKAL6al5k4QIU6mZ9LmZ6yWYXRi4UTjLlyfQNgvRVg5AIigg1ioC8DShVhbAQBLhRLQytpwwbJHAMEBCNgsFsF3CcHtg8F8FjrkznJ5Do

TyHxaTpyK3JngZYPJzodQvLPhaHvJZZfKCxR7bqFZAr7ogrlaKyVano1ZKHd60J95NaorCGiFMESHsHSHcEwC8FuxML8T9DDay4gBjbBxMjnAq6zYYZL5wZHjJx65+I7

Z75ir5zH5GKRK0aW7FCnbyC1zKrXb37O5W65H5Gv7PZeKf79zf5TS0b/6sZcAB5AFRKcagGh4QFJKR4wHR6eqzxx6biJ4IGMhIG3z5JBpDSWJKYrYsBr7YGaY0EJrF4E

HAJg5ppGYMikGV79III0514LGfJM5YLN7wCgAc5t484d4C5d51Y94NbOHFoD78SRHD6ZCoBgSRBgC6iAZZAq4soQYIBvwr5yKhyJHDwpyKD9CqZCoipbaoaVYYaZGyrF

EX5X434O6qoP6aqhQv7JKUa+6vZf70a/6pT1E/aNEzyB62oxJtE8aJIurQE04iZwHepDFTTI6p5jFybBoAnTBhDho46RhzEF77E6arTLEpoBhl7k4V7ZrbEWb5rUH6y0

EbIew0CoDQxQCPhdTzwCF+ZCEtaqnqnYCanqiDoKEjqXK0z0zToGGzpPJpb6GvjVAfLGEbo05mG7qd4Hplawm2Gqxnq1bwp3FIouHUQqm+BGkmnan9aS4gYvFy5BwTbT

B5A+xz5iKq7RwxH/FWRYFLYY7r5crxgpF5yXwIkyqpTZHTDFB5DFDRC34YnFEXbVm1nu74k0bVHe6fZtlkk5QRJUmA7tFOqQECYQ7dFMmx7gDz4J7w4ZqjHXwcnXzp5T

BJhhCxhlJ44xrClKmLFinJqk7pokEylU7V67F077GM6N6s64InH4Kc7c6ni8784yxC63Ei6NYPEBFewUrBHiRjDFBsgaCeaRFpnMrgaJyxiXz0iRBxignFSH5tCobnDn

A44jQwn77irwkn6YZZHFF4aKoEaFFNxHaP4uLka4lv4vbtlGpEk+7v7fZTzkl9nAHUlxLA5DmdEMlDLCYHzMliYZqXzsnIGclo7cnKJ5Aravxr6fybk/wMKil6YrGppS

mHk9KykUE15nRnnbklqZD8griqChhHJVgADUVYpQgQogvmsMaKeliQBlQg1AJlZlFliAUWRW4llpCWx4jMtpKWuhi6tpy6n4OWJh3RHpkse6sEVhvpkK/p9hcKwuou2l

zWtEtlYA9lRlpl5lkgllb6xK2wP5mQuOWwUk8ghEnAvxYFAJ1kQJO2CiG+VkY0xZish+6GWFiJFZyJl+1+dctid+RFZcgUpG2JbieJdFfuhJ+upqXZ41ABjF7GLRIBrF

4B7F9Jo5jJPFge8BGaeS85MmgaXJQ0E0miwq5S0l+esl2m+Be5RBB5xmqlx5OxXFmlipyKdBIAoIau6ouMMgogPhMAUAVYMgVYRQew9ufYghaKn10c31QISQMyWwANQN

YAIN/AYNZp0WDIyhcWE61pSWvljyqW+AehXMgVLpIVbpz1osAKEVXp0V6FSsJ6cVMKWNjhveIZxaKVmQ0NWpjAP18N/1gNwNoNGuMZxKPx8ZoR8u4ReQs+k56Z0RWFrK

UGtVR+DVimm26FFSZu2FSJR2RwuA/QqAtuuC9ZRGjZD2j25RpJdck1fitFlFPZTR/2rRy1Yew54OqSG1mSfR8tAxM5EC6EglAlwlS5WNwqamT85w51OBIp11hBqxyl91

lO5B1OVNtOr1DCF5zOV5eCHA3AQ0IA6MYgxANAlgshigqgdcuKzwGwAA+o8ZEqMN9NQHXb8EZCAGBIweIawV4eSD4X4XzHissscsvJfO9SIV3WIcxJ4VIf3bIQADqMBL

0QROB3DMRsg5BCJgzuAeyJAGBFhA1821hAgw1MBYAg0HAbD7DfQg0yBo2gRL0DhHKUImmxy/SEA1y6CQwvlOEc3i6fnATNqS1QCoBdCYDbAeCVWL7ZmWLsomiwVyJG6w

ltUZHlnYaDVHAok9UFH9VqqDUkXP6jUUWVG20dlTUMZ1HdkMW9kLXB40lsW8YcXrXp3jkygskZqSbCVTCo5h2G6ob9DnBKYx3zHaXyUl6J3EHJ1kFV5PVUGFraXvVsiJ

DrBWX+aZDKNYgY3uXNAqG41Tr41OmIB+VXwk1Lrk3fi5ZhUFaelXHemgoxVM3VYs2VJs3Bn7Fc2ICaOqN5X8Q7iFWIAwAj5hAABSCY+A0wI+0DbMicjIlwoQtVCD8GRk

q5igukyF0JzVqIqD+2OF+teFSqZtTuxFWJ2q1t1Dfc1FFDxJ2INtYS81lJzFA5tJ4eI5XtrDm17DfFJBIxvDqB0FLA/Qr8amIjW5yK4j4p+56xmaMjcplBCpCjb1GyjI

kQ+yxyOpay+ptEKzazchpyOjnlah3ldyBNOhpjAVRj4AFjAQVj7pNjtNdj9NYqjNKszjIauEiV75BsrhLWOzuKfwfBjdwE3CAT+kmAfCO49AAiCo0Tmk8AliwwUFvJiD

AwIQFS2ixulMmFaDFuXVqJvVhGxTBDpTZF7idTXu1TDtpD9TtDjTi1LFDqjDdJqxXR3tMeXTQESepuB1KOPLYd4l782OSmG5F1hOO5ClEpHSd1GxR5qdJ56dexijbhU9

Hhvdc9XBshajWzxw7hPdkhHB89vhezQ67lo6ONVpjQGhyWhN/l6WlzQVq6ljoVdzNNRWJWcsjjrz0KFpNxf9HjPztEk93dM9arBrGrRr/hA2XsZYoLYRSZAwURauWZkG

L8QJTQekDVfKWTVkU0ZZuL+tOR1iZR6J5tBbpRHcY1jtZDVT9tM1VbNLztQertjLK1TDa17Te8bDeCJ8cigxGaekglc5fU/Lgz0xMifQQpl1xYEzN1kj0rMzWx6lp5md

xa2dRxbON5ZxXO7efOXpv97N+xQL6AbIoLRAO43C5wxQkg5wfBPbOlytWueZ0Fq2Si4JkJ4YmTOiDNaGOtHVGDLc2DaJfVDZJTw1ZT5FFRLGVRNbJqlDf+FTVqFJzR9D

btHR7bbqHTPtW1HDjoNVPLC5w76Olw1k/K4Yl8+OU7Reu5CdSlUjMrD1crcjCzYrOlcuapGpvNWraKhpHHppblihZr46FriWPllzJjC6drzMhhwVTrlNe84VbrlhpWDj

DNfpbzMWQZb59x3zYZBpEZvH0ZR7ITsb0tSZ1kKufw6wJArKQqabW+L7+uMYUamLxkv76DWw5+3VQHhLRRoHT+I1rZs1VF2INRcHJJCH/uSHLtS1Lb7tzDHb6SXb6dSe

ue+HQli5RH0iymuZFHLHM7NHkpdHC7alad8jLHUA9Az9XIKQsw0wvIKQWe2K9XjXYQ9XTnpArXAYmA3gYAuwqgUyDot0lXAIyXAQxNFK7sA4kgNOCQuAE3LwU3NOqwfw

Z4+AVnzd3Rs3OQa3lYG3GqFg82sQ7oRALHmnSVyKqg9AVAQieAQ3VXSIsgErh7gD6AUTktcbiuocqZftmQith3icj7UF78iD/KyD6F4QekebZ+jZkQxQCYbuRTvnmDtZ

cPCPEH5Lb2nZVDQXTtUXTbMXYBcX6HUeSX/RcO58uHQ7pp6XhHolstLAo0Km6EuXuB+XilhX87mxJX8rZXuBa7TeG7pxre27Fxu7dj+77j2lR7hEoL9AAAGgiOgKCP0K

CBQLC7EWm9Iog+GNMFEJUmhc861W5/m5gxYlYgRXg5iWB6S5W9SxS34mF7UxF4AdFwy4T2hyy5xZ2500twgbmYO303T5ELyUyCaONJO3l/Hez1K9M1z49fKbXlpUsy1k

cCIeCADXwRDXqWiqn5WjUCINo4odjUJwluPaJ1J3aUTWY2TUYRTT8i6zug8+64eqp7Fep6zb6we8lQG8cGn/n4Cy9yIu96Z597GIm5mUrdmRNJBY0FGIg8H2ZFtjMcb9

D/rZXNXMW8B6W5g+v+3IF/W/byalS1BzQ42/2SHi0x7ckl74lz7zeT29ORT+0L03y6gchYI5oimepjJZH8TpM7dbH1layME+L1RZlnUOIC9ryQvO8juyfKC43GWnf+hR

CPa6hQWfCMCGEAABqCYTAUhXV5T9geeZGYOnCUTWQQgkYJCpQKoFIU4MLnOEpKnarudDspvQ3Ob1wYgdiW1vHEmSwi521YONTJjAf0i5MV6WzTJlq009oYdveWHDlgHV

YBB1uG8AJHKHVQKCMkK2Xcjj/1Z5R9JWaxcvAx2AHzNE+K7GzC1gRBo1PAVYHwGfUYBYpLECYXZlxw2TmCwaVgr6kwDsHyJHB/HH1no2E7HNNCYnG1uc0k6ZYZONzZ1u

nQU4WEoqynawsei9YBkPKnfSXjeh76IAXBlg6wbzU8EOD/m6zMWvxEZTD9Eyo/IbCBV+5JtJ+icZfEQJgrJN1sy/L9mKlmLpFcmetHfm3E34+cBqLcXfsWx4E49q2IXL

HvByGENs8e5/Bhq22ZZQEWG0g9lt2ynJ9tcOXDPartVp5HUKkkJSpMmE0GittBf/WdrR055AC5mGlHMCYIoj89c6m7YXveTACPk92CA87gwiPa3RQW0wDQHwmmAAArM0

MZwqEL4YmAJOIlMCaoNCIwkQRQMmF2hvwj8dAnJqfjyYsDLE1idgdvwCiEMAu5TcYYfySgCC0oeI4QXQ2bbu9VqnveYbfxkG+82oDPJAhsPGIjoRoamHPGEBFax0xGOg

qZvoJTqGCLhGdMAcWneo5AqwAAXisFcAeAzELVIEDIT8AqwAACg/a7MAAlE4JayiiJR+daUXOEICPA+cCo5UXkDVGF93mhzPGuXyvDicHSpNe1tc3XT18oh9zRTrEI9a

t8nG3rI0C8K+YURPGIALUZKILoyiDkBoqAEaJVH5CaA6o3xl7HkgmdShjAJkAz3H7q57cNQsEcZFlrz88OLnNIlDxRF9CuhBLQivgyLEb8K2JDE/pUxGFTVj+H+U/pMK

aYX9xBV/Vlph0WH39lhcgqyHBgD6v9RK78KMDtjcjf8DhcdI4QVxj68jZmS7BVkn3AGXlji0A84g+UuLPkfR2nZAS9zAigsdALATAfIFkiYAPhQI+9rA0zGrkSB+uayB

EFNDhhBGsCDFrCR/ZtDkRHQluGb3RGI9ehGqLgcQ0g4NiaxCUSlnWzt4ki6WKHWLh7zmEJduKNI5Ln7wHaKDlBGXOnuJXjCmh0CEfQ4UsWOEc9ABBg84cuyFGmDaIFKc

UUGN1GyiwxRonqNBXDCmiNmkNDZBRO1FSjeAeouUYaKVH0S4wTE2LCawE4WiDGVo7QvaWJoXMK+DrbLLJydHycXRMQ+xvENQht8vRgZT5luOJDpCQAbEqiZxJonyjeJp

ABiQJKPY+YShCuJMaHGAo/cZsVQ/7r0EvFPwcxmtVIpD0YEm9yxe/H8WWOOD9DKxgE+isBLox1iwJ1YxDiIKgnki22lIuCUBFJ52TH+SeYPi/xQJ09FMGiFMlr2jTjiu

Rk46PnoOlJES5xvPc8hANuEriRea4sXhuJSGIDnuUbYCOUHe5SQ5ekgMCDuHOB9Y72fxSDM5PqqkDYEUQXksdQfH69s29ApEbrU6r60vxFvDgViJJbcDbeEUzHqBOx5C

CXe+PN3oOVimwSpB1IzsdtUdDh80uqEzYXwFXLRgJoaiHCROLwlTiipKlPkcRPnFXCNCmQbYJRJ1EGTQxRkxUT1BxxtABJWfayhsm+nsTgxXE2icZOBkCT5CmNZIX4K8

pWtTmEk6vvaNr5yTTCikyKspM9ZVZ1JyQs7r6O0m6daIkM/SSGP1EAygZstMyS91kigtVAmAT0BSmdBlhmAZ4vqdVWgyNAhmiDHbOcDSbZs8OBYj8eYlYHfiS2RLJaf+

P37gS+BBI+scFMimkiCee02YW00OnwTjpOHLSEgQUFoSjqmEpoPIjUz3T8pj0wqUnXo6vTSpzHXAu9Xui0zDR7YOGjMniD4AuIv0UYKoA1F3R/p7s/ml7OoC+y/oAcnw

RrEElgBVClok5kELOYSdHS0kh0bc2dGuslJTzCrGpKSFG5NJSA8mWildncTwxHs7ZFWG9kRz/ZkbSXJgNBaEQccxQMsJgDADWc7J54yDHh3pAzA4MDVMpBKkmmviJZs0

zBgUwWmYi/x/ncDoMKEHKyf8qsv3NtKmGocKRB0knnfxOmNAQ6e1PsSoNEpYSBSkdK2eM25EACZxi7Urk7P2LvVEI30Kbk5VFGmU9JPUGMNMG8H8FNmaKe+eYHfqmVn5

VYV+aQHfmfzEZprESSJ0TkV8bRkk0Ic6WxkRC5O6SaIfjJzk2E858VTcUXJRQUzywNsR+QAqcrALQFUYuucSgRAJirJTIaCqmOTZ8ygSY0YYOrSUzZttab4maf+2ODNh

cAVZWyVvzlnHBLaVtdHrwPIa1tNp4Elec2OmFE84pushKXfzJ69sexqbNLrvMumogI0yYdQaM0o7isJGJwwiQ7OvnGDSJ1wiqcuIJDBjMgxdUuuXSNaV1q6cgdMA3U/J

TQNurddusPE7rBtmCobbwrISrAAA+PPhn0/DD0jkFIenssAnp98M+S9JenwnkARC/ZzEIgFfRvo/RKwgsAAOTtg+cUAdYBQAvqGAfoUcA4LbGYgGVn6CQQwLwCXpdAXg

lYRQIksYDbB3ATBWsNYKYA/R1WMhXwqjWBDMQcYjONbr6AHpVh3ANS4KOwUfBUAPoI+BUIDRxh7AfoPBOZdgCoBVhngj4TAFWBgCqgIAl9fANfXoC30MEs4HGO4DXq8B

k0iy5ZWkqrBrLJlhyLZcxF2XAgDlRyk5WcouU+B2w1ygGt1zuW+gHlSNVZZgHWWDK3l2yz5fssOXUBjlGS05Vkp2UAqnlNykFeKXBUrK7YLyjZbCo+X70EVPylFX8p+i

XLAVdsLFevXuVVgllEK/FVCteUw04VJK75Uit+VoqqVmK4FXSrBUMrHlkK6FccqJU7KOViK/AMisyXnLKVGKoFbcpxVCqmVzEAlTCrZXEq9lnK6VdyrlXoqrlNK/laCs

SC4qnl6qsVZqolXaqpVMq1Ffqt5WKrsV9KxlXirVUsrCVVq+FTqrtUUqDV1K5iLSpNVgAzVIq1lfMq1VfLbVeq/5YasDXGrlVrq81R6o1URrrVUaslbKtjUBqplCal1c

KuZWirNl7Km1ZmvtXZq+VSq/NaqueUprLVaa71dGvJU8qFVRqqtYKqTVhrPVDayVWWr9WOq21zqjtQWvdVFrxVjavtS2rjW5r21pqlVW6trVjqvVvarlc2odWtr41s6k

NfOuTVLqe1pa1dVmvlXTqg1iakdYuvDXvL01pKw9eWuPU5rT11ahdRauLWRqb1uqtdRWqdUCrTVvseqa8I/JNT0AcvUFhsBCYUpMB6AARBAEZQ8yqq8LRbL3MfYNV5Ek

06aX+w87FF5pGIwRSRhnk28qxQE/EYvPClEaIJyHMkVrIkHX8qRes3oth26aNBjZ/qRkYdRDRkdhUKcCESzwenUdbZRXOPoxxAGXDzFn0xAIAu/LMTs+GyCTWaO9Gxz4

5ok6BdaOCEpy7RacxBY6NxlZy0FcQwmXYRcYfNXyAGnTmilk2xjgIUkPcZgN+H0BSgmU/AbEz2EJMiByG19uQOmA68tEBvFDOhqYGW4J5OGpHvLPw0rTCNas9aQ70JEY

9pFoglsTMOo3tiFh9G2QU/yQZGzA+R1V+OoiTAIV9hnIs+QVN0F2ziu8fIwaAJY7vU351kT+WDPUaIBqtH8shdHO2yQKAh1rZObaPMaaaM5CknTXTT00ejEh9hIzX627

54KGtICmrc1sKFewBEoLdwAAEdzghEXULqEk2dzeZCGxFsuUvgNUkw2+OMD5r0TYt2hY8z8dLMnm4ahqoWgCRjwXnTVJFa02LdFKo1tib+dG0TJywQL1D+x6U02fIgmi

KoVsp8uSufLnbGLZxpiirc7OELxKC+Um8GSn3h3GtzSMWFGWoTL7KbxJVfKSWEMdZIL5JKCvGQNvdHPM1OxMhKsZrJm4Kc+KO8hfxFwSWTwicYOhdUIBJqLe5STTNskW

aElkV+hY/ycWKC2/jy4AUxWWtIe1Ly5qtLCjZrMv7xcFFsBCcg/xWECy0pB8o6i/DgQ68kmPG62XxuK0CazhjssxSxxuFWKt2Dwp4eL2wWNTJc1wSWvIF1D4BigmAKSL

JEBGbb4NrkHbZqGjqIMEwEQFTIKlQrDzTt7487VLLRFXbgt080imFqCkTVxF/A6XQ0Vl2u8xBCW97bRsUUITt5ciZCXtSp5sbioOW66UhVB1XUitPI4qSYp543ylWmoq

sDWCgBFKruWAQOZkFFGt729JSzAHJtqwY6E5gQmBapq6019whWm6xv1seaDbydmClxlTrG1pCJtAYlvYUuKWd6LNdwKhSztsl3s/uotROGpn5mahudXKXnXmNLKeTV+n

QisSLr8li7hduI+eSno+xPayNL2yjQruJ5jklFSUtXZqGWB/bNdV0kjrCImhV7p24OoxZfO55MczdfPSxYL1vKrjHh64+Af+pp1HslQktW6G0CERQAyw3U6bnBpgYn6z

QjCgPZCOMghBQ4miJ+CnGO1YsGBOLO/Rdpj2P6ret2iXWRoe2O9BBUihpnLt2m/75Fm8/PQbM1BslFBJekSkdUUxlJDco06A1Rwla16XpUOhvUgdvmsSW96pLwDUC72I

AKJO9Iw/bnAXCSFN+jKBaPpU2da4Fqc/HbJMJ3abG+rogmUNqJlJDl9XfVfWijMOGGXoDOr2HAGZ1JkEKFnHbh3IB6CNGFqmBjDzpYNKCBdks8uNht8k8GE9d2sRTBxV

mkaIt3++Xa2MV2SH9ZjGzUPIZ4YDijqOi1Cvyny2iNCtNso3acJKnQ6RN5XYbimhq5NdSAKQQ3P0cGNUxww9XCaWMa649c+uA3RUHdxG7ZIxuYAebn/Om7p1ZuKxxbqN

xW7bd1uNsGbi8F2O7d9jTiA7qLQ8DHdTuhc/Ypd2u63cejNAB7vwCe5S8Xuj2CI59xjDRGrOcLLHDPzoODAHOmcM6S5z5JpGo9GRy7dwedzYjZ5q0/g+/pI2f6ijIhzP

fFrkUbz/9UhyoxCMEqsaFDIaJCjIn5SRo1DBi//hDvgNlaBRirZFBVyq6pA+jdXAY6hjmTjGU4pASwHyXq6xgeoXJtoNyCmOrAZjMgQbj0aW5LHNjscA43N0m7SntjxN

I40UBON7wtuMRvbqcazIXHKwVx6nVpJAC3GYAN3XAPMaSBPGXj/eF7tN0lqLaNAwiMIGyHQAiLepPunub0Ggrz9FMLmvMTZFv2C7ITXBrIzCeWm5HiRAh6Lc71RM7Ss9

GJnWeUZS20jck+J31P9tKSea4wUJD07lIK1g6a9F8uvdocQMw69DLWXULUBhlGSMljAXJSjU9l1gYA1YDiN2BMMgAyzp4CszxKrM1nQ59Zxsw9C4iD7UMbWtGUnIxl46

EFU+3rcTtn3N8fS3hgzSGgLl6mcF/otsyjUMmdmmA3Zus2SD7NIx7cR7FEJLUwH9BsAYQKSLLRBbkGQR8LN08ZGqTz9kw6IagS+ZykudUpHCjDcwJbiBagzfnHI3wYi3

hm09uPKKT/tKN/62WCZxCW1H5RIEi9mi5eMK0FRkm8CeZykwWavk6HizTe2iDkFwCrGqw30jJaKHKVeBcUsyUgPYN2ZKjQluyaYKqNaWMAk1xFiwTAAADcT0LwNstNBN

bFk7YZ4JctwCkwv5LEzUQRcfnEWuALKzpRRbYDUWoxtFyiyHEYtL0WLqNMGpxc8DoAeLZoGi4JZ8DCXBzujc1qjJtKjncd8C6TgTun0N9zCumsnbnM9FJDRt/h0MmZok

vv0pLpF3NXcAVHyWvBilxUXRexRMhVLzFx5axc0tcWdLzEXi/pZFCGWRLR7bAHvsiPlDO5R+9MQwrzLsi9tSiDWtm0UzgmuF5cHhXwuhMFtLagF5PfkZHiFHl5UZ1edB

PXlxmsTnY5RclIQKvwkCGipkVMBzy8kdsyQ/XS0cN2aHpGWFos10eQNLjUDv0tSHYqIBl0K6VdCJbXTcVRtcINsLxaGB8Uqs9WfdcNrwRCVhKEdnySJSsm2zZjWO2QYF

fQGOXfrg15hveo+AvrvgDlflmNbbFDD+q/Z1oKsJvW3qXL8AoawtZepLUZrb1/ajdTOqHVzrO14N7tVeonXQ2p1D6vNcOprUvrx1K6j9Uer+tPWz12Nuta+uvU+rvrhN

wdT+u3WI3R1ENt9RTc/X3rK18N2m+epxvLqD1+Nu9VTc3Vs2wb9N5G5DffW+r0brNmm4LYvXC3GbTagmwOv5uS2d1Xa1NSjbxti311J6zGwjY5uk3cb3NjW1+upvBqpb

nN/dVDZ5sw2tbW6023ra5sW3DbLNom0+t3UM3ybct3mwrbhtK26b0t1WyLaZvy3Ybj6rG8+rtvm3RblNr2yHZ1sk291atg21HeDva32bcdt26jctvi3nbYKv9aTP1NHt

fhoLdAPIATAQBQQLAYoPNuvNws4GQJJMPlf1w8pccr5l82hpKuYa5pUJv85wN4Ov6lZiJx7WMK2lNWZFa8/aW1agtfaexuuNLvif5aoZVMyZIZk0bGa5nWjE1+2YWeE2

CjKtEMlswVRa2uMbD/gkc2PscOYyNNk5yIX1o8PZz59Tl4bYZrt3ja0UB92bcBAzCS1fhmAjQMeIpTdTHNxUeJrInruB6PNXmiaXzsVh+avJ8qfDJVZ7sAW+7kuge4Ia

JHD2M90Z9EzBInsdjoLBexVBltqMhpeSSFV+JolQts82jkOqa9vdpNjJlmpAeGTNrq3atJtzD/i8ZeHPmWz7Y5qy1cx63X3pzt9hyy3wX3OWRtz9gI4w44cAtQjwEAfR

8esmKo2djk7bXXbKQosr9S/XNn6fSPHZxd3d7yQMPhNAWB7IFxsWBZKPZ6yj7V6C51aAPhoNdJskNKhgGD8p2u2Z5o2vfGv5mtDtD8rTNfKlzWoBaB6qRgdqlYG87OCo

9gHMlpEBfhcvXUBAB2Be6XTFBgEoD2qr9yCrbQbfM3ZQoIiXxEezhR3dRFsCjH8eohjVYJKoOIzxI4o2IYgsSG7HU9tLawrS7yH+WT8PoOolxxjicz1e9e348msIG6HC

44URDJb0ewnAD1/e9M/uutBD7gnOObYfa3ozLLzhiczZanN/ISdc+xyxgokdL6pH7lqZ1WBmf7Aln79wwGlc+5KZvjlYX44QJ0jmgkjpAkEy+Pbvfno9FT2WXHrw1IPR

FYZupxY4mFWOmnNjyC3g7adJ4J2s9zLe8wqTIVQ+K9/RWheGcYX/HYzwJzvdwL0nFKTJ9k2yZZMcnUMPJ8PuS6FO9c1Asxk0+KYVPLG5Tax1Uy8ClMsvvUSxpUxqdZe4

BuXJxwKGcftzamTuuBaJzcau5Gn7j93e+habeEvd6Adz6yX0FUfH7wRddjk7QdB5izYM3z7IjWUvbK5Kn5cZsoa5qfBcQJEioe8IcwfNWYp2syQfGehyAGexq5Zx4hf6

fmhLgX3Sh7AYIlUmhNuL+h6uxQOhOrdsA54dgfzsvdyEktfAKUFkj8Acg/QHICiGrsa88yqmQaVNVlpoRxpz4hmkb0/P+biipDhMLpAQchagXc8/u3VcHvhcGnI9uLbI

pweOvWnvFb7W1AoedPEXsKMpCNCjBH5RrPjjQyM83sBOaTEzsib3yrCQa7AoYPjqJek3I7Z3WAPAAu+jJWGQ0xfVZ8Jyx32GcdtrLZ9ZdcO2XM5Ij0nWI4fs+H7CIqa4

y/bh2rv53nHHfYtqVdMhNEqr7K8ZEzE68o0A8tRXmI8nsH/TBj+HmEAuyVv/J4HyD8g4RN1uwX6syCeBahctPJ7vtVXa6+TM09+r22foPh991wWvHq9oZ746xejPqTJE

83aG5bwwDRecA64uK9eNAbDgTutkJIA2B8J6UGYdNxeKBIfsG7fiEaN6eKdsGztpV47GW4rfGubt1b0x7VdrFRbEP5GtEy29attv0PDGzt46GKvqLe3VkN+KaCxwDPvH

pH0d+R/Hc4vJ3H026y5mYIcEJQ0yKsJUhfiG4HxT8SpC2bs85AHPuymZC59B7ufkyYcZZ9w8Ma8PNn6mlw66SJ17OZzSnQ5wkJvcnOo3K5nSd598+JB/PsYQL4+M8877

kgktBEAI0iD0A+EdZb3Rk5/f8eVMiDYT4+OYOTSi3o8iT0cCk/8KehT+2T9U7g9mO63aDmLU29e3iHMTmn1LXC7WH+ounqBPkiaHZHiU0Xv/TF3AcwtWeqPsO5HSIUwH

UBsAxQa56w7p1bedve3wczu8U3qEeHDhvh8e4EdX3kFcXi9wc6vdHPH727055zR0mp8jv0ME7zvrqBKOP3U2M8Vlbha1D6QZof9x88X7g9gP4nsp30Jg+XZ/nousD8UA

g9I+a3KDhDw1Zl1n9R7LV8exp5hcYfux7Ti6dT2m+DiRosGDRByNM8wH0LK37F5R/emiaDiIT2j+gZt11SmPlpoDRVUlqqBCITp4oLJG2DxjeP/UoEhUkE/Dxo6igYVC

dTiZHbw9YnyPa1/a9QfAXPX4F2/v6/1OMHeP5t2PYdc0b4pyu8bwgVqGgGXHrAJexUkjBQHiP6LqhxvdK2BvrPbP96hWirCqhdvxyvAL6CKiI76tIAH337729A1Xrwf2

OUjJWfnf1nFlo91F+2envdn+WeL26Oe9JeFzGne99I5azh/jvAf6P7Eh31q9Bf0wFwDuBoD4A646Tm8yrUzeWJ5+cJWgUv19Mgf9HbX9keW46+ljsjOvzH/B8U+p6cf6

eo38N+aejfifWn11whep5z3VBklZCqwN9eM//Xq3ln2VNwuZAsgu3u3K4irAbcpuf1RGoDR8CyjjDIfth9kAP/UAJlJ/2OGf8eWX+Dk1/2P+5QUTD6lNB74xuPqcMU/E

9xi93Dey0vc5zcR1e8Y5XnzOcWsffxrgH/RIGP8CFZ/wRpX/AGnf8DzF7hIBJaHcEwFQQIRFkh+gIgB+JJfHKx0gRoefhckoHVgxgcODOB3wotfbrxxFdfWt1H8CjZE0

atbXfH3tdEtD7Tz0KjbTx5JerfT12hIwSxEmh1/Zb039mfD33W8SzPCwNU8YKwTRpiaXGEOQrBAIBOs3/QgGBh1gVQGRp2wXFBbANgESwO8ZNJQNFAVAg4FrMNA5bm0C

MA3QP+h9AwwIWQTAkSy3d0dUyyOZT7K70i9utO71i8M/R71nMVOSAOS8fWGAI+819UUUuVlAmgFUDbA6OE0D0ABwKv9nAtQFcDjA+4GSsXuBoElo2QYoA0AKUCgFuA5a

Bvxrs7zD9kh99cQ3F5QscKEjD0aAjCjV9SnH53LhNfGT1hMCNJPVqd9fZT0acYzVtzN8ldHolhcECVoRt8PXFZnm9GDKQLI8mfCjzkDWfXexaw53ddxfcl3JHVoh1g7a

EXdPAofW8CR9DrWu8gA27x2chHB7zACnvCAOvdc/DSWXN/WNfV2CN3bmRudWgSWjAAwgTgBHwcgZAEIhKFMgKThkyfjyd9M2Z+CGAyOWWkaNIHOgRHk9HCE0k9e/aT2R

8uvboMT17tUF3H9QLDWUhdYzIn2S1xgtqE1cpg3D3OARoM0FUx2FYdzM9DFGQKWD+ReQN39EAF4N5pTrbbx+99vXUm2DMgVkO+pQlDkP99BzePzWdfAw9xCEbvGSRACZ

9EIIS9s/VSWOdIg/P1gCdgtdz2CmAdkOL95HdAA0B33J8S/dKgs/UkDaDGYj0g6BFMj1diieQDaAYAaYFwAQvVEOyJqrXrwU9LXI/mxDLHXEKGD1PEYKdcSfePCAMW/P

T2IcD8BCjfho6TzXmDzPRYMs9t/RvWRQLdeaw4lFrS2BLplrBxV4InFda1cVG6OFB2t8ANuj2tMgA6xDZ9WQJSNZ2QtUNeCIlA5BHoKQHq1utc+PkKYA2lT0GQBYAZZD

6VMvJzwC83PPLxCBc7ZUMA130eQCZBQWUoDJB+ALIGQA2gDbQqDlaRDURx4XBqibsW7Vu2aCHCYt1gcOg5EP79LeYMwVkXQvoPYCkTa12e0hvFD3xDfQ9tzn80tVyAZF

9PbpGD41MBCijC6Q6cS39lgnf2T5aIUgK2DQ/P8IOCj7H/zsMTg/wMn0Lg+72CDrg0IJUkXmCIPk0og0zQ2Q/woFlHCfYJ3Q2AwINkHwANAX4RAwgQ5FyGB+PZcIKseU

dkTXDKBaH2eY6A0DyOBfzR0IPDe7VgKx8Tw+tyd5G3bgON8CfU3yS0jpfB2kMg9EQJDDhoTKWhDccN8IpMYw930ZCVgjb1ohX4WrW5DQ/RSJm0gIkyxL4fAy73FC1NAI

Mgigg6mllCs/W4Je8EI1rVS8ngtFFUjOHCzVHDWEP2BCJpgT0HQAwgWSDaBGAZ03nwu5DnT901MWXykQ0QRMALcaIy0P1pOgxiP/Mh/eT2PC3QjgLPCv9C8OscrwviM+

0O3HsXLd3XXDxmAdeJQlUwTPEjwZ9pAj8NkDZI78IYcV3ZsLeDzAiqKrDNg9SMgV93MCOT89ItP0uDoI2xlgj9NZmnNELIh9xqjn3RdzQjn4PUPLcDQhcL91sJE0PpFm

g6aJa94faDzR9YPCKJ35Efc12g42IgYMSi8Q4YJSiBA+xxdc7w8n2kxKfLYTI4BmNf2d8lvBYPpDYwr8PjDFxHOkt17hCN1t1eovnxHDzQUFhHxBAbABYBkAPICrtKvR

vyydhofpEzZhPba2/YSnL80txwogRQBdmAuE3C1XQ0KSU8PQ8Fy9DsHH0N2iLfRM1BFhI1M1hQowXSGzw6fAqPUN3w56QZC3pMqMmc4AlvR88VAPz2c8cvPsI88HQ6qN

/CGY7sOy9XPKkPZjhQsLzEl//c+3HNgAuvlACOouUJMic/bqLz9HgvqK5j7PJmKy8WYvmKC98vd+1HChsAH1gQgiYHwck1XYEKmh6QY0IHldISaQtCtw+gLKsbQu0IdD

4YlHytxnQliJH9Yo+q04DcfJsW4jeAnPXN8xg/0P9o7whf2kw+rUvSshn4TzVgxhmSSPwlio6mNN0cLBMJo8byBa1sVUw+xVWtnFDa0bpF+FugLDvFYsL8VZ6MNgGUTr

AUNqj+Q2dy1Ch6WsKiVuoKaDiVvvf3zaUwIZ4CrAAAA1LpNA9sC4gwASwFsBPAfAEsBA/fekgAO4u+lkAJbZ6x4ImLbYFGB7gJ5RLiVYlGjKVAbLegNV8AZgjAhdQH+n

e8AGJqVHDpcByPEgKUBEHOB6ADyHDBmZIEOjp/jYVALJG7XlEoiqBNu2ti6IuGM69B/FgOH8+vNiIG9IzLiKn9UPGf0JC0otLR14HwkSMGZyQ8SijAyYl3z9d4426NKj

7oumNohX0f8Nv9ME+qOPszLcLz8DmoiCNaioIwyJgjpYsILuC5Y8yKQi/RHSUwShoofBPjMgLiDZAEQDYDAAEwNJy8ittZXxc1TY0iNqDdeZCmTgmgxEVCjx5BVEKZlo

qtyijkYmKNRix/T2In9vY4BOSj+A3GJgtHQD9kyjw4p+FgRw0RkHyjEEjf2QSZImmLQTp3BrRTIlI7+WWYbEtSP2ZFCDSN3d8E4WMr4iErGUCDJYpvgoS4IinRct94uh

LX0UyE0Rm0hooIklo8gTgBpQwIWSATAssecOzJo6dCFNiyObXl15vNN+Lmj2gpEOTgUQx2LRCQzNaOGF3Y9iKENzwoBMvCdojRIDjbwpPBkRdEgk2yYYEMjnw9meLQV4

1owm6PMTE4oJ2ZDjsJsJrisEw72rjOQrhzwTMdMUJFjTglqOlC7LKWOMjKE0yPuCj7WhOLk4dZuN+8tY5MD1CZEMaOSTNw8H2fghZaaLzEo0HJMtwYAVaJk8K4G5Ndi/

4spM2iqkpKJqTc9TRIccexdJJ7doEpkCUJVyQd1jinpErUE1UE3Q20pEwsN2ej6PSN3WSdkuMmYTEAOXigApIW6DAhSEcoJ4T4NVf2l8wYpRHl9FfD+D2EinKGNaCYY0

t13CmA9ENDM9ff+IN8bXSf2qTsY2pKS4C9Ish+TCY8VBkRYEr/iBT+Ndo3r1prPFwUDMgIv05Co/IPzL8RkjZDFT/fCVLHjrnICJFCT7bSJmTwIrxP0ifEzw3QVZY9vh

Jkhw5CML8W9CPxL9JU65yGjvyXWPjBHnWI1YAcpU2Jxx3nfXHGhnOLbCPxLkilPyS9wxaSqcf46KItdFEuKIbdDfVRKZTCfa8LG88YpQWY0KffTxfhBGXKNUw+U6hwDc

wUpOIYQCXXo1q4eTQh2ZMUgHbGzhhUZrigMi06lxFMHKel2foJTFbnZcZTWtMZd+Xb6BlNG08SDWAhXGIBFddTFfQYRDTY01NNHjWVxaR7dZhFHCCqK1Iys72SziedWU

C4CjRwfR1KBNh4NpIYxQTPJ1oju/T+IH8mIuT3kSA00LnpTKkxlNeTmU95LqTLfNqFq8OUsAy0U8tKMFlo9FK6O6SzE0FIsTwUukweNGTbNIGMC04Yx/S+SdEHq5l0jE

H/TWuAYyAyTJaEU65UwaY1pdRTOYwZdFjGtOZc605DIbT1TFU3SQ1TPYybTNTSfk7SxXA1Iohe06V3WhzTIdOY8PoiWkRSpaRMWTJPNA5IB4/dcSgbCGqbVw3Chzd+O7

9rcZ0GKBUAJgKtxzsJ0z4yjwvdNGFg0hlNDTj08NJxiz0pYQDCexRkH3li9UQNlo+gRVAfFjEx9MpiQUk3U6NhUiFJTiqpa3UwNGPQjNsinIhbWwBfhbhEwEIAc4Bvig

Y0H0zFxKJMED0IgRrw3DyIiRJ/MpE2PRR9qUkpJCl9055KPTtok9P9jWU6QziYmkkdjcgiTCOmTS3fF9L6T9Mn8Jnd9QGoEz5lI2/1z4Ms7iE/9FCYYBAjGojZ08TL7T

VJlDyEpZP8TF9ENDMgzM2nUfc8sgfkPjpgfxklohEJN0iB5ICAGQBdxIELB8iYnJymphpVyCfEUjCaAYwPU/Jl8yqU4pJEz1ospIATOI0LO9DpMllK3kos4YivTbfYaH

w8mFflAfTcJa6OfTdM7C36S0s8uEnpq4RAM4IWzXPgghD/BIDuzD7IrKODLWVVI8SJQs4KlCJYyrMWSvDcINWT6shWIL9A2a7Kezg0FrI+iQWSWgTBVAGgA2ACAlgEVc

Bs5zJjBmFLlFxx0QLJI3D10xEPojZsroPmyHklGOCz0YpD1EM1s3iI2zsTIQIZArY0kPDi4wPYXkRWhGkMKiTsqmJQTX09NPQTe+EQluhilQPy3jcAXMCyy7Ezb1cxhc

j2FFzxciZOKzpkr7N0jiE+ZPPcqswHKoS9U1y1SEVQgXOlyruEXIud5c8zJjYAfUJIYzyA2FDddaDQq2aDUNTjIJymyGsgq9CkysmbIKvX+LJyxMjiJDSIXanL4DT0xK

Uw80tFMmqMcPcOImhVMapGjyOkvKTGsn07nN6S9M4NwZxDMsJ2MzInUzNBz5XVrJPZJaDQHOBeCEXFBAB9IEMsQz9cSlqFM2IRlV98c1rwYi3c7dLkTeg0TI2l4olExe

Sws9bKDzNsyoxTIw4jUCX86eUODcgccaOk0zjsxPJ0yOjc7NSzyojBNUBNSY5WyF1QGZHrA5wfcxbNPQJfMgA3BGwXXz6ATfNNhBYyZOODSs77LmS/shZN8TqsrqL1S/

DXXOiC0UHfOXz98nIUYhj85s3MzjOc3PEpLc280ryZgTHNqCOnd8wURps5HirIXc/jOdyWyBbNKTA0j2I7yuA1bKxie8iLIAMQ8rlhusmc5pOUQkwR3xc9Essd2Ty581

PIsUOfO4To8apBjxgAJeBqQoyR0yJk+EdQmAFKBpgfrkAcENIAu2yB5GYhE9SU+vPmjcMInJkTfUpGNbzFspAvKT0HCTP9z0CmnN7y6chTM3DBKI+05TcccSh2xwgRby

nztM43R6Rk4RVHw8LshfNFS0AZwA9gfoJ/xypD8r/IHMb/F/MsLOAawuQCH5VAM/ymzRwoKzfBd7NAiL8lXI1SSEgyOAh9nTqPnNqE/VJzzn8mVJcK3C2wr+oN87wqwD

WsmXj/yJ0ryKnTbUuRBedYUC2JNDPnBmm8yGA6RKbzIov1N3TpC8nOUScQ5DykylCzApULQ8jjLwK+GfD0ZBX4Ggw5yKYqSJ6TkslPKncKITNOq4v0lIFZNhjCYryAKX

HqGmKy02DIrTTTatPG5UM3l3rTEMxU3QycM3lxbT9uLU0wBLjAjJiLiwYjMrTSMwdPFJh0zIFHCh+ajI+4kxFMiB9O5bIued/je9MBMhZIorFRIMkotEL4HYnMPDSchR

JqKUCr2IUK1PDAtGDIs/vKd82i9HAqQ+gZOBfgEErTL6LTs2fKFSKC8gBGLP0yYo5M80iYsgyZikyQAz5i/rjgyzilCA2KmXBbnlM1i1Ys5cdjLYs25DjZkr2K8Mg4p1

Mji7tOLRTi/tLIzLipguuLpgVAT/yjXTK0Njv3RcIZBw0DNixyscS2M784fXJINpmwJ03txyinfhrh4eERS9zgSn3IqSEorvIDy/YqEqwLSfHAqUypvfT2sgQ4M0AZ44

8wZ05zp8wwsFTxnGz0hTOfcJ258onBrKGjihajKIBr6CAC+JnIIEMIc8yJQk3CVw6CmfiX4uvN+LjsRvK/jm8yoqkLECkEvEzD0yTO7zGis0uaKcCkOI1BJvXD1UyIeA

VhRL9CtEqTyBi8gqGKxNTZHtAoleVMfBI/BaybBkEK2CERQwXFEfkVAd4AKUXgGsBiN2wBIMrBUaB/0+sKLFIrBg2ID2X0CzA7LLRRCIJsvyQWyuVPbL5ATso+huysAF

7L36fsoOBByvpRHLrA6sGVN3AKcoVEZymcHnK1ADwKcS/CzSPPyk/S/NVzr89XIBydUhUKgCHgnksNTaIFcocpaAdcrbLkwjsoLQuynsv4A+y5uGPLhyqzlHK0ac8tGB

Ly8i2vL+zZiFvLcYBcvkdRwj4UloQmEfDwjMAbhHYTuCiMtAI+SR+L8QjEhMsdyG8sQs1LZEtMsxD+ginJU8sHCErzK/Q+pKGI8OYOn08NaF+AjojsrpIMKBUreyDd6y

26z4RGAOmGeU74DcB+hV8pgD+odApgi3LIK0gCsEnAYGm64fZZiC0r7gGgB0q/oPmmrkRlI/LhoPoMs1VB2CdYC4JEixcslzS0eSuOVJXNUGUr389UHUrHAzSs7KdKn4

BwAUaAyt9ljKjYFMq0lCyvDkrK/mlsqpVByvoAnKlAJyoHyoSSfLXErSIISdIifWCK1cm+w1zvy+CNWTH8xgrBzMgOSoUrPKiKhUr3BYKBmQNKqcECrdKkKqeg/gcKpa

rzKquVirfoaypkAEq+yruBHK9sGcq8K6YHjFJaMIGwBLEW6CyBPQN93DLnMtz0QZP+CEiaBn4WENE9hClUuTKt0ioskK2KulJCycyk0tsdI0rRKNBZDZTJEjVM9TPURq

QzpIN0XSySoncmQy7I+pjA+yl0AOwdwB0AGzGgE4sUAOwOTCdKmcpugwava3gr4gAIG2hawUKCPoqwbstOUxcogD5p/qogBcqxLWiFBAvqhd1QBfqw5WwAAaoGuQAQa4

MUhr9zX6FqBIa2QGhr7Qb6BwRhy5iAHAkav4A2BUa9GuJrMa0/JAjE/CLzKzovD8sKqvy++xWSoisqpM1gkqGjxqXkQmoxrAag5TJrkgha0prTYamtPBaa/gHprYapmo

RrWa5Go5qclX325rcg1rN3FzcnHAALpSlZhRYBWNhRv0u/AnNwA1StHmYr/JbUprhAs4jVqJQSlRPBKTfQPKaKOrA6K5ZNHHbI9cccVDAoFdPHovJM44msrOzMSmSs9L

qCrnxMz6CoJPMyLJajJoBcAZJSsQKABoCWqgSFMkXSpgB8QV8X42vM8ypshENa9TgC4CuA5swEr1K28tGNqLPQ+otzKg6/MsECFM/3kUFh8rXSGZddS2UuiqyhOpny3S

6Sps9vfL61sKUg4mgKUfKpgA+h54kwL9lfrVSurNRyqCCxrl3DBIXrUqpeqSAGIHevXqF4jYC3qUaHevyUrBfesHM3s58t/8mot8vyrha4RyKqxa3VOJkQc/8ulqZU4+

o8LJAU+pXqL6oiyvqb61et3qH6jcDNqPolqTuKR+B4rH4DYifjUdKK1ECI9WMme3OTEyu5MWikfd2rF17ktuuqKDSuQuzKA6niN7reKikE+TQ83nThL0JU0Hm9YREgos

8yC5Oo9L088NxhTXouFKGjmZSWnQAhEBMEIC2QKlG4LBsrGhorh4FCmIiNw+EKdqNfSlIBLmI8hozKaKDisGDFCuhpvDz0iBG0RBKI6PwKlCGX2QpowR0vp9eiqetdKp

Kz31WDaIHcF+o0AmtRFpmIHepbNXGgWnP8nlTxpgbea/wv5rCE9+vKyQirVLvtEvH8rMjoigBo2SWsXxpf8PGtiyCbzMhuUtrMihWklKa7SMMjKcG3J1dTweC5PrqRCg

xxf1xC5/Qf0ECoLMobBvY0v0bTS+hrkyg4sOpLLjo/TyjBkwQgsoCJ68SurLp6xxveqHo9dihSaCiJzoKGCqWvMzKFT4JCZf7bAFK9MU9Mi2018OdOyZ5G3oE0QISeis

gLODP5xIbEYnoKOqlsg9KNK0C7ioMaLqgvW5QkCDpvMbBWMh081J8gZvsbXqtbzkiRUxAFKB6AI/LCqYAGZA3Ny5KsDEBnlP6C3iIq9sEsBQlYKuBpdves0VBFQKsBha

eqwyr6r+aFs1+b/mjqsBaOzEFrBaGwVCogqTKlFtha9KlGgRayQJFp+hUWyyoxa4aYJpfqAi18qCKImgqq/rRamJpKqJarOsayWsbFvarDKoFuDkCW8FuJaoWsltar4W

4oERa3Cult6qPrRlvMyQNSWmBro4EOCR9D9XJozd6QRTH8i2UNyTzhSm1RvKbW4GpqqaKmi1q0a6msKU7qMY7urOroXMBJV0LSq3z+SYs1AnSZkyAT0rK3m4FIca3qr5

oMyqCozJeiefP0sAZRwqzUlpPQW6DCBQQXUHkAsgCqnLzLxdkSFlowQQueZoRd1LKaVSzI0taAs2pp9rlsv3Mxirm5psMao0pTBBI0uB5rDo5vGOqcd+m56okqaHT5tp

irE3SUIgcgXUBHwqwQiDZBy0GZG+lluZeqeUyQdsxSKWzClF7b+2wduHbPQUdrAbJ28sxnbD7KaD5qlc2BQvshanGX+zb8zXPFq9UjxQaz/ROdr7aB2odpHaiLVdpxgp

29c0wrxq+bTVblasABDgHQ7VowajYkGMfEQeIY2aCxoCAvzbsiauHh4HYlMoLZwOnIm9rItd0PtbKc1T0Dqq2i6sYa4XGhU9ag+c0BjyTQMSrbbBmwNs7bLEygsejUDf

htoLYUyNtaymdajNKBuEEwBoBwwYcBkbMxJ+BAK/EU0FCBNq4KJQxmvUDuKIvAXi2Eyi2knJtbS285s7zLmlDvOrZ/Ixt6AmQbDxOi+ABCkhJKQgorjqMXLnKGag2rtu

VIV3UoCeAty3wDRoGwRbicLH3Qzq4BjOscrM7pTQ+zO9bDErNZa8q9ls/qrgrlvlCeWvVLvdjiwBoM6jOzwFs7Hwezp2THdajPVaP2xTutrYEIEg88UWKgxmiQO01pVL

a4BUBgBxSo5qtwPYBUHFLxO+Do/0/auoqpymm2TpdaGG0OvdbkWCOtLKg9ZOH6d8OhPPbbU03nLMKQ3UNozzw230r87zMvjMloKAc4DAghECgGFQepLFKq9xoBRHpBST

Wg2hDskgTrX4XIs0BE6jm4tqBL26pRKK6u6krsrayu/iKJCdPJkAebEcUQOfgU4IRkZBGukd2a7PwtNLa7u2nmjXzKLPv1sTsa7mnqq7BXSDAVHy+TW3bPs3drFjzgyJ

sPbtUn+tibVknXPKq9cxAEe6PBZ7q+7wkqNrtDQWSLsmwAC2RqjADWjauHklS9XzNa0u3LtgKcujLrg6pdXRq2inWtDzk7Wm8ngw78mlhqOpy3d+WFR8mzTtd9SC2sp4

a2fVOrDaBGiNp66dk8I2oyr2MsBs1+AKADeCkkqXzzIhGA1oGA0QWWjvSgoibJUblSq5KW7pgFbqg7EHFvNOaZCstvkKK2mTudb9u8BLp6rS6nhjTw46yHUR4wfJKu7a

Qwjo+a4wt9PMLEAHcBb0mALCvoAPYEluvqAAH2e6lCV7sPrMgD3ueUyQWct96IqqsED75LYPscSMqrwOZbQm3KsACr8g9pvzQe7loCSsFN6Oh6QAcPq96o+oyuQRY+oP

rCBP5IaPeNhevkkUg5eMCBl402uLsS7WMiIC/5P2OgVzadq9XuE6W6zRv9SKG9vKzKLm06tK6Te1KL4qu3CIiw6hoVkUUyI0ThukjOe90q98NkDuI36/iTmMyAN+juL+

IgIrdv8LnOgWvCb92twxB7omrztz6XGM9oF7/RXfr+Iho602oyR8bhHiTCIS4CiYgQh8VLrkxFFjXx6gwZi2qGabvoIahO5bv76d09MttaO6rbodadu43qp7yumtroyi

HTlLgRVyCaHiNW2prqd6O2l3r5zu24GqXzLBZMirBFACgaVr9wJwGYgmgFs2IGaBqsDIGKBj6AYHLBOgc3aGondoAC921Pw5aPOo9uKrr+1xz5b/RNgeYhmBygfEGqwD

gZ2SjzCLvfa/krVq8iQfZWmczR8oWWQoxZR2rV7GyYnsy7teluAJ6SektoK7kCkfqk6x+3bon69o512wL3WxnLkNRAnXhskMmP1oI73m/AbujXe9rrI7xm9OqzzM6/Pu

HDmC1K366KAQzt+E2gVAAcypexHHUGPzHnR5R1EGEN47oHMAY16te/ap17WKvI2OryexpusGkB03qn7DujQsUEre/AskpeSeMHqE2epBMTqMS1fucavpWSFKAWIEGDQq

yakgdoGKvbfsQBtgNoY6GDgZiGkHaFQ+xcSE/bgdFj+HX7Mz7PywQbB7vO4mUh6Zm/lspkhh5sE6HRh7ocYHxhnZMLtJaSQE4AywWSApRVARbSb7HM1lB/7Iy3kg46TU

AAe0L0WCbNAGGKs1vAHNeyAd168hs5pOqaG32L27J++TuMhkyQfJTNr0hkHJDowRfpwHruvAZa6UsrEtusxh1ZhYGqBnoarAvjCzpaxUR8gakHdhywWxHfC7qC4H/ung

cB65h8/qz7L+mWPB6oi2/oSb1hzIDxH0R6QeJGhoz+2oy+EfgGQAviKuBERm+u4cFJZukWWfYd8V4YV8e+wTsyHvh3IZBd2KxDs4q7XN7SBHbBs3ocGlO0QPZEGeMaBB

C4Rx3s8HERwYrnr1+jfpbNd+wc0P7mW4/rCa2Ws/rPcRaxYZz7as0keCGAKnfvNHzMxRwUHDkP5JWbI4HVuzJZGgfK2bDWsWRNbdBgtn0Gie9Lry7B+7Rrta4BpDq4rE

B0BJKGKu+wen61CpwZEjoKd+GgQzpeodMTGhmeqcbZrPwa9LM8qZr5ahouJ2oz5AeQHkgpIIRBYBuEYuuuG+PSMowkUWHZrm9X4MRJQYMhvvo0aoBvXszLfcw3sdbx+4

oeBGUB1otzHNC4VBSSsudwdwGjR27ta758/nMQBuEFvXcA1gY5WBaFRQPqaAQ+nkN3H9x+0F1Vjx8vrPHE+tHXMi/unKrVTBavgfc72o50av7XRmhPPadJPcdzVDx/Fp

PGZBlgCr6ke5gDVagwHEHkANATyNWbXTM/QTTM2o1pQhxZBbp35ZR0cZ+GFR/IaVG9GoofTG5xy6tBHYSioaErKBZ+GQo9C/1v5SvBu7u3Hu2ilDL73wHFuFbpWylrZh

+h3SRYm/moVq4hGqiluRpBzb/xCbph2ZPfL5hp0ez7vxxUOgC/xtfWYmC0PqrYmBJjieEnzMxV0lo5eEJkwE9KXUHgnQKKryb9pusENIFEjeXrGyPM8RPeHdqpisMGJC

k5t+H9eyTtQKrBtMdwdkBkieEYLe6TEqGR2ZCgjphGJfv6Kk65ofkjKUH3uOV5AVwr7isUeZEsAWY3GGeysKy6xAqJRHqHJDBgWdqimmwWKftB4pvZESnKkZKeDQ1mfF

HSnnPUgCyn0qx8eAixJ8kZmHJQ9OTaiyEzzrpHlhwJPdH/O8iVymYp3ADinlLIqaSm7cMqfyEKp9sAynqp/DwQbmC2N2ozYwShDl5IgOzG4KTJqRHqEUNRI0hiQo2yYC

17J7IZYrDq5yYnHDSywYBHVRmwc0SC9YRiLKTu26q/51M2zgNHnSm7pKitx5Efeozx7CAEsfAKqfJDVmKMS0tfwGQdWYSLFlWpafoOZH5QD6i8ZABvp38F+nmITKffhd

mYGcj7oKS+h8tIZ5SxhmFchqZfHlc1zodH0/Nqa/GOp4QcQiFJtFARmpQA1X+nUZoGaegQZzGfBmfoHGehmIgcarfc32v0eTID9FQaDHu5SvL6QhZAorhDdHFLuyJzgV

ABdqnirLuEVSe8xwKHpO2htQ7qersXkz2nUOBANFBQfP5ZuUs6JxwaJjwYDbne7wcIHSOsZrzpkw9OMyy0wla0cU1rIehzjPyGEnzjCwjuhLD/FMsMNZy4sykC6TOv5p

C6yDC6zrirrZu3Qh3qB/tqAl6aQeTIZkQeOoAxRFAA7CHQDsEJAucMUT3pian6EMNo/LADFExlVxAABCOOcJGJBlgETmsAIeJTn2wtXGRaKuHACzmc55Fvzmg/QueLnf

QMuanbqB0gciBq5kEGTnU5huZ+gm53QAgBs5hIFzmXrDucwAi57gFLny5vuYkG2gQedrmR5zsIznm5yedbm853ejnmF58ZUSAe5+ObCB154efrmt58eZbnp5tuYPn96T

ucXnu55ecxHYEC+fwA65tOcbnM53ebvn95pFsfn55ruZPnX5xgc80P5r+dHnt5ieannGAGefbmgFo+aXne5t+f6BIFzefTmb5v+fgX75wBbetgF5+dAXUF8BfOAMFq+a

wXf5uBYQWH5gheQWX5khcsFGQche/mx5qhb3nZ5pBZAWwAU+YrnnPPIBYXoF7BeoW8FgucIXj5nhbAWmFqubBga5y+dYWYF2+dwWAFsRfoXiF6QfEpBF6+fYX/5zhboX

uF3hZXnnPNedkWh5z+cwWf5neZEWVFw+YMWpF5GfPnTFjeYoXLF2BY4XEF/RaIXJFxheRmEwLRcoWrF9xdoWD6NRe8WNF8MH8XXFpRZoX8FkJbsWfF5z3QWnF+RaEWdF

5Rb0W4lrxcMXMR3HEiW2FwJd0WPFzJYkXslxgesg8lxRZwWYl1RfiXpBnHAqXhFoJdiWn5kpfsXZkGRaTnzFlxfyW3FwpeCWWllBbqWB55Ja6WFFxpb6Xml8RcGW+Fnb

AaW0l6pdsWsltpfCA5lgpfSWilgZYYW6lvxZGWoF7RbWWFlrhaWWElhnlWXel9Zf6WplrZZmWklzpb2WAl85cOXPF1pZOWyF3ZYsWel6JdEXFll5bGHpgM5a+WbFo5d+

W+F8aABWql75eBXploxaaBwV6xYyXNl4hctHpmnAyR7WPajLABPQCgBYBCIVADCA1ecvJtqo4lFjyd1EaurNChxvaZlGRx0TtbqExmAc26LBtyYumRvTyYzGUB1LjxNn

BkaF0hzQQgWLGio0seGbg2j6p3BvubibFX8ZlPvEn1UtzqknOW8meWTf6rqbhT/RSVfMzCvajIpQpIDFFwA2gBEBA1CI80F/7IE2g3BI/3HjomzpRmbP+LaVgfqqLEx2

AaZWwSo3rVm1R66ekMlMcOsEp/J1AgZ4hUMjn6QBV7TqI6CB+7v07tmaqaEZzx0P0yno1h8aRlJh0UMamJJj+vlWBBmSYpmfxtZOpnGHJCkr7Ee1rP+8X+rCNF8IAARG

UGEJ4yazM2iOflm72+3XWhGVfZRuhiS3RbppXVusTvpWJO/4ddXARq6dkzvJ0OHBGI8/ArjAhGFwaTSXpuxrNn6Jj6Zkr3qdVelSkm77iVShY7HVfHT+98fTXPxzNaVX

6Rh/NEGdJJdaGiBfBsfOBdQOXjZBboTAAbly8gotrWHhqYHb7Q9ElJzapR4cYgHsJ+UdpS/hlWfcm3VgdehL6cr1a1HfksaC81YENcfhGNx96aRGF1s0b37wMbiZjmYG

A/rJHCZgHtmGWp0hLCLM/Y9uVX7CRkbctYilrFQ22YIaIr9qM3UDAhJASQFPAYGOIfhYH1huLlKRs6EWAH31vNqlnqVr9btWxxk6Z0b8JinpnGiJ9UdKGFOkxvImRI9T

K+4mg4NZeq51+DdNHcRiufbAyBxKdkHuJ8QfU2TRTTYdD0Ns/I+zMNikew3BHXDdQVwA/dc6miNo9bX0dNpgb03QJ8apwCX+lnDl5PMLIF1D71vSFAI5u0UaiAVsCUcm

k3h/Zv8ksJ/jZwnf1lyd7XpxwibZXiJm6dDhju0db4YLgMaG11oNw0dnXjRuspU3aIS0ZxGCtr0ZJGGcjDfcSsN5qfM3QiyzZuDrNymbK3upxJuK2O48avyDfRjVuS2A

C+LruHXMk0PFmXxSWajHkeGWblnYCl2Py6ye4TcKGPJgkPZXNZtpvdbpowStuqykCOhp8st16YRHNx5Te5708tOMQAlrR2czDnZi61dmo2ZBg9nC4xAG9nl4v2fbBQlK

zoUAgu0zpDmawpZHrjmNqOcQ2boNpego4VppZqXjlsYZMW7lj5cqX4VjZauX1F0FccWwd7pYh3Adn5ehXMR+RAB2JloHZBWYViJfeWEd8ZYuXJl0JdKX2B25bkXRl1JY

OXIV55ZR29ht5fh2xl+Zap3ilmnaJH/l3HYZ3KdoFep3rloxYQp0dgncx2Wd5iBjB+dp5eZ2GF3ftbjrx5FXvonlFQHGV9lieb3imtnZI+CtVt+BgAsgEfFUA5w8bpvM

74k1evEjIMaDjKX4sHl2mwtsXQi3O1ulYdWGVoNMnHqGvtcunZx8TZBGvV3yaHyhKthvLd5EGxvJj46nLZ22TRtfqSawJ0yivNl1lxvD2qwSPdwTnxirdM2qt7xIv7RH

LNbknfxu/uPWY9yPaGjdQtVvkhZIKDR0Ao5Tsac0kmNolNX1aEIHSZCnK1YIa9q/cIOqnJ3Cb/Xpt1Wf7XXdj1cqMvVu6dc4RItQTNAnOf3ZMTBVnTuI6fB7tvLcC1my

Kj3Mgafe+6k+p8YJnE9pqZ+ycNmrfCK/E+/JWG7NtFAX3C1kcMZBQWNzBoAcgVQEYBCIN+yY3o6JjOTAn1rGl5RG15ezfWUMVXrx6VSz4ayGm9nIeOnW9mLf/WWV6fwS

23dlAY/MGe7d1l61McdhCn0SssZGadxwvo5ilyjZB3ADNn7sODpVlNdlWSZ1qbw2jIgjYPXKdPfdQOHQtCJTJQWPIBHxOAAREwFVATAVStb4jp0fWAO3lFfXJR7jeG2+

ha3YcntfH9bYC295MeVGeAl3bE3u9kDc2rZ+9jTuq18GuoU23phOJD2WhxAHI2LRzfvAxDNxXOwO3x8WJ3WyZvdZqyM9q2NVWdJVQ9sjPPSWgEQ4k+QH4AhEbhHKAmDy

vOykUWCEM42UMULYwnuDjtd4PjmjEME3h+x3dH6gDkBJAPxD112fhw831dEpyQnXkM9vk+Q+224NpQ4inAmNTdBmUWrEeQPXKlkbSPMZxKeJHNDo/plWdDoHv4Hd12kf

q3s14jafyPR1I5Xn2wPI8yO8K//MlpigW6Dl48gSQAMoY2Rw9Lr/NmvMC28rV/cVgPDnjfbW+Nm3ftXoBntcAPnd1lbm3Etz1efgR15Tt6BVMLHAjDXm02bonctrnuUO

QAQrbn2VDkrcKObR4o63XdD6kYWGDDnfaSFqjqHtI2Wt5o8/RJaQiDLBdQDQDABbobYEl69duFlv2+jzV320IgSElv3xsyaRCBrVyRNtXJjgTf/3TpqhqCO5j4A4WPQD

odbUUID7JkpCccXkhNn1xoPaSO8t0PdohTKduSPzdzH6ZbNSTjJV7NKTw+2WAE9jdaJn0+ySauPpJio8MPfy7bJMO19ak/JOGzOk61ilCFHsUHn4AMcqEf279wBPux9h

QA9UJ1gEjGP97IhjHbk4wfjG7dn2ti2EBwDa73B19DvdaQdGrut6XPXHGqQHerbdg3FDok+o8OuijsmaqOgXvIPj479BABwwX4OvpwwOXgJWy9qRF50/NvpoapyQmERh

G69+brGPMJ7w8OnHJvw/hOhNoQ4InZtiNI1mkth3MxPl4SEjURFUEfdRLLTnnN239jgCYPGbx0VrTcjj1rCvGgJ48alWsql8pP77R7dbZOFVm48iLtckg5axCz6XeAnm

jphJdOGAaYEwEdwClBnw1pu8z5RhszOGqRQgAsctW9mzw/C3Izn/aOmW96LYROGmjvdEPQjwdaS3dsetrjSMc2n1gOhV3TpI6GytA6coyT2k8RmnKPcYlFLEE0VMoY9s

8dvOg9WGdD8zzvk8vO6ZiPcok7zpykfOwJ5865nQvIzZZa6z4mYbPHRps45PbjvPp5O0Ud89+gaTik6vPvz28/Gg/zpyifOqwafdmnrihNklpMAD4nQAywVQDayRzyvI

Z4DWspDycx8oPWsnKVy3aTKDpxc+jOaUgQ4AP29gDc72xDrc6WPXwtLiiOthbKO4xx6hI9zPuG8Ke+bC++89mQnKM84lF5LQZhmRWJ/ibirWweQF/BXz2/zFWML0ynkv

nupS5UnVLjFvUvNL6s6mHtDi49KOPx/Q+guWz3fZV21VmS5j39LxS6SWVLgFpMu1ADS7JBcLxAHkBccRuTaBQQbYDZAwIFgH8Zy80c9nT5+D9lCAyOCDfr2qVm1cYDv1

v/ZXO4z51f9rkTkI9ROwj7WZjA0ByEYfF+Z2DCnWxLgk6tO9jlI7ogT6h87kuTRBS+xQlCGZFsLLAJgAUqoAYms4kCAakFgBcATi28VAJ9dCMsit/BRAbdLqsB0umr5M

kcW2rjq6PHur5iF6u29RUEGu9rYa9/BRr0rfqmsDkzbX2M+xs4zW7LoHKiLVhmnX9Ff5QhVku9Lxq+UsWr9wtWN2r9yo7Alri53WBVrga7nAp4g8ZGu/LjCDyAEUl04o

ATzHcBHxfhfs7WnMxV+DDH5EEWVlpwTmaKhODmmWVhOot9i9XPAE9c/mOkzryYL1ltoeucGZiUh0er48mDcqu8z5I6kvklVJRxhmbZ5TRrqAe+s30O9fZTXiKlOvyeUZ

lGoEHBg0RpXdgWlFsxpuBYAJoJsclJm4KU29LfTZuhyjm6qUq5AWB5v6lGAH5vmlHmvpPytpk8q3196raia09yo6MOkMXNZaxhb1mrpuxbxm/wBmbqW9ZuawWW9YhObn

GG5u6lPm8YAmlVGv+uAry1OoyQmMIApQ2gHcHEbAYpjdkaEKNjYnOeUaiPcOP15K/KdUbnw7W7JtrEM4vgj9ROUL+6tLQJu9qMxoNn4wcpAh5Dz8fbDXGJiNYRgSzgpU

vKmq5FvkBop7rnTBmZqUBbNS5WiQruvG/yvTma7jssMBr6wU9OOaz1+sCLwLy48gvjr/W85O4mo26z219Zu/lFW7twXSCfoTu63Lu7hu/yzyDsdOoyIABEEYAEwARDfg

xuqtcb87zJEqFlTCvHIb3mLn1L4P0rjG8yvAj86Zyu074OoEjKjIRn1GfV/TxJMEWYPnNOZ1nY+D3rTmq9uglr9sC2GRhtFtcBQGxUUnAHC2cBScwAGMTLPgHlsFnAwH

y8urlH5aB4bBYH9sHgfEH+PZX2tbpPZ1uU9mkbHuYLp+0cudJZB84Jhh9B/DlMHmB5SLcH+0EQfyDqjJdPluLiBDhvub9rTFDQlvpqCjISvRmjYfJU8E7eAauG+4sulB

6kelZ7HxTvH7t5Ofu7Bt1rag378PNWPlEE6hUxYMPE/Jv/7wk+qvgnSsZvJalfAHiBzAF6Boe1IWwve2Jpg/BRXo3Q+LyBgGajOmAHrTATLAywEfFQEor3zakQ619Wl1

4o79IdjufMmE4Tuu1jU7MHZCtc64uNzvK94vX7qYiKvds/p0EYscbtwqvDHqq8kuBkq69C7uJwp9DmCHva9X3U1uVaOvyj8h/suVV429ogSn5o/azc6gIG4eaFAAqhDB

HlFizMgPAht4zrEM4FgLeAZsAM3u12J61PkOnU54vg8tR8dA37sDc5TVyXSBTITQTbb/uU0gB+MeQ20x/SBEgagEseDAGoBsew+77nGm6wrRSEYnHmJyja8gWHOoz8AS

IFUBigOXjLAiAWIb+Obhnc+m6gnrlFJXyVilYZpkb+c4mOon23emPYng3qd24txM5kzgNnsTfvKhhAE93unKvIYNtEHJ82ejH/J9FXxVlA5XXzL5Nf2vKn3A4s2t9u/L

qfJHKh7X0T1257NzWn7sBDhsmwMclO4WHle6fZu3p6X4xHtoOyIRnoZ9VP+XsZ5iept+M5E34tpJ9metZpPDfuUtrR8qQ18W0tlotj/E9yfKbwB5MfrZsx/2eLHxUCOe

YAE5/d6HQ858+27z656uL/LvIHzzqMzASIATQEfH6BdJ7gvaS4u356mp/n8lbDOuDkF6+G0r5c9vuAjs6eZWlH8LL7qX7+nLfuzG5F7jSHxLPEM9C70NYtnw1086yO3u

o18JeVU4l5wOIL0mfwPv6l0aMPzr/UzVWyD259/yGX9p/oz0G/h5s4fXGXoDO/nwF/cl+noV+GfBn4V4hfRXrK+K6pn7i83OpXxbfUelMT3YI5SyxTBTIEKO6WnXA9tV

4kvZ6vbY67zHw5+selrzIEj2TXq6yaBzXoUste3uajMV5UASQG9B+gTBKY2VmM/TIdteU3fjLz78J59fv9q+98O2L1iMEPu37bt7fEn3G/m2C9N+773BLvgGMKEKWb2z

PJ6im7nfyxqS8j3uJuPYwPdr/u9Au7Roe+su9DvN/amDbrk6Le0vNfVz3bn9IuoycgeXlKA2QEfB3u1pvrbaIszAeRTJs2vOFx7eX3jd9fIt/g5feOLsV5m3pn/t77yI

3voF1m9qBttQJw0DAg4bp3rTsU3djnF7d6QAGx4rknPelsjkm7kB57M5P2uUPtRJ8p6IeDr1k5HuanqzfHvVkpcyZH/RaT6U/FWlT6FPbizh7afbQujJtTQfarp+fy65

eCbfLIOj/JTxjxj7RvmPt2NY+33+AY/ecbuF64+EXgVCkOpgRCjviMXp6tVesXvJ/nfujBkzaQiXFkyOg6uMkrpclixl3WLMMtlwZKWoLlzZL1jVkuwzW06GH2LDi/Yj

hS+Sh4wFLk0C14BvRSit+s+KDs8ReKbh6RAYw2iCSNm7wSFIwVK73q3YXPH3xO/GfgLWY5heOPyV6C+0tC7s0ebSnbGTIJA3+5neYv9V+2f30hL5SAkvvowTB6uSwFZN

koHb4GM9vnr5Ml+gQU2gzhTBYrFMq0zL9y+gIDYzu/MQJkuK/m0gr8Fcyvrkoq+Gsqr5ldHucjPeiR0vIADLLPxl+C9bP1lGHEOv4qC6/AzvMPQo+vxi4rgeDqM+vv/X

lj8xuVshJ4C/acjO5lfenUL6TgEblTB2EE382YYnkRnEsS+xi2YEO+UgS4Cot6uen6xxzv68BgzySxYoQzGSlYtpKOXOUAe+ef5YtW4Xvwr75c3vttI+/RXL74F6fv84

r+/BSgH7wuCKxr7+SKvSdJiM4WOJjvFf+mH9fZ5T3Is/WPPsF6mPxxu+6DeXV8b77fJvgsoQILuxZ8hHdhTAiUN9H7LdneV+uL/xcP0qn+GMaf3b9czafywFczmftL4p

KMv6kqy++fnL4F+0M4X52Kxf0r45Lyv7Skq/JXPtOq+Li2r53eAbyaoDBClcEBCN7+f2TUgQwU5XnRuailB8OBMnjJE7uFtkBqBVAcEAJzTgJv/twa/uv/L+Ufp98/Av

F2v8ARXGmJ9b/AEBv9H8llekANM9XzgFL2B/+v/7hINUr40uQq0f6/BluHEin+h/s34NQp/rukwcpoKf74QUPKf8hZmW9CAP+MDvDin+aIN+tX/8vmP/SQp/z0CK/jjH

DPe/J+Kf6VNSgFQY9Au/iRZ7/VAHcG3gu6SEDZIdUh7ATAAgaTIjAAkEBWaSJAaAP5oByG8j96WCBLABXxnwTf538HogxAR4B4ATGh7wTAG4AdPj84dCC4AoRA+9GAD3

/YuyeAXAi4A4jCgAClBrKX7iSAW4CAyOfizIVxjtLFMBMDdECIPCCDHDAyr0AxgE44NgDtLDoCzIGCgcAsIDqiFAFeLNf4wAPf680VLSuoCCC8QaGDymUAB1KYzqOgEr

CoAHAB0FcgCDgeIADaLgBgAAMglYAyinKagC6gGqADaUwFbAfABkA9QGRuEwC/CNXA0AUECDgKADEAj2B2AigH7EIlTYtAfQLbDKB2gGwRd/RvDv/MRB6dLeBqAT6ieA

YIHaUbrirAHzwRqPwGnQM+DmABcDGdXYD7PU8BCIBIAVUMRjMuIXI3Zf4CF0NQHeA2pDsuLwFtQErDWgY0yZpVwGFKKbiVAjQFKcd0DIAaIH1VDwFqQYwh/qTuA9gE4h

CQISBAAA
```
%%
