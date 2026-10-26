"""ArbitrageIQ backend package.

A local decision-support tool for an Indian ecommerce reseller. Contribution profit is
computed here and only here — the frontend renders what this package returns and never
re-implements a formula (plans/AGENTS.md rule 7).

No module in this package makes an outbound network call (plans/SECURITY.md §7).
"""

__version__ = "0.0.0"
