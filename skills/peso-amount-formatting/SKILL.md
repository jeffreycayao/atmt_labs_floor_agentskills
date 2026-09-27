---
name: peso-amount-formatting
description: Present confirmed Philippine peso amounts consistently in customer copy, reports, and tables. Use for formatting only, not tax, exchange, or accounting calculations.
---

# Peso amount formatting

Format amounts already identified as Philippine pesos for the requested medium. Preserve the underlying numeric value and any meaningful precision.

- For ordinary display, use `₱` before the amount and comma grouping: `₱1,250` or `₱1,250.50`. Use two decimal places for centavo amounts; do not silently round away supplied precision needed for a calculation or audit.
- Keep a column or report internally consistent. If a system expects a numeric field, leave it numeric and put the currency in the presentation layer.
- Distinguish PHP from other currencies. When mixed currencies or a system without reliable peso-symbol support are involved, use `PHP 1,250.00` if that makes the currency unambiguous.
- Ask for clarification when a source such as `1.234,56` has an ambiguous decimal convention. Do not infer tax inclusion, VAT, exchange rates, discounts, or conversion from the format alone.
- For prose, spell out the currency only when it improves clarity; retain the exact amount supplied. Never treat a formatted amount as evidence that a payment was received or a receipt was issued.
