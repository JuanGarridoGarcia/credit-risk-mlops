"""Simulated Lending Club: the only code that reads the 2019 snapshot (D-043).

It plays the role of the data provider. For each month it writes two deliveries,
``listings`` and ``outcomes`` (D-039), as gzip-compressed CSV with every value as
text (D-050). The rest of the system must never import this package (test T1.11).
"""
