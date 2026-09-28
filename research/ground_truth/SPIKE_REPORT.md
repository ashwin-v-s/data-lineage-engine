# ProvSQL Feasibility Spike

## Date

2026-09-23

## Environment

- OS: Windows
- PostgreSQL: 18.6
- PostgreSQL port: 5432
- Database: kairos
- Python: 3.13.5
- OpenLineage Python: 1.53.0

## Objective

Determine whether ProvSQL can be installed and used for the KAIROS
independent ground-truth path.

## Test Case

Input table:

`employees_a`

Columns:

- country
- salary

ETL transformation:

```sql
CREATE TABLE out_adjusted AS
SELECT country,
       CASE
           WHEN country = 'US' THEN salary
           ELSE 0
       END AS adjusted_salary
FROM employees_a;