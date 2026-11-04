# Authorized independent clinical-data audit

The authors state supporting data-use authorization and the applicable ethics
documentation are available. The data custodian must provide the permitted
independent reviewer with the exact issuer/reference/scope, approved access
conditions and an approved restricted computing environment. This document does
not create authorization, an ethics determination or a consent waiver.

1. Record reviewer identity, institutional role, authorization reference, source
   extract hash and analysis-code/environment identity in the independent report.
2. Keep identifiers, dates/attributes at record level, individual scores and
   fitted clinical weights inside the authorized environment. Do not copy them
   into the public image or reviewer bundle.
3. Reconcile the approved January–April 2026 extract with the source audit and
   11 Excel files using the supplied cohort-reconciliation code. Reproduce the
   No-eRM patient-day endpoint and mature January–March index inclusion rule.
4. Run `observed_30d.py` against the approved source path with the published seeds,
   feature definitions, patient-disjoint/temporal partitions, calibration and
   validation-selected threshold procedure. Separately execute the fixed-role
   ambiguous-identity exclusion sensitivity. Do not choose a new protocol after
   viewing test results.
5. Compare all 90 aggregate operating points and confusion counts with the
   published CSV/JSON. Preserve exact count equality; report numerical metric
   deviations and software/hardware effects rather than silently changing the
   reference. Numerical-versus-statistical tolerance must be agreed before rerun.
6. Export only custodian-approved aggregate comparisons and the signed external
   report. Record every failed command, changed assumption and unavailable input.

No authorized independent clinical-data replication was performed in v26. The
blank report is supplied to make a future legitimate audit executable and
documented, not to imply that an external investigator already completed it.
