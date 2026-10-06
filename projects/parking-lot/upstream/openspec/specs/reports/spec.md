# reports Specification

## Purpose
TBD - created by archiving change reports. Update Purpose after archive.
## Requirements
### Requirement: Revenue report
An admin SHALL be able to request a revenue report for a date range, returning
the total charged amount, a breakdown by calendar day, and a breakdown by
vehicle category, computed from closed sessions whose exit time falls within
the range (inclusive, end date treated as end-of-day).

#### Scenario: Fetch revenue for a range
- **WHEN** an admin requests `GET /reports/revenue` with a `start_date` and
  `end_date`
- **THEN** the system returns the total revenue, an amount per calendar day,
  and an amount per category, counting only closed sessions whose exit time
  falls within `[start_date, end_date]`

#### Scenario: Sessions outside the range are excluded
- **WHEN** a closed session's exit time falls before `start_date` or after
  `end_date`
- **THEN** its `amount_charged` is not included in the report total, day
  breakdown, or category breakdown

### Requirement: Occupancy report
An admin SHALL be able to request an occupancy report, returning the count of
currently open parking sessions in total and broken down by vehicle category.

#### Scenario: Fetch current occupancy
- **WHEN** an admin requests `GET /reports/occupancy`
- **THEN** the system returns the total count of open sessions and a count
  per vehicle category

#### Scenario: Closed sessions are excluded from occupancy
- **WHEN** a session has `status=closed`
- **THEN** it is not counted in the occupancy report

### Requirement: Invalid date range rejected
The system SHALL reject a revenue report request where `start_date` is after
`end_date`.

#### Scenario: Start date after end date
- **WHEN** an admin requests `GET /reports/revenue` with `start_date` after
  `end_date`
- **THEN** the system rejects the request with a validation error

### Requirement: Non-admin cannot access reports
A non-admin user SHALL NOT be able to fetch the revenue or occupancy report.

#### Scenario: Operator attempts to fetch a report
- **WHEN** an authenticated operator (non-admin) requests either
  `GET /reports/revenue` or `GET /reports/occupancy`
- **THEN** the system rejects the request with a forbidden error

