"""Query context discovery (Phase 3).

Each node explores its own database through its own keys and returns the context it found. The asking node
merges what the nodes return (`aggregate.py`) and uses it to search the text vaults.
"""
