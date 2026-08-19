"""Adapters. Lower an approved rule package into an executable target.

Adapters are one-way and lossy by nature: a target runtime has its own semantics, and
where those differ from the IR the difference is reported rather than absorbed.
"""
