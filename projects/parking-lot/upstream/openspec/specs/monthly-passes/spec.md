# monthly-passes Specification

## Purpose
TBD - created by archiving change monthly-passes. Update Purpose after archive.
## Requirements
### Requirement: List monthly passes
An authenticated user SHALL be able to list monthly passes, optionally
filtered by vehicle.

#### Scenario: Fetch all monthly passes
- **WHEN** an authenticated user requests the monthly pass list
- **THEN** the system returns all passes with id, vehicle id, start date, end
  date, amount, and active flag

#### Scenario: Filter by vehicle
- **WHEN** an authenticated user requests monthly passes filtered by vehicle
- **THEN** the system returns only the passes for that vehicle

### Requirement: Admin creates a monthly pass
An admin SHALL be able to create a monthly pass for an existing vehicle with
a start date, an end date after the start date, and an amount.

#### Scenario: Create a monthly pass
- **WHEN** an admin creates a monthly pass for an existing vehicle with a
  valid date range
- **THEN** the system stores it and returns it with an id

### Requirement: Monthly pass validation
The system SHALL reject a monthly pass for an unknown vehicle or with an end
date not strictly after the start date.

#### Scenario: Unknown vehicle
- **WHEN** a monthly pass is created for a vehicle id that does not exist
- **THEN** the system rejects the request with a not-found error

#### Scenario: Invalid date range
- **WHEN** a monthly pass is created or updated with an end date on or before
  the start date
- **THEN** the system rejects it with a validation error

### Requirement: Admin updates a monthly pass
An admin SHALL be able to update a monthly pass's dates, amount, or active
flag.

#### Scenario: Deactivate a monthly pass
- **WHEN** an admin sets a monthly pass's active flag to false
- **THEN** the system persists the change

### Requirement: Admin deletes a monthly pass
An admin SHALL be able to delete a monthly pass.

#### Scenario: Delete a monthly pass
- **WHEN** an admin deletes a monthly pass
- **THEN** the pass is removed from the list

### Requirement: Operator cannot manage monthly passes
A non-admin user SHALL NOT be able to create, update, or delete monthly
passes.

#### Scenario: Operator attempts mutation
- **WHEN** an operator attempts to create, update, or delete a monthly pass
- **THEN** the system rejects the request with a forbidden error

### Requirement: Check-out charges zero for an active monthly pass
The system SHALL charge zero at check-out for a vehicle that has an active
monthly pass covering the session's exit date.

#### Scenario: Check out a vehicle with an active pass
- **WHEN** an authenticated user checks out a session for a vehicle with an
  active monthly pass covering the exit date
- **THEN** the system charges an amount of zero for that session

