"""Intraday (daytrading) research toolkit for liquid US stocks.

Pipeline: data.py (Alpaca/CSV/synthetic) -> strategies.py (entry rules) ->
engine.py (cost-aware, flat-by-close simulation) -> validate.py (walk-forward).
Research only: no live order placement lives here.
"""
