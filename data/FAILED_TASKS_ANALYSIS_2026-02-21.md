# Retail Simulation Failure Analysis (2026-02-21)

**Simulation file:** `2026-02-21T00:37:20.185158_retail_llm_agent_gpt-4.1-mini_user_simulator_gpt-4.1-mini.json`  
**Tasks reference:** `tau2-bench/data/tau2/domains/retail/tasks.json`

## Summary

| Metric | Value |
|--------|--------|
| Total simulations | 114 |
| Failed (reward = 0) | 35 |
| Success rate | **69.3%** |

Reward is computed as **DB × COMMUNICATE** (both must be 1.0 for success). Failures are due to:

1. **DB = 0** — Final environment state did not match the golden trajectory (wrong or missing actions, or wrong order/arguments).
2. **COMMUNICATE = 0** — Required information was not communicated to the user (e.g. numeric answer, tracking number, total refund).

---

## Failure categories

### A. DB match = true, COMMUNICATE = 0 (correct actions, missing communication)

The agent did the right tool calls and state changes but **did not tell the user** the specific information required by the task.

| Task ID | Scenario (summary) | What was not communicated | Correction |
|---------|--------------------|----------------------------|------------|
| **2** | Count t-shirt options + return cleaner, headphone, smart watch | **"10"** (number of t-shirt options) | After `get_product_details` for the t-shirt product, explicitly tell the user: "There are 10 t-shirt options available." |
| **3** | Count t-shirt options + modify pending small t-shirt to purple, etc. | **"10"** (number of t-shirt options) | Same as task 2: state the count clearly in the reply. |
| **4** | Count t-shirt options + modify pending t-shirts to purple, S, etc. | **"10"** (number of t-shirt options) | Same as task 2: state the count clearly in the reply. |
| **34** | WFH scenario: change address or return office items; total refund amount | **"1093.34"** (total refund amount) | After computing returns/cancellations, state the total refund amount (e.g. "You will get $1093.34 back in total."). |
| **95** | Exchange two laptops to i7/8GB/1TB SSD; total amount to pay today | **"167.87"**, **"60.78"** (per-exchange price differences) | Evaluation expects each exchange’s price difference to be stated; agent stated only total "107.09". | After each exchange (or in one summary), state the price difference for each order (e.g. "$167.87 for the first, $60.78 for the second; total $107.09 today"). |

**Root cause (A):** The agent answers the user’s question but omits the exact value the evaluation expects (e.g. the number "10" or "1093.34"). The communicate check looks for that value in the agent’s messages.

**How to correct:**  
- In policy or prompts: after lookups (product variants, totals, refunds), require the agent to **explicitly state** the requested number or value in natural language.  
- Optionally add examples in few-shot or instructions: "When the user asks how many X options exist, reply with a sentence that includes the number."

---

### B. DB match = false, COMMUNICATE = 1 (wrong or missing actions)

The agent communicated the required info but **did not execute the expected sequence of actions** (or used wrong arguments). The evaluator matches golden actions to the trajectory in order; wrong order or wrong args can cause a match to be “consumed” by the wrong golden action and lead to DB mismatch.

| Task ID | Scenario (summary) | Failed action(s) | Likely issue | Correction |
|---------|--------------------|------------------|--------------|------------|
| **15** | Modify pending boots to size 8, same material | `modify_pending_order_items` (order #W5199551, item → new variant) | Modify may not have been called with exact item/variant IDs, or was skipped. | Confirm order and item IDs from `get_order_details` / `get_product_details`, then call `modify_pending_order_items` with the exact expected item_ids and new_item_ids. |
| **17** | Change delivery address for #W8665881 to Suite 641 | `get_user_details`, `get_order_details` (#W5199551, #W8665881, #W9389413), `modify_pending_order_address` | Expected **order** of `get_order_details` calls: #W5199551, #W8665881, #W9389413. Agent likely called them in a different order. | When multiple orders are involved, follow the golden order of lookups (or ensure policy specifies a canonical order) so the trajectory matches. |
| **20** | Upgrade all items to most expensive variants; pay difference with gift card | `get_order_details` (#W4967593), `modify_pending_order_items` (4 items on #W9911714), `get_order_details` (#W5733668) | Either order of `get_order_details` calls differed, or `modify_pending_order_items` was not called with the exact 4 item_ids/new_item_ids. | Match the expected sequence: get orders in the specified order, then single `modify_pending_order_items` with all 4 item changes. |
| **27** | Return hose + backpack, exchange boots to waterproof variant | (All actions matched; DB still false) | Possible confusion between return vs exchange; or exchange/return calls with wrong item_ids or payment_method. | Ensure return and exchange are done for the correct orders/items and that exchange uses the exact new_item_id for the waterproof variant. |
| **31** | Lost tablet: tracking, refund/reorder, cancel charger, cancel boot, keep kettle, return sneaker | (All actions matched; DB still false) | Complex branching: user prefers partial cancels; agent may have cancelled full order or wrong items. | Follow scenario: cancel only charger (and boot if possible), keep kettle, return sneaker; ensure tracking and refund info communicated. |
| **32** | Same as 31 but cancel boot and kettle (not just boot) | `get_order_details` (specific order), `cancel_pending_order` (#W9373487), and order of subsequent get_order/cancel/return | Order of operations and which orders are cancelled vs returned. | Same as 31; ensure cancel is for the correct orders (charger, boot, kettle) and return only sneaker; order of get_order_details matters. |
| **36** | Order over limit: split payment or switch to cheapest options | `modify_pending_order_items` (3 items → cheapest variants on #W9348897) | Agent may have offered cancel or other path instead of actually calling modify with the three item changes. | When user accepts “switch to cheapest options,” call `modify_pending_order_items` once with all three item_ids and corresponding new_item_ids. |
| **38** | Same as 36 but cancel order if cannot reduce cost | `calculate` (sum), `cancel_pending_order` (#W9348897) | Golden path has find_user_id_by_email then find_user_id_by_name_zip; then only calculate and cancel. Agent may have done extra lookups so trajectory order diverged. | Align trajectory with golden: authenticate (email then name_zip if in golden), then calculate total, then cancel order. |
| **41** | Fix address on orders + change jigsaw to easiest variant | `modify_pending_order_items` (#W4082615, one item → new variant) | Address updates may have been done; item modification for jigsaw might be missing or wrong item_id/new_item_id. | After address fixes, call `modify_pending_order_items` for the jigsaw item with exact item_ids/new_item_ids from product details. |
| **57** | Order W4284542: ETA; if not shipped, cancel air purifier or whole order to gift card | (No golden actions; DB still false) | Task has no explicit action list; final state may differ (e.g. order not cancelled or refund method wrong). | Implement scenario branches: check status; if not shipped, try cancel single item, else cancel full order with refund to gift card; if not possible, do nothing. |
| **59** | Two orders: status, cancel older if not within 5 days, refund amount; change address for the other | `calculate` (164.28), `cancel_pending_order` (#W8268610), `modify_pending_order_address` (#W2702727) | Agent may have communicated amounts but not executed cancel and address change with exact arguments. | Execute cancel for #W8268610 and address change for #W2702727 with the exact new address; use calculate with expression "164.28" for refund. |
| **64** | Exchange camera to highest-resolution waterproof at same price | `exchange_delivered_order_items` (delivered order), `modify_pending_order_items` (pending) | Order #W7464385 might be delivered for one item and pending for another; agent may have used wrong tool (e.g. only modify or only exchange). | Determine which items are from delivered vs pending order; use exchange for delivered item and modify for pending item with exact IDs. |
| **66** | Change luggage to coat; else return; else cancel order | `cancel_pending_order` (#W3361211) | User fallback: if change not possible, return; if issues, cancel. Agent may have modified/returned instead of cancelling. | Follow fallback: try modify, then return item, then cancel entire order if needed; use exact order_id and reason. |
| **71** | Modify order to default address + lamp black + backpack medium/polyester; confirm with PayPal | `modify_pending_order_address`, `modify_pending_order_items` (lamp + backpack) | Expected: address first, then items. Agent may have done only one of the two or in wrong order. | Call `modify_pending_order_address` for #W5270061, then `modify_pending_order_items` with both item changes (lamp, backpack) in one call. |
| **72** | Same as 71: address then item changes; mention both at start | `modify_pending_order_address` | Same as 71; address change may be missing or only item change performed. | Same as 71: ensure both address and item modifications are executed in the expected order. |
| **74** | Exchange laptop to i9; cancel other pending order (5 items) | `cancel_pending_order` (#W3189752), `modify_pending_order_items` (#W5166363, laptop item) | Expected: cancel one order first, then modify the other. Agent may have only done one. | Execute cancel for #W3189752, then modify #W5166363 for the laptop item with exact item_ids/new_item_ids. |
| **76** | Remove fleece from pending order or cancel; modify skateboard to maple/34"/graphic or cancel; total grills price | `cancel_pending_order` (#W8367380, #W1242543) | Golden expects two cancels (fleece order, skateboard order). Agent may have only done one or used wrong reason. | Execute both cancels with exact order_ids and reasons ("ordered by mistake" for #W8367380, "no longer needed" for #W1242543). |
| **82** | Return the more expensive of two tablets to credit card; if not possible, return everything to GC | `return_delivered_order_items` (#W9571698, 4 item_ids, gift_card) | User wants refund to credit card first; if not possible, return all and refund to GC. Agent may have used GC directly or wrong item set. | Try refund to credit card; if policy disallows, return all 4 items and use gift_card_7250692. |
| **98** | Exchange bicycle + jigsaw (same order), exchange camera (other order), cancel skateboard order | Two `exchange_delivered_order_items` + `cancel_pending_order` (#W8855135) | All three actions expected; agent may have done exchanges but not cancel, or wrong payment/order. | Execute both exchanges with exact item_ids/new_item_ids, then cancel #W8855135 with reason "no longer needed". |
| **99** | Same as 98 but art-over-animal for jigsaw; prefer visa; cancel only skateboard (or whole order if single-item cancel not possible) | Two `exchange_delivered_order_items` (second has different new_item_id 5546244844) | One exchange used wrong new_item_id (6245746168 vs 5546244844 for art preference). Agent may have chosen animal variant. | Use exact new_item_ids per golden (art theme for jigsaw); execute cancel for skateboard only or whole order. |
| **101** | Two orders: change address to NY, modify silicone watch to metal (white); modify air purifier to large+night+HEPA | `modify_pending_order_address` (#W4219264) + two `modify_pending_order_items` (#W4219264, #W6729841) | Address change may be missing, or only one order modified. | Do address change for #W4219264, then item change on same order (watch), then item change on #W6729841 (purifier). |
| **103** | Return bookshelf+jigsaw (same order), return backpack (other); change pending address to Chicago default + item to red; tracking for cancelled order | Two returns + `modify_pending_order_address` + `modify_pending_order_items` | Golden has modify_address before modify_items. Agent may have done returns only or wrong order of modify. | Execute returns, then modify_pending_order_address for #W4860251, then modify_pending_order_items (red variant). |
| **104** | Return bookshelves/jigsaws from different orders, return backpack; change pending item to red + address to Chicago default; tracking | Multiple returns in specific order + modify address + modify items | Expected order: return #W8660475, return #W9218746, modify address #W4860251, modify items #W4860251, return #W6239298. Agent may have done different order. | Follow exact sequence of returns and modifies; ensure pending order is #W4860251 for address+item changes. |
| **109** | Change wrong order address + user default to new Houston address; exchange tablet to cheapest | `modify_pending_order_address` (#W1603792) + `modify_user_address` + `modify_pending_order_items` (tablet→cheapest) | All three actions required. Agent may have looked up address but not executed both address changes and exchange. | Execute order address change, user default address change, then exchange_delivered_order_items for tablet to cheapest variant. |
| **110** | Same as 109 but different new address (760 Elm, 77034) and tablet order | `modify_pending_order_address` (#W1092119), `modify_user_address`, `modify_pending_order_items` (#W1603792) | Address changes may be for different order (#W1092119). Agent may have modified wrong order or skipped item change. | Change address for #W1092119 and user profile to 760 Elm; then modify #W1603792 tablet to cheapest. |
| **112** | Modify laptop order to NYC address; modify laptop to item 9844888101; change watch to black dial, leather | `modify_pending_order_items` (#W9810810), `modify_pending_order_address` (#W3730488), `modify_pending_order_items` (#W3730488) | Expected: modify items on #W9810810, then address on #W3730488, then items on #W3730488. Agent may have done only address or wrong order. | Execute item change on #W9810810 (laptop), address change on #W3730488, then item change on #W3730488 (watch). |

**Root cause (B):**  
- **Order sensitivity:** The evaluator matches golden actions to the **first** matching tool call in the trajectory. If the agent calls `get_order_details(A)` then `get_order_details(B)`, but the golden order is B then A, the first golden (B) matches the second call and the second golden (A) has no matching call left → action mismatch and DB = 0.  
- **Missing or wrong arguments:** A required call (e.g. `modify_pending_order_items`, `cancel_pending_order`) may be missing or use wrong order_id/item_ids/new_item_ids.

**How to correct:**  
- **Agent:** Prefer a consistent order for multi-order lookups (e.g. by order_id or by recency) and document it so the agent follows one canonical sequence.  
- **Tasks:** If multiple valid orders of operations are acceptable, consider evaluation that is order-agnostic for read-only actions (e.g. allow any permutation of `get_order_details`).  
- **Agent:** Before modify/exchange/cancel, re-confirm order_id and item_ids from latest get_order_details/get_product_details so arguments match the golden IDs.

---

### C. DB match = false, COMMUNICATE = 0 (both wrong)

Both the action trajectory and the required communication failed.

| Task ID | Scenario (summary) | Failed actions | Communicate failure | Correction |
|---------|--------------------|----------------|---------------------|------------|
| **16** | Cancel all pending orders; return one watch; total amount back | `calculate` (3131.1+4777.75+367.38), `return_delivered_order_items` (#W9389413, one item) | **"8276.23"** not communicated | Execute both cancels and the return, run calculate with the exact expression, then tell the user the total refund amount "8276.23". |
| **28** | Return skateboard, hose, backpack, keyboard, bed; cancel hose from pending; total refund | `calculate` (200.8+96.35+193.38+231.37+196.53) | **"918.43"** not communicated | Perform all returns and the cancel, calculate the sum, then state: "Your total refund will be $918.43" (or the exact value). |
| **33** | WFH: return office items or keep order; total refund; else change default address to Seattle | `modify_user_address` (Noah, Seattle address) | **"1093.34"** not communicated | When partial cancel/return is not possible, change default address via `modify_user_address`; also communicate the total refund amount when applicable. |
| **45** | Exchange robotic vacuum for canister; gift card for price difference | `calculate` (652.61-642.72), `exchange_delivered_order_items` | **"9.89"** (price difference) not communicated | After exchange, compute price difference (e.g. 9.89) and tell the user they will receive that amount on a gift card (or as specified). |

**Root cause (C):** Combination of (A) and (B): either the agent did not perform the full set of actions, or performed them in the wrong order/with wrong args, and also did not communicate the required numeric value.

**How to correct:** Apply both action-sequence fixes (B) and communication fixes (A): ensure exact actions and then explicitly state the required numbers in the reply.

---

### D. Action order / “first product lookup” (DB true, COMMUNICATE 0)

Tasks **2, 3, 4** also have a **failed action**: `get_product_details(product_id: "6086499569")` — the t-shirt product. The golden sequence expects this **before** the other product lookup (9523456873). So the agent likely looked up the other product first; the first matching `get_product_details` in the trajectory then matched the second golden action, and the t-shirt lookup was never matched → one action check failed. Because reward is only DB × COMMUNICATE for these tasks, and DB was still true, the **reward 0** is from COMMUNICATE (not stating "10"). So for 2, 3, 4 the main fix is communication; optionally align product lookup order (t-shirt first when user asks for t-shirt count) so that action checks would also pass in a stricter evaluation.

---

## Recommended changes

### For the agent (policy / prompts)

1. **Always state requested numbers:** When the user asks “how many…”, “what’s the total…”, “what’s the difference…”, include the exact number in a clear sentence (e.g. “There are 10 t-shirt options.” / “Your total refund will be $8276.23.”).
2. **Stable order for multi-order flows:** When handling multiple orders, use a deterministic order (e.g. sort by order_id or by mention order) for `get_order_details` and other read-only calls so trajectories align with golden sequences.
3. **Confirm before modify/cancel/return:** Re-read order and item IDs from the latest get_order/get_product before calling modify/cancel/return so arguments match the intended items.
4. **One-shot modify when changing multiple items:** Use a single `modify_pending_order_items` (or exchange) with all item_ids and new_item_ids when the scenario expects one call for multiple items.

### For task design / evaluation

1. **Communicate_info:** Ensure `communicate_info` lists every exact string/number the user must be told (e.g. "10", "8276.23"); keep formatting consistent (e.g. "1093.34" vs "1093.34").
2. **Order-agnostic read actions:** If multiple orderings of `get_order_details` / `get_product_details` are valid, consider evaluating only the set of calls (or allow reordering) so that correct but reordered behavior does not get DB = 0.
3. **Branching scenarios:** For tasks like 57, 66, 31, 32, document the exact branches (cancel one item vs whole order, refund to gift card vs not) so the golden trajectory matches the intended branch.

---

## Task index (reward = 0)

| Task ID | DB | COMM | Primary failure |
|--------|----|------|------------------|
| 2  | ✓ | ✗ | Communicate "10" |
| 3  | ✓ | ✗ | Communicate "10" |
| 4  | ✓ | ✗ | Communicate "10" |
| 15 | ✗ | ✓ | modify_pending_order_items |
| 16 | ✗ | ✗ | calculate + return + "8276.23" |
| 17 | ✗ | ✓ | get_order order + modify_pending_order_address |
| 20 | ✗ | ✓ | get_order order + modify_pending_order_items |
| 27 | ✗ | ✓ | DB state (return/exchange) |
| 28 | ✗ | ✗ | calculate + "918.43" |
| 31 | ✗ | ✓ | DB state (branching) |
| 32 | ✗ | ✓ | get_order order + cancel/return |
| 33 | ✗ | ✗ | modify_user_address + "1093.34" |
| 34 | ✓ | ✗ | Communicate "1093.34" |
| 36 | ✗ | ✓ | modify_pending_order_items (3 items) |
| 38 | ✗ | ✓ | calculate + cancel_pending_order |
| 41 | ✗ | ✓ | modify_pending_order_items (jigsaw) |
| 45 | ✗ | ✗ | calculate + exchange + "9.89" |
| 57 | ✗ | ✓ | No golden actions; DB state |
| 59 | ✗ | ✓ | calculate + cancel + modify address |
| 64 | ✗ | ✓ | exchange vs modify (delivered vs pending) |
| 66 | ✗ | ✓ | cancel_pending_order |
| 71 | ✗ | ✓ | modify address + modify items |
| 72 | ✗ | ✓ | modify_pending_order_address |
| 74 | ✗ | ✓ | cancel + modify_pending_order_items |
| 76 | ✗ | ✓ | cancel_pending_order (both orders) |
| 82 | ✗ | ✓ | return_delivered_order_items (4 items, GC) |
| 95 | ✓ | ✗ | Communicate "167.87", "60.78" (per-exchange amounts) |
| 98 | ✗ | ✓ | two exchanges + cancel_pending_order |
| 99 | ✗ | ✓ | two exchanges (art vs animal new_item_id) |
| 101 | ✗ | ✓ | modify address + two modify_pending_order_items |
| 103 | ✗ | ✓ | returns + modify address + modify items (order) |
| 104 | ✗ | ✓ | return order + modify order (sequence) |
| 109 | ✗ | ✓ | modify address (order + user) + modify items |
| 110 | ✗ | ✓ | modify address (order + user) + modify items |
| 112 | ✗ | ✓ | modify items + modify address + modify items |

(COMM = COMMUNICATE check; ✓ = pass, ✗ = fail.)

---

*Generated from `tau2-bench/scripts/analyze_failed_tasks.py` and simulation/task JSON. For full action lists and communicate checks, see `tau2-bench/data/failed_tasks_analysis.json`.*
