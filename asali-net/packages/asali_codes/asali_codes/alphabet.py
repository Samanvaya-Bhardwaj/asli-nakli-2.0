"""Crockford Base32: no I, L, O or U, so the commonest misreads can be undone exactly."""

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
INDEX = {ch: i for i, ch in enumerate(ALPHABET)}

# Letters that are not in the alphabet but are read for a digit they resemble.
DECODE_ALIASES = {"O": "0", "I": "1", "L": "1"}

SERIAL_LENGTH = 11
ISSUER_LENGTH = 2
