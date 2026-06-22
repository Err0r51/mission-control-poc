# Metabase Dashboard Playbook

This playbook treats `warehouse.analytics` as the KPI source of truth and Metabase as the
presentation layer. The main dashboard should be built with Metabase query builder only.
Do not recreate KPI logic in native SQL unless the warehouse contract changes first.

## KPI contract

| KPI | Canonical warehouse field(s) | Grain | Definition | Metabase query-builder note |
| --- | --- | --- | --- | --- |
| True positive incidents | `analytics.kpi_monthly.true_positive_incidents` | tenant + month | Count of incidents opened in the month where `fact_incidents.case_outcome = 'true_positive'` | Safe to sum across tenants/months |
| False positives | `analytics.kpi_monthly.false_positives` | tenant + month | Count of alerts in the month where `fact_alerts.resolution = 'false_positive'` | Safe to sum across tenants/months |
| False positive rate | `analytics.kpi_monthly.false_positive_rate` plus helpers `false_positives` and `resolved_tp_fp_alerts` | tenant + month | `false_positives / resolved_tp_fp_alerts`; denominator excludes alerts resolved as `undetermined` or `benign` | For multi-tenant or multi-month cards, build a custom expression from summed helper fields instead of averaging the rate column |
| True positive rate | `analytics.kpi_monthly.true_positive_rate` plus helpers `true_positive_alerts` and `resolved_tp_fp_alerts` | tenant + month | `true_positive_alerts / resolved_tp_fp_alerts` | Use summed helpers for aggregate views |
| Incident escalation rate | `analytics.kpi_monthly.incident_escalation_rate` plus helpers `escalated_alerts` and `total_alert_volume` | tenant + month | `escalated_alerts / total_alert_volume` | Use summed helpers for aggregate views |
| MTTD | `analytics.kpi_monthly.mean_mttd_minutes` plus helpers `total_mttd_minutes` and `mttd_incident_count` | tenant + month | Average incident `first_alert_at - occurred_at` in minutes for incidents with a linked alert | Use summed helpers for aggregate views |
| MTTR | `analytics.kpi_monthly.mean_mttr_minutes` plus helpers `total_mttr_minutes` and `mttr_incident_count` | tenant + month | Average incident `closed_at - opened_at` in minutes for closed incidents | Use summed helpers for aggregate views |
| Customer systems under monitoring | `analytics.kpi_monthly.systems_under_monitoring` | tenant + month | Count of systems active at the end of the month based on `fact_customer_systems` intervals | Safe to sum across tenants for month-level totals |
| Alerts reviewed per analyst per shift | `analytics.alert_reviews_by_shift.reviewed_alert_count` | shift date + shift + tenant + analyst | Count of alerts with `reviewed_at` populated, bucketed into UTC shifts | Build directly from `alert_reviews_by_shift` |
| Automatically closed incidents | `analytics.kpi_monthly.automatically_closed_incidents` | tenant + month | Count of incidents where `closure_mode = 'automation'` | Safe to sum |
| Total alert volume | `analytics.kpi_monthly.total_alert_volume` | tenant + month | Count of alert facts by event month | Safe to sum |
| Alert volume by source | `analytics.alert_volume_by_source_monthly.alert_count` | tenant + month + source product | Count of alert facts by event month and product | Build directly from `alert_volume_by_source_monthly` |

## Canonical Metabase sources

| Table | Intended use | Primary filters | Default charts | Presentation fields | Drill-through detail |
| --- | --- | --- | --- | --- | --- |
| `analytics.kpi_monthly` | Executive KPI cards and month trends | `metric_month`, `tenant_id` | Number, line, bar | KPI fields and helper numerator/denominator fields | None |
| `analytics.alert_volume_by_source_monthly` | Alert source mix and monthly source trend | `metric_month`, `tenant_id`, `source_product` | Stacked bar, line | `metric_month`, `source_product`, `alert_count` | None |
| `analytics.alert_reviews_by_shift` | Analyst workload by shift | `shift_date`, `tenant_id`, `shift_name`, `analyst` | Grouped bar, table | `shift_date`, `shift_name`, `analyst`, `reviewed_alert_count` | None |
| `analytics.fact_incidents` | Incident drill-through and slice-and-dice | `tenant_id`, `severity`, `status`, `case_outcome`, `closure_mode`, `opened_at` | Table | `severity`, `status`, `case_outcome`, `closure_mode`, `opened_at`, `closed_at` | `source_case_id`, `assigned_analyst`, `closed_by`, `first_alert_at`, `mttd_minutes`, `mttr_minutes` |
| `analytics.fact_alerts` | Alert drill-through and ad hoc review detail | `tenant_id`, `source_product`, `severity`, `triage_status`, `resolution`, `event_at` | Table | `source_product`, `detection_name`, `severity`, `triage_status`, `resolution`, `event_at` | `source_alert_id`, `system_id`, `linked_case_id`, `reviewed_at`, `reviewed_by_analyst`, `review_shift_name` |
| `analytics.fact_automation_runs` | Automation drill-through | `tenant_id`, `workflow_name`, `result_status`, `started_at` | Table | `workflow_name`, `result_status`, `started_at`, `runtime_seconds`, `auto_closed_incident` | `source_run_id`, `related_alert_id`, `related_case_id`, `ended_at` |
| `analytics.fact_customer_systems` | Monitored-system drill-through | `tenant_id`, `source_product`, `still_monitored`, `monitored_from` | Table | `source_product`, `hostname`, `monitored_from`, `monitored_to`, `still_monitored` | `system_id` |

Use the four fact tables for detail pages and drill-through only. Top-level KPI scorecards
and trends should start from `kpi_monthly`, `alert_volume_by_source_monthly`, or
`alert_reviews_by_shift`.

## Metabase metadata setup

Configure these fields in Metabase model metadata before building the dashboard:

- `kpi_monthly.metric_month`: Date
- `kpi_monthly.false_positive_rate`, `kpi_monthly.true_positive_rate`, `kpi_monthly.incident_escalation_rate`: Percentage
- `kpi_monthly.mean_mttd_minutes`, `kpi_monthly.mean_mttr_minutes`, `kpi_monthly.total_mttd_minutes`, `kpi_monthly.total_mttr_minutes`: Number
- `kpi_monthly.tenant_id`, `alert_volume_by_source_monthly.source_product`, `alert_reviews_by_shift.shift_name`, `fact_incidents.severity`, `fact_alerts.triage_status`: Category
- `fact_incidents.source_case_id`, `fact_alerts.source_alert_id`, `fact_automation_runs.source_run_id`, `fact_customer_systems.system_id`: Entity key / ID
- `fact_incidents.occurred_at`, `fact_incidents.opened_at`, `fact_incidents.closed_at`, `fact_alerts.event_at`, `fact_alerts.reviewed_at`, `fact_automation_runs.started_at`, `fact_automation_runs.ended_at`, `fact_customer_systems.monitored_from`, `fact_customer_systems.monitored_to`: DateTime

Recommended dashboard filters:

- global month filter on `kpi_monthly.metric_month`
- global tenant filter on `tenant_id`
- source-product filter only for source-mix and alert drill-through cards
- analyst and shift filters only for workload cards

## Dashboard build order

1. KPI scorecards
   Use `analytics.kpi_monthly`.
   For additive KPIs (`true_positive_incidents`, `false_positives`, `automatically_closed_incidents`, `total_alert_volume`, `systems_under_monitoring`) summarize with `Sum`.
   For rate cards covering multiple tenants, use query-builder custom expressions:
   `Sum([False positives]) / Sum([Resolved TP/FP alerts])`,
   `Sum([True positive alerts]) / Sum([Resolved TP/FP alerts])`,
   `Sum([Escalated alerts]) / Sum([Total alert volume])`.
   For MTTD and MTTR cards covering multiple tenants, use:
   `Sum([Total MTTD minutes]) / Sum([MTTD incident count])` and
   `Sum([Total MTTR minutes]) / Sum([MTTR incident count])`.

2. Monthly trend of total alerts
   Use `analytics.kpi_monthly`, group by `metric_month`, summarize `Sum(total_alert_volume)`, chart as line.

3. Monthly trend of incidents
   Use `analytics.kpi_monthly`, group by `metric_month`, summarize `Sum(incidents_per_month)`, chart as line.

4. Monthly trend of TP/FP/escalation rates
   Use `analytics.kpi_monthly`, group by `metric_month`, then build three custom expressions from summed helper fields:
   `Sum([False positives]) / Sum([Resolved TP/FP alerts])`,
   `Sum([True positive alerts]) / Sum([Resolved TP/FP alerts])`,
   `Sum([Escalated alerts]) / Sum([Total alert volume])`.
   Chart as multi-series line.

5. Monthly systems under monitoring
   Use `analytics.kpi_monthly`, group by `metric_month`, summarize `Sum(systems_under_monitoring)`, chart as line or bar.

6. Monthly automatically closed incidents
   Use `analytics.kpi_monthly`, group by `metric_month`, summarize `Sum(automatically_closed_incidents)`, chart as bar.

7. Alert volume by source product
   Use `analytics.alert_volume_by_source_monthly`, group by `metric_month`, breakout by `source_product`, summarize `Sum(alert_count)`, chart as stacked bar or stacked area.

8. Reviewed alerts by analyst and shift
   Use `analytics.alert_reviews_by_shift`, filter to a date range, breakout by `analyst` and optionally `shift_name`, summarize `Sum(reviewed_alert_count)`, chart as grouped bar.

9. Incident and alert drill-through tables
   Build separate table questions from `analytics.fact_incidents` and `analytics.fact_alerts`.
   Keep IDs, timestamps, tenant, severity, status/resolution, and lineage fields visible.
   Link these tables from the executive dashboard rather than using them for scorecards.

## Guardrails

- Do not point top-level Metabase cards at `raw`.
- Do not use native SQL for the main KPI cards or trend charts.
- Do not average precomputed rate columns across multiple tenants or months; always use the helper numerator/denominator fields for aggregated views.
- Treat the fact tables as drill-through sources, not as places to redefine KPI semantics in Metabase.
