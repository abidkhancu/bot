"""Paper Trading module for the Crypto Futures Signal Bot.

When ``PAPER_TRADING_ENABLED=True`` in config, signals are forwarded to the
PaperInvest API (or a local simulation fallback) so you can evaluate strategy
performance before connecting to a live exchange.
"""
