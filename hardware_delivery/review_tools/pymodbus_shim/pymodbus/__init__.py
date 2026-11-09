"""Stand-in for pymodbus that talks to ``fakeplc.py`` (review tool only).

Put ``hardware_delivery/review_tools/pymodbus_shim`` first on ``PYTHONPATH`` only
for ``observer_check.sh``.  It shadows the real pymodbus and must never be on the
path of a measurement run.  Each call does less Python work than real pymodbus,
so the observer starvation it exposes is, if anything, understated.
"""
