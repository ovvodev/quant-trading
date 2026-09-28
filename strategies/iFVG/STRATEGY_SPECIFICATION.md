# Strategy Specification: Inverse Fair Value Gap (iFVG) & Predistribution Inversion (PDI)

## 1. Strategy Overview

- **Strategy Name**: Inverse Fair Value Gap (iFVG) / Predistribution Inversion (PDI) Strategy
- **Original Source Files**:
  - `strategies/iFVG/ifvg pro.txt` — "IFVG Pro v8" (KAIROS), Pine Script v6 Indicator (930 lines)
  - `strategies/iFVG/IFVG Model.pdf` — "PDI = Predistribution Inversion" Strategy Guide (9 pages)
  - `strategies/iFVG/iFVG_Ultimate_PDI_Refined.pine` — "iFVG Ultimate (PDI Refined)", Pine Script v6 Indicator (1052 lines)
  - `strategies/iFVG/iFVG_Ultimate.pine` — "iFVG Ultimate", Pine Script v6 Indicator (971 lines)
  - `strategies/iFVG/Indicator iFVG.md` — "ICT IFVG PRO+ Indicator / IFVG Ultimate Toolkit PRO by Yahya", Reference Documentation (95 lines)
  - `strategies/iFVG/Golden_ifvg.txt` — "FVG fill with immediate rebalance [LuciTech] / Golden Arrow", Pine Script v5 Indicator (142 lines) — *Note: Regular FVG bounce, not an inversion strategy*
- **Strategy Category**: Institutional Market Structure / Imbalance Inversion & Accumulation-Manipulation-Distribution (AMD) Reversal
- **Core Idea**: 
  A standard Fair Value Gap (FVG) represents an unfilled price inefficiency created across 3 candles. When price fails to respect an FVG and instead closes forcefully through it, the inefficiency flips polarity from support to resistance (or vice versa), becoming an **Inverse Fair Value Gap (iFVG)**. 
  In the specialized **Predistribution Inversion (PDI)** model from `IFVG Model.pdf`, this inversion occurs following a liquidity sweep/manipulation outside an accumulation range, targeting the opposing boundary of the accumulation range.
- **Intended Market Conditions**: Liquid intraday futures markets (e.g. MNQ / NQ) displaying distinct session structure (Asia, London, New York) and clear sweep-and-reverse dynamics.

---

## 2. Source Material Inventory

The folder `strategies/iFVG/` contains 26 files in total:

| # | Filename | Type | Size | Source Content Summary |
|---|---|---|---|---|
| 1 | `Golden_ifvg.txt` | Pine Script v5 | 8.5 KB | Tests immediate rebalance / bounce within a regular FVG (LuciTech Golden Arrow); not an inversion model. |
| 2 | `IFVG Model.pdf` | PDF Document | 1.7 MB | 9-page guide explaining ICT AMD (Accumulation, Manipulation, Distribution) and the PDI (Predistribution Inversion) setup rules, S-Tier criteria, invalidation rules, and 15m HTF alignment. |
| 3 | `Indicator iFVG.md` | Markdown Notes | 6.7 KB | Feature guide for "ICT IFVG PRO+ Indicator" / "IFVG Ultimate Toolkit PRO by Yahya" (HTF FVGs, PO3 overlay, session killzones, SMT divergence, EQL/EQH scanner, checklist). |
| 4 | `ifvg pro.txt` | Pine Script v6 | 47.6 KB | "IFVG Pro v8" by KAIROS. Implements candle-3 FVG inversion over prior opposing FVG, session sweep gate, A+ setup classification, initial candle-1 stop, swing stop, and session target levels. |
| 5 | `iFVG_Ultimate.pine` | Pine Script v6 | 61.3 KB | "iFVG Ultimate" multi-module indicator. Translates the PDI / AMD framework into Pine Script v6 with dynamic accumulation boxes, manipulation extreme stops, accumulation target levels, and HTF overlays. |
| 6 | `iFVG_Ultimate_PDI_Refined.pine` | Pine Script v6 | 65.9 KB | Enhanced version of `iFVG_Ultimate.pine`. Implements an explicit state machine tracking accumulation tightness, manipulation leg FVGs (max 1 FVG), close-through inversion confirmation, Rule 1 (R:R), Rule 3 (EQH/EQL), and Rule 4 (opposing 15m FVG). |
| 7 | `IMG_2293.png` | PNG Image | 121 KB | Chart screenshot showing a bullish Inversion Fair Value Gap (`+iFVG`) formed after a downward imbalance is flipped upward. |
| 8 | `IMG_2295.png` | PNG Image | 91 KB | Chart screenshot showing a bearish Inversion Fair Value Gap (`-iFVG`) triggered after sweeping London Session High. |
| 9 | `IMG_3287.png` | PNG Image | 845 KB | Mobile UI screenshot showing real-time multi-timeframe liquidity dashboard (1m, 2m, 3m, 4m BSL/SSL status and EQH). |
| 10 | `IMG_3313.png` | PNG Image | 384 KB | Chart screenshot displaying Buy Side Liquidity (BSL) and Sell Side Liquidity (SSL) swing tags and price reactions. |
| 11 | `IMG_3315.png` | PNG Image | 720 KB | Chart screenshot illustrating institutional liquidity sweeps at BSL/SSL shelves with resulting directional displacement. |
| 12 | `IMG_3319.png` | PNG Image | 658 KB | Mobile UI screenshot of the "Auto IFVG Checklist" dashboard table (Delivery, Liquidity, Momentum, Breakeven, Draw on Liquidity). |
| 13 | `IMG_9132.png` | PNG Image | 193 KB | Chart screenshot plotting session liquidity horizontal lines: Asia High/Low, London High/Low, NY High/Low, Day Open, PDL. |
| 14 | `IMG_9871.png` | PNG Image | 252 KB | Chart screenshot showing session markers (PDH, London High, Monday open) with multi-timeframe candle counters. |
| 15 | `IMG_9872.png` | PNG Image | 121 KB | UI screenshot of Higher Timeframe (HTF) status widget (5m, 15m, 1H, 4H remaining candle countdown and FVG/VI color indicators). |
| 16 | `IMG_9873.png` | PNG Image | 53 KB | UI screenshot of the HTF Information Table displaying Time, Swing, Expand, and Divergence status across 5m, 15m, 1H, 4H. |
| 17 | `IMG_9877.png` | PNG Image | 167 KB | Settings dialog screenshot for "IFVG Ultimate Toolkit PRO by Yahya" showing box levels, touch color changes, and palette controls. |
| 18 | `IMG_9878.png` | PNG Image | 46 KB | Settings dialog screenshot showing multi-timeframe dropdown selection list (1m through Weekly). |
| 19 | `IMG_9879.png` | PNG Image | 116 KB | Settings dialog screenshot showing HTF label styling, alignment, countdown display, and FVG vs Volume Imbalance toggles. |
| 20 | `IMG_9880.png` | PNG Image | 150 KB | Settings dialog screenshot for HTF FVG Overlays (configuring HTF 1 to 4: 5m, 15m, 1H, 4H). |
| 21 | `IMG_9882.png` | PNG Image | 176 KB | Settings dialog screenshot for Killzones (Asia 20:00–00:00, London 02:00–05:00, New York 09:30–11:00 in America/New_York). |
| 22 | `IMG_9883.png` | PNG Image | 204 KB | Settings dialog screenshot for Killzone Pivots (show pivots, alert broken pivots, extend until mitigated). |
| 23 | `IMG_9884.png` | PNG Image | 12 KB | Chart screenshot showing visual labels for Asia High and True Day Open reference levels. |
| 24 | `IMG_9885.png` | PNG Image | 146 KB | Settings dialog screenshot for Opening Price Timings (True Day Open 00:00, 06:00, 10:00, 14:00 NY time). |
| 25 | `IMG_9886.png` | PNG Image | 164 KB | Settings dialog screenshot for SMT Divergence asset pairs (SP500/SP5000, Gold/Silver GC1!/SI1!, BTC/ETH). |
| 26 | `IMG_9889.png` | PNG Image | 50 KB | Settings dialog screenshot for liquidity line formatting (line color for highs/lows, width, dashed style). |

---

## 3. Inputs & Parameters (from Code Sources)

The source material provides two distinct code implementations with explicit input parameters:

### A. Parameters from `ifvg pro.txt` (KAIROS IFVG Pro v8)

| Parameter Name | Pine Identifier | Default Value | Allowed Values / Range | Purpose | Direct Signal Impact? | Source Citation |
|---|---|---|---|---|---|---|
| Setup Sequence Lookback | `setupLookback` | `20` | `[5, 60]` | Lookback window to locate an opposing FVG to invert | **YES** | `ifvg pro.txt:37` |
| Box Projection (Bars) | `lookForward` | `5` | `[1, 50]` | Rightward visual projection of the iFVG box | No (Visual) | `ifvg pro.txt:38` |
| Liquidity Scan Range | `liqLookback` | `20` | `minval=5` | Bars scanned prior to setup to confirm a prior liquidity sweep | **YES** | `ifvg pro.txt:39` |
| Show A+ Setups Only | `showAplus` | `false` | Boolean | Gating requiring a session sweep within `setupLookback` | **YES** | `ifvg pro.txt:40` |
| Min Imbalance Size | `minImbalanceTicks` | `0` | `minval=0` (ticks) | Minimum gap height in ticks required to alert/signal (0 = off) | **YES (if > 0)** | `ifvg pro.txt:41` |
| Swing Lookback | `swingLookback` | `15` | `[2, 200]` | Lookback window for swing pivot stop calculation | **YES (for Stop)** | `ifvg pro.txt:44` |
| Swing Stop Buffer | `swingBufferTicks` | `0` | `minval=0` (ticks) | Buffer added beyond swing high/low in ticks | **YES (for Stop)** | `ifvg pro.txt:45` |
| Show A+ Initial + Swing Stops | `showStopPlacement` | `true` | Boolean | Toggles rendering of initial candle-1 stop and swing stop | No (Visual) | `ifvg pro.txt:46` |
| Show Structural Invalidation | `showInvalidation` | `true` | Boolean | Renders invalidation line when close breaches initial stop | No (Visual) | `ifvg pro.txt:47` |
| Asian Session Window | `sessAsiaIn` | `"1900-2359"` | Session string | Time window for Asia liquidity high/low capture | **YES (A+ filter)** | `ifvg pro.txt:62` |
| London Session Window | `sessLondonIn` | `"0200-0500"` | Session string | Time window for London liquidity high/low capture | **YES (A+ filter)** | `ifvg pro.txt:63` |
| New York Session Window | `sessNYIn` | `"0700-1000"` | Session string | Time window for NY liquidity high/low capture | **YES (A+ filter)** | `ifvg pro.txt:64` |

### B. Parameters from `iFVG_Ultimate_PDI_Refined.pine` (PDI Model)

| Parameter Name | Pine Identifier | Default Value | Allowed Values / Range | Purpose | Direct Signal Impact? | Source Citation |
|---|---|---|---|---|---|---|
| Setup Lookback | `i_ifvgLookback` | `20` | `[3, 60]` | Bars scanned backward for opposing FVG | **YES** | `iFVG_Ultimate_PDI_Refined.pine:19` |
| Trigger On | `i_sigTrigger` | `"Inversion Creation"` | `"Inversion Creation"`, `"Retest / Touch"`, `"Both"` | Determines whether signal triggers on inversion candle close or subsequent retest | **YES** | `iFVG_Ultimate_PDI_Refined.pine:39` |
| Filter: Killzones Only | `i_sigKzFilter` | `false` | Boolean | Gating allowing signals only inside enabled session windows | **YES** | `iFVG_Ultimate_PDI_Refined.pine:40` |
| Filter: HTF Bias Confluence | `i_sigHtfFilter` | `false` | Boolean | Gating requiring 15m/1H swing alignment | **YES** | `iFVG_Ultimate_PDI_Refined.pine:41` |
| Enable PDI Strategy Model | `i_pdiEnable` | `true` | Boolean | Enables AMD / PDI sequence gating from `IFVG Model.pdf` | **YES** | `iFVG_Ultimate_PDI_Refined.pine:48` |
| S-Tier Setups Only | `i_pdiOnlyStier` | `false` | Boolean | Gating requiring strict S-Tier criteria (manipulation sweep + R:R >= 1.5) | **YES** | `iFVG_Ultimate_PDI_Refined.pine:49` |
| Minimum R:R Ratio (Rule 1) | `i_pdiMinRR` | `1.2` | `minval=0.5`, step 0.1 | Rejects setups where inversion close is too far from manipulation extreme | **YES** | `iFVG_Ultimate_PDI_Refined.pine:50` |
| Block Opposing HTF FVG (Rule 4) | `i_pdiFilterHtf` | `true` | Boolean | Rejects Bearish PDI inside Bullish HTF FVG, and vice versa | **YES** | `iFVG_Ultimate_PDI_Refined.pine:51` |
| Accumulation Scan Length | `i_pdiAccLen` | `15` | `[5, 40]` | Lookback bars used to define accumulation range | **YES** | `iFVG_Ultimate_PDI_Refined.pine:54` |
| Max Accumulation Range (ATR) | `i_pdiAccAtrMax` | `2.5` | `minval=0.5`, step 0.1 | Rejects overly wide/volatile ranges prior to sweep | **YES** | `iFVG_Ultimate_PDI_Refined.pine:55` |
| Max Manipulation Leg Bars | `i_pdiManipBars` | `12` | `[3, 40]` | Maximum duration in bars for manipulation breakout before reset | **YES** | `iFVG_Ultimate_PDI_Refined.pine:56` |
| Min FVG Size (ATR) | `i_pdiMinGapAtr` | `0.05` | `minval=0.0`, step 0.01 | Minimum height of FVG created in manipulation leg | **YES** | `iFVG_Ultimate_PDI_Refined.pine:57` |
| Max Significant FVGs In Manipulation | `i_pdiMaxLegFvgs` | `1` | `[1, 5]` | Maximum allowed FVGs formed during manipulation leg (PDF requires 1) | **YES** | `iFVG_Ultimate_PDI_Refined.pine:58` |
| Block Trades Against EQH/EQL (Rule 3) | `i_pdiEqFilter` | `true` | Boolean | Rejects trades where Equal Highs/Lows sit between entry and target | **YES** | `iFVG_Ultimate_PDI_Refined.pine:59` |
| S-Tier: IFVG Near Manipulation Extreme | `i_pdiExtremePct` | `0.45` | `[0.1, 1.0]`, step 0.05 | Requires inversion close to occur within 45% of manipulation range | **YES (in S-Tier)** | `iFVG_Ultimate_PDI_Refined.pine:60` |
| S-Tier Requires EQH/EQL At Accumulation Edge | `i_pdiRequireEqS` | `true` | Boolean | Requires equal highs/lows at the accumulation boundary | **YES (in S-Tier)** | `iFVG_Ultimate_PDI_Refined.pine:61` |

---

## 4. Entry Logic

The folder's source material specifies two distinct entry architectures:
- **Architecture 1: Overlapping FVG Inversion with Liquidity Sweep** (`ifvg pro.txt`)
- **Architecture 2: Predistribution Inversion (PDI) / AMD Model** (`IFVG Model.pdf` & `iFVG_Ultimate_PDI_Refined.pine`)

Both rely on the exact 3-candle Fair Value Gap definition:
- Bullish FVG on current bar: `low > high[2]` (`ifvg pro.txt:287`, `iFVG_Ultimate_PDI_Refined.pine:475`)
  - Top = `low`, Bottom = `high[2]`
- Bearish FVG on current bar: `high < low[2]` (`ifvg pro.txt:288`, `iFVG_Ultimate_PDI_Refined.pine:476`)
  - Top = `low[2]`, Bottom = `high`

---

### Architecture 1: Standard Inversion (`ifvg pro.txt`)

#### Long Entry Rules:
1. **Current Bar forms a Bullish FVG**:
   $$\text{low}_t > \text{high}_{t-2}$$
   (`ifvg pro.txt:287`)
2. **Prior Bearish FVG in Lookback Window**:
   Within the prior `setupLookback` bars ($i \in [1, 20]$), there exists at least one historical Bearish FVG:
   $$\text{high}_{t-i} < \text{low}_{t-i-2}$$
   (`ifvg pro.txt:308, 310`)
3. **Imbalance Price Overlap**:
   The current bullish FVG price span overlaps the historical bearish FVG price span:
   $$\max(\text{newBtm}, \text{oldBtm}) < \min(\text{newTop}, \text{oldTop})$$
   where $\text{newTop} = \text{low}_t, \text{newBtm} = \text{high}_{t-2}, \text{oldTop} = \text{low}_{t-i-2}, \text{oldBtm} = \text{high}_{t-i}$ (`ifvg pro.txt:135-136, 292-293, 311-314`).
4. **Prior Liquidity Sweep Confirmation**:
   The lowest price during the setup sequence ($k \in [0, i]$) swept below the lowest low of the preceding `liqLookback` bars ($k \in [1, 20]$):
   $$\min_{k=0..i}(\text{low}_{t-k}) < \min_{k=1..\text{liqLookback}}(\text{low}_{t-i-k})$$
   (`ifvg pro.txt:319-326`).
5. **Imbalance Size Threshold**:
   $$\text{oldTop} - \text{oldBtm} \ge \text{minImbalanceTicks} \times \text{mintick}$$
   (`ifvg pro.txt:361-362`).
6. **A+ Session Sweep Gate (Optional, if `showAplus = true`)**:
   An Asia, London, or New York session low was swept within the last `setupLookback` bars:
   $$\text{bar\_index} - \text{lastBullSweepBar} \le \text{setupLookback}$$
   (`ifvg pro.txt:340-343`).

#### Short Entry Rules:
1. **Current Bar forms a Bearish FVG**:
   $$\text{high}_t < \text{low}_{t-2}$$
   (`ifvg pro.txt:288`)
2. **Prior Bullish FVG in Lookback Window**:
   Within prior $i \in [1, 20]$ bars, there exists a historical Bullish FVG:
   $$\text{low}_{t-i} > \text{high}_{t-i-2}$$
   (`ifvg pro.txt:307, 310`)
3. **Imbalance Price Overlap**:
   Current bearish FVG overlaps historical bullish FVG (`ifvg pro.txt:314`).
4. **Prior Liquidity Sweep Confirmation**:
   Highest price in sequence swept above highest high of preceding `liqLookback` bars:
   $$\max_{k=0..i}(\text{high}_{t-k}) > \max_{k=1..\text{liqLookback}}(\text{high}_{t-i-k})$$
   (`ifvg pro.txt:329-336`).
5. **Imbalance Size Threshold**:
   $$\text{oldTop} - \text{oldBtm} \ge \text{minImbalanceTicks} \times \text{mintick}$$
   (`ifvg pro.txt:361-362`).
6. **A+ Session Sweep Gate (Optional, if `showAplus = true`)**:
   An Asia, London, or New York session high was swept within the last `setupLookback` bars (`ifvg pro.txt:342-343`).

---

### Architecture 2: Predistribution Inversion (PDI / AMD) (`IFVG Model.pdf` & `iFVG_Ultimate_PDI_Refined.pine`)

The PDI model follows the 4-phase sequence defined in `IFVG Model.pdf:2, 6, 7`:
$$\text{Accumulation [A]} \longrightarrow \text{Manipulation Sweep [M]} \longrightarrow \text{FVG Creation \& Inversion} \longrightarrow \text{Distribution Entry [D]}$$

#### Long PDI Entry Rules:
1. **Accumulation Range Defined**:
   Over the lookback window `i_pdiAccLen` (default 15 bars), price is contained within a consolidated range:
   $$\text{accHigh} = \max_{1..15}(\text{high}), \quad \text{accLow} = \min_{1..15}(\text{low})$$
   $$\text{accHigh} - \text{accLow} \le \text{ATR}_{14} \times \text{i\_pdiAccAtrMax} \quad (\text{default } 2.5)$$
   (`iFVG_Ultimate_PDI_Refined.pine:481-484`).
2. **Manipulation Sweep (Downside)**:
   Price breaks below the accumulation floor:
   $$\text{low}_t < \text{accLow}$$
   initiating manipulation state (`pdiState = 1`, `pdiManipStartBar = bar_index`, `pdiManipExtreme = low`) (`iFVG_Ultimate_PDI_Refined.pine:487-494`, `IFVG Model.pdf:2`).
3. **Single Significant FVG Formed in Manipulation Leg**:
   During the downward manipulation leg (within `i_pdiManipBars`, default 12 bars), exactly one significant Bearish FVG forms:
   $$\text{high}_t < \text{low}_{t-2}, \quad \text{gapSize} = \text{low}_{t-2} - \text{high}_t \ge \text{ATR}_{14} \times 0.05$$
   Total FVGs in manipulation leg must be $\le 1$ (`pdiLegFvgCount <= 1`) (`iFVG_Ultimate_PDI_Refined.pine:514-524`, `IFVG Model.pdf:2`: *"The most optimal entry in the PDI Strategy is when there’s only one single FVG in the leg up or down"*).
4. **Inversion Confirmation (Candle Close Through Gap)**:
   Price reverses and a candle closes strictly above the top of the manipulation FVG:
   $$\text{close}_t > \text{c.top} \quad (\text{where } \text{c.top} = \text{low}_{t-2} \text{ of the manipulation FVG})$$
   (`iFVG_Ultimate_PDI_Refined.pine:526, IFVG Model.pdf:2, 8`).
5. **Rule 1 (Minimum R:R Filter)**:
   $$\text{Risk} = |\text{close}_t - \text{pdiSL}|, \quad \text{Reward} = \text{pdiTP} - \text{close}_t$$
   $$\text{calcRR} = \frac{\text{Reward}}{\text{Risk}} \ge 1.2 \quad (\text{default } \text{i\_pdiMinRR})$$
   $$\text{close}_t < \text{pdiTP} \quad \text{and} \quad \text{close}_t > \text{pdiSL}$$
   (`iFVG_Ultimate_PDI_Refined.pine:531-536`, `IFVG Model.pdf:4`: *"1 = If the Inversion is way too high, so near the highs or lows of the accumulation zone and it would give you terrible RR"*).
6. **Rule 3 (No Trade Against EQH/EQL)**:
   Trade cannot fire directly into unresolved Equal Highs / Equal Lows sitting between entry and target (`iFVG_Ultimate_PDI_Refined.pine:538`, `IFVG Model.pdf:4`: *"3 = Don't take it against EQH or EQL, they are kind of like magnets so why would you go against that?"*).
7. **Rule 4 (No Trade Inside Opposing 15m HTF FVG)**:
   Entry cannot occur while price is currently inside an opposing (Bearish) 15-minute FVG (`iFVG_Ultimate_PDI_Refined.pine:537`, `IFVG Model.pdf:4`: *"4 = When you want to take a bearish PDI but you are inside a bullish 15 min FVG - don't take it, its very easy to get manipulated"*).

#### Short PDI Entry Rules:
1. **Accumulation Range Defined**:
   Consolidated range over `i_pdiAccLen` bars: $\text{accHigh} - \text{accLow} \le \text{ATR}_{14} \times 2.5$ (`iFVG_Ultimate_PDI_Refined.pine:481-484`).
2. **Manipulation Sweep (Upside)**:
   Price breaks above the accumulation ceiling:
   $$\text{high}_t > \text{accHigh}$$
   initiating manipulation state (`pdiState = -1`, `pdiManipStartBar = bar_index`, `pdiManipExtreme = high`) (`iFVG_Ultimate_PDI_Refined.pine:495-502`, `IFVG Model.pdf:2, 3`).
3. **Single Significant FVG Formed in Manipulation Leg**:
   During upward manipulation leg (within 12 bars), exactly one significant Bullish FVG forms:
   $$\text{low}_t > \text{high}_{t-2}, \quad \text{gapSize} = \text{low}_t - \text{high}_{t-2} \ge \text{ATR}_{14} \times 0.05$$
   Total FVGs in manipulation leg $\le 1$ (`iFVG_Ultimate_PDI_Refined.pine:514-524`, `IFVG Model.pdf:2`).
4. **Inversion Confirmation (Candle Close Through Gap)**:
   Price reverses and a candle closes strictly below the bottom of the manipulation FVG:
   $$\text{close}_t < \text{c.btm} \quad (\text{where } \text{c.btm} = \text{high}_{t-2} \text{ of the manipulation FVG})$$
   (`iFVG_Ultimate_PDI_Refined.pine:527, IFVG Model.pdf:2, 7`).
5. **Rule 1 (Minimum R:R Filter)**:
   $$\text{calcRR} = \frac{\text{close}_t - \text{pdiTP}}{|\text{pdiSL} - \text{close}_t|} \ge 1.2, \quad \text{close}_t > \text{pdiTP} \text{ and } \text{close}_t < \text{pdiSL}$$
   (`iFVG_Ultimate_PDI_Refined.pine:531-536`, `IFVG Model.pdf:4`).
6. **Rule 3 & Rule 4 Gating**:
   Not trading against EQL/EQH (`IFVG Model.pdf:4`) and not inside a Bullish 15m HTF FVG (`IFVG Model.pdf:4`).

---

## 5. Signal Confirmation & Execution Timing

- **Confirmation on Candle Close**:
  - `ifvg pro.txt`: Evaluated strictly when `barstate.isconfirmed == true` (`ifvg pro.txt:291, 444, 469`).
  - `iFVG_Ultimate_PDI_Refined.pine`: Evaluated strictly on confirmed bar close (`iFVG_Ultimate_PDI_Refined.pine:480, 603, 626`).
- **Trigger Modes (`i_sigTrigger`)**:
  - `"Inversion Creation"` (Default): Fires on the exact bar that closes through and inverts the FVG (`iFVG_Ultimate_PDI_Refined.pine:560, 565`).
  - `"Retest / Touch"`: Does not enter on the inversion candle; waits for a subsequent bar to retest the inverted gap boundary and close in trade direction (`iFVG_Ultimate_PDI_Refined.pine:618-640`):
    - Bullish retest: $\text{low} \le \text{top}$ and $\text{high} \ge \text{btm}$ and $\text{close} > \text{open}$
    - Bearish retest: $\text{high} \ge \text{btm}$ and $\text{low} \le \text{top}$ and $\text{close} < \text{open}$
  - `"Both"`: Allows entry on creation or retest.
- **Execution Bar**: Evaluated on completed bar close $t$, executed at the open of bar $t+1$ (or at close of bar $t$ in vectorised backtests).

---

## 6. Stop Loss Logic

The source files document two distinct stop loss models:

### Model A: Initial Candle-1 Stop (`ifvg pro.txt`)
- **Bullish Stop**: Placed at candle 1's low of the 3-candle FVG formation:
  $$\text{StopPrice}_{\text{Long}} = \text{low}_{t-2}$$
  (`ifvg pro.txt:371`: `af_initialSL := isBullFVG ? low[2] : high[2]`).
- **Bearish Stop**: Placed at candle 1's high of the 3-candle FVG formation:
  $$\text{StopPrice}_{\text{Short}} = \text{high}_{t-2}$$
  (`ifvg pro.txt:371`).
- **Alternative Swing Stop (`ifvg pro.txt`)**:
  $$\text{SwingStop}_{\text{Long}} = \min_{15}(\text{low}) - \text{swingBufferTicks} \times \text{mintick}$$
  $$\text{SwingStop}_{\text{Short}} = \max_{15}(\text{high}) + \text{swingBufferTicks} \times \text{mintick}$$
  (`ifvg pro.txt:110-111, 372`).

### Model B: Manipulation Extreme Wick Stop (`IFVG Model.pdf` & `iFVG_Ultimate_PDI_Refined.pine`)
- **Bullish Stop**: Placed immediately below the manipulation extreme wick:
  $$\text{StopPrice}_{\text{Long}} = \text{pdiManipExtreme} - 2 \times \text{mintick}$$
  (`iFVG_Ultimate_PDI_Refined.pine:531, 577-578`, `IFVG Model.pdf:3, 6, 7`).
- **Bearish Stop**: Placed immediately above the manipulation extreme wick:
  $$\text{StopPrice}_{\text{Short}} = \text{pdiManipExtreme} + 2 \times \text{mintick}$$
  (`iFVG_Ultimate_PDI_Refined.pine:531, 577-578`, `IFVG Model.pdf:3, 6, 7`).

---

## 7. Take Profit & Target Logic

### Model A: Session & Swing Liquidity Targets (`ifvg pro.txt`)
- In `ifvg pro.txt`, target price (`af_aplusTarget`) is dynamically derived from resting liquidity lines (`ifvg pro.txt:374, 249-270`):
  - For Longs: Nearest unmitigated session high above current price (Asia High, London High, NY High) (`ifvg pro.txt:249-258`).
  - For Shorts: Nearest unmitigated session low below current price (Asia Low, London Low, NY Low) (`ifvg pro.txt:261-270`).

### Model B: Accumulation Shelf Boundary Target (`IFVG Model.pdf` & `iFVG_Ultimate_PDI_Refined.pine`)
- **Take Profit 1 (TP1)**: Placed exactly at the opposite boundary of the accumulation range:
  - Long Target: $\text{TP1} = \text{pdiAccHighState}$ (`iFVG_Ultimate_PDI_Refined.pine:532, 580`, `IFVG Model.pdf:2, 3`: *"set the first TP at the bottom of the accumulation zone and then leave some runners"* / *"You could then have your TPs at the top of the accumulation zone"*).
  - Short Target: $\text{TP1} = \text{pdiAccLowState}$ (`iFVG_Ultimate_PDI_Refined.pine:532, 580`, `IFVG Model.pdf:2, 3`).
- **Secondary Target (Runners)**: Past buyside/sellside liquidity pools (`IFVG Model.pdf:2, 3`).

---

## 8. Invalidation & Exit Logic

1. **Structural Stop Breach Invalidation**:
   - `ifvg pro.txt`: Evaluated on confirmed candle close against the registered stop:
     $$\text{Long Invalidated if } \text{close}_t < \text{StopPrice}$$
     $$\text{Short Invalidated if } \text{close}_t > \text{StopPrice}$$
     (`ifvg pro.txt:447-455`: `"reason: [dir] IFVG invalidated after candle-3 confirmation"`).
2. **iFVG Box Invalidation**:
   - Both `ifvg pro.txt` and `iFVG_Ultimate_PDI_Refined.pine` define an iFVG setup as failed if a subsequent candle closes through the opposite boundary of the inverted gap:
     $$\text{Bullish iFVG fails if } \text{close}_t < \text{realBtm}$$
     $$\text{Bearish iFVG fails if } \text{close}_t > \text{realTop}$$
     (`ifvg pro.txt:470`, `iFVG_Ultimate_PDI_Refined.pine:602-607`).
   - Generates immediate exit signals: `sigExitLong := true` or `sigExitShort := true` (`iFVG_Ultimate_PDI_Refined.pine:605-607`).

---

## 9. Trailing Stop Logic

- **Source Code Finding**:
  - `ifvg pro.txt`: **NO DYNAMIC TRAILING STOP** in code. Orders use fixed initial/swing stop and fixed target. Midpoint CE (50%) touch is tracked for alerts (`ifvg pro.txt:509-520`), but does not trail stop loss.
  - `iFVG_Ultimate_PDI_Refined.pine`: **NO DYNAMIC TRAILING STOP** in code. Levels are static once registered (`iFVG_Ultimate_PDI_Refined.pine:566-578`).
  - `IFVG Model.pdf`: Mentions taking partial TP at the accumulation edge and leaving "runners", but provides **no quantitative formula** for trailing stops on runners.

---

## 10. Timeframe

- **Execution Chart Timeframe**:
  - `IFVG Model.pdf:2`: Mentions executing on **1-minute** (`1m`) and **2-minute** (`2m`): *"e.g on the 1 minute TF there's multiple ones but then there's only 1 in the 2 min. Because then you’ll just have to wait for the 2 min FVG to get inversed and then you can enter."*
  - `ifvg pro.txt` and `iFVG_Ultimate_PDI_Refined.pine`: Operates on the chart's native resolution.
- **Higher Timeframe References**:
  - `IFVG Model.pdf:4, 8`: Emphasizes **15-minute** (`15m`) FVG alignment (Rule 4: check 15m FVG).
  - `ifvg pro.txt`: Inputs define Asia (19:00–23:59), London (02:00–05:00), and New York (07:00–10:00 / 09:30–11:00) session liquidity windows. Also checks 1H and 4H bias.

---

## 11. Repainting / Lookahead Audit

- **Audit of `iFVG_Ultimate_PDI_Refined.pine`**:
  - **NON-REPAINTING**.
  - All HTF requests use closed-bar indexing `[1]` with `barmerge.lookahead_off` (`line 232-233`):
    ```pinescript
    request.security(syminfo.tickerid, tf, [fvgTop[1], fvgBtm[1], isBull[1], fvgTime[1]], lookahead=barmerge.lookahead_off)
    ```
  - Signals fire strictly on `barstate.isconfirmed == true`.
- **Audit of `ifvg pro.txt`**:
  - **REPAINT / LOOKAHEAD RISK DETECTED IN HTF MODULE**:
  - In `ifvg pro.txt:186`, line reads:
    ```pinescript
    [ib, bTop, bBtm, ir, sTop, sBtm, gapTime] = request.security(syminfo.tickerid, tf, f_execHtfFvg(), lookahead=barmerge.lookahead_on)
    ```
  - `lookahead=barmerge.lookahead_on` on intrabar data creates lookahead bias in historical Pine backtests.
  - *Recommendation*: Python implementation must eliminate `lookahead_on` and calculate HTF states strictly using completed closed bars.

---

## 12. Ambiguous / Unspecified — Needs User Input

The following critical points are either unspecified, ambiguous, or have conflicting implementations across the source material in `strategies/iFVG/`. Per instructions, these are NOT filled with invented defaults:

### Item 1: Core Strategy Variant Selection
The folder contains two fundamentally different iFVG signal models:
- **Variant 1 (Kairos `ifvg pro.txt`)**: Any 3-bar FVG that overlaps with any opposing FVG in the last 20 bars, gated by a prior liquidity sweep and session timing. Stop is placed at Candle 1 (`low[2]` / `high[2]`).
- **Variant 2 (PDI Model `IFVG Model.pdf` & `iFVG_Ultimate_PDI_Refined.pine`)**: Requires an explicit Accumulation range $\to$ Manipulation breakout/sweep $\to$ Single FVG formed in manipulation leg $\to$ Inversion close through that FVG $\to$ TP at opposite accumulation edge, SL at manipulation wick.
- *Question for User*: Which variant should serve as the primary strategy to test on MNQ:
  - (a) Variant 1: Kairos Standard Overlapping iFVG (`ifvg pro.txt`)
  - (b) Variant 2: ICT PDI (Predistribution Inversion) AMD Model (`IFVG Model.pdf`)
  - (c) Test both independently in raw signal forensics?

### Item 2: Native Chart Timeframe for Backtesting
`IFVG Model.pdf` mentions 1m, 2m, and 15m. `MNQ_1m_continuous.parquet` is 1-minute data.
- *Question for User*: Should raw signal forensics be evaluated on:
  - (a) Pure 1-minute bars (`1m`),
  - (b) 5-minute aggregated bars (`5m`), matching the Herman benchmark,
  - (c) Or both?

### Item 3: Signal Execution Trigger (Creation vs Retest)
`iFVG_Ultimate_PDI_Refined.pine` line 39 provides three trigger options:
- `"Inversion Creation"`: Signal triggers immediately on the bar that flips/closes through the FVG.
- `"Retest / Touch"`: Signal triggers only when a subsequent bar pulls back into the iFVG box and rejects.
- *Question for User*: Which trigger mechanism should be the primary entry rule?

### Item 4: Stop Loss Rule for Raw Signal Forensics
- Variant 1 uses Candle 1 extreme (`low[2]` / `high[2]`).
- Variant 2 uses Manipulation Extreme Wick (`pdiManipExtreme +/- 2 ticks`).
- *Question for User*: If testing raw signal forensics before stop/target logic (Step 4), should we test raw unstopped MFE/MAE first with the standard placeholder risk unit (e.g. 20 points / 50 points), or use the native setup stop defined by the selected model?

### Item 5: Accumulation Detection Parameters (PDI Model only)
If Variant 2 (PDI) is selected, `iFVG_Ultimate_PDI_Refined.pine` sets:
- `i_pdiAccLen = 15` bars
- `i_pdiAccAtrMax = 2.5` ATR
- `i_pdiManipBars = 12` bars
- *Question for User*: Should we lock these exact default parameters from `iFVG_Ultimate_PDI_Refined.pine`, or does your trading manual prescribe specific bar lookbacks?

---
