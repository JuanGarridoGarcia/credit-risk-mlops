"""Monitoring of the models in service (step 6.1, D-137 to D-146).

Every month the system's flow measures, for what the champions received and answered:

- **drift** (:mod:`~credit_risk.monitoring.drift`): the PSI of each of the 30 features
  and of the PD, the LGD and the expected loss rate against the reference of the pair of
  champions that answered (D-139), with the share of missing values, the new values and,
  for information only, the Kolmogorov-Smirnov statistic;
- **early warning** (:mod:`~credit_risk.monitoring.outcomes`): the default rate within
  12 months of the cohort listed 17 months before, against what its PD expected (D-143);
- **real performance**: the cohorts that have just matured (term + 5 months), measured
  like a challenger at promotion (D-144).

The reference of a pair of champions (D-138, D-142) and the monthly run live in
:mod:`~credit_risk.monitoring.store`; the results go to the tables of the schema
``monitoring`` (D-146).
"""
