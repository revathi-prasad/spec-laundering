# What SpecLaunder solves — a diagrammatic breakdown

## 1. What a "VERIFIED" stamp actually means (and the gap)

```mermaid
flowchart LR
  I[intent<br/>human] --> P[spec φ<br/>the promise]
  P --> S[code S<br/>the impl]
  S --> PR[proof P]
  PR --> V{verifier}
  V -->|VERIFIED| C[consumer<br/>trusts & ships]
```

The verifier certifies **"S satisfies φ"** — *not* **"φ captures intent."** When
one agent (an LLM vericoding pipeline) authors **both** φ and S, it can move the
goalposts: weaken φ so a wrong S still satisfies it. The stamp stays real; the
code is wrong.

## 2. Honest vs laundered (the core problem)

```mermaid
flowchart TB
  subgraph H[Honest]
    direction TB
    I1[intent: return max] --> F1["φ_strong:<br/>r>=a, r>=b, r==a or r==b"] --> S1[code: max] --> V1{verifier} -->|verified| OK[correct ✓]
  end
  subgraph L[Laundered]
    direction TB
    I2[intent: return max] --> F2["φ_weak:<br/>r>=a, r>=b  (equality dropped)"] --> S2["code: max+1<br/>(backdoor)"] --> V2{verifier} -->|verified| BAD[VERIFIED but WRONG ✗]
  end
```

Same intent, same green "verified" — but the laundered branch ships wrong code.
**Our detection target is that red box: verified-but-wrong** (not the author's
intent, which the artifact can't reveal).

## 3. Where the lie can hide (three families)

```mermaid
flowchart TB
  W[a verified pair that is actually WRONG] --> A["A. spec weakened<br/>φ made weaker; code exploits the gap"]
  W --> B["B. proof bypassed<br/>φ unchanged; an assume fakes the proof"]
  W --> Cc["C. spec incomplete<br/>φ never captured the property"]
  A --> Ad["coupling  (V ⊆ D)"]
  B --> Bd["axiom_scan / coupling V_semantic"]
  Cc --> Cd["trivial_sat (partial) — coupling's blind spot"]
```

## 4. The coupling check (the mechanism)

```mermaid
flowchart TB
  R["φ_strong = reference (what SHOULD be true)"] --> D["D = clauses φ_weak DROPPED"]
  Code["S = code that runs"] --> Vv["V = clauses S VIOLATES"]
  D --> Q{compare V to D}
  Vv --> Q
  Q -->|V empty| H["honest (S meets the real spec)"]
  Q -->|"V ⊆ D, V≠∅"| SL["spec_laundering<br/>code breaks exactly what was dropped"]
  Q -->|"V ⊄ D"| PL["proof_laundering<br/>broke a kept clause yet verified = unsound proof"]
```

Counterfactual reading: *if we restored the dropped clauses, would S fail?* If
yes, the dropping is the **but-for cause** of the false "verified."

## 5. How it is evaluated (the data-science pipeline)

```mermaid
flowchart TB
  PB[problem bank<br/>spec + reference impl] --> G[generate:<br/>weak specs × candidate impls]
  G --> VF{Dafny: passes its own spec?}
  VF -->|no| X[discard]
  VF -->|yes| POP[verified pairs = the population]
  POP --> LAB["LABEL = ground truth<br/>differential test vs reference"]
  POP --> DET["DETECT = the models<br/>coupling / mutation / LLM-judge"]
  LAB --> CM[confusion matrix]
  DET --> CM
  CM --> RES["coupling 1.00 · LLM-judge 0.93 · mutation 0.56"]
```

Labels come from an **independent oracle** (differential testing), never the
detector — so the evaluation is non-circular. Family C is the region where the
reference spec is itself incomplete: the oracle's blind spot, and coupling's.
