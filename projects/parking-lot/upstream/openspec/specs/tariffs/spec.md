# tariffs Specification

## Purpose
TBD - created by archiving change tariffs. Update Purpose after archive.
## Requirements
### Requirement: List tariffs
An authenticated user SHALL be able to list tariffs, optionally filtered by category.

#### Scenario: Fetch all tariffs
- **WHEN** an authenticated user requests the tariff list
- **THEN** the system returns all tariffs with id, category id, type, amount, time
  window, and active flag

### Requirement: Admin creates a tariff
An admin SHALL be able to create a tariff with a category, type, positive amount,
and — for nightly tariffs — a time window.

#### Scenario: Create an hourly tariff
- **WHEN** an admin creates an hourly tariff with a positive amount
- **THEN** the system stores it and returns it with an id

#### Scenario: Create a nightly tariff with a window
- **WHEN** an admin creates a nightly tariff with a start and end time
- **THEN** the system stores the time window along with the tariff

### Requirement: Tariff validation
The system SHALL reject tariffs with a non-positive amount, a nightly tariff without
a window, or a non-nightly tariff that carries a time window.

#### Scenario: Non-positive amount
- **WHEN** a tariff is created or updated with an amount of zero or less
- **THEN** the system rejects it with a validation error

#### Scenario: Nightly without window
- **WHEN** a nightly tariff is created without a start and end time
- **THEN** the system rejects it with a validation error

### Requirement: Admin updates a tariff
An admin SHALL be able to update a tariff's type, amount, time window, or active flag.

#### Scenario: Deactivate a tariff
- **WHEN** an admin sets a tariff's active flag to false
- **THEN** the system persists the change

### Requirement: Admin deletes a tariff
An admin SHALL be able to delete a tariff.

#### Scenario: Delete a tariff
- **WHEN** an admin deletes a tariff
- **THEN** the tariff is removed from the list

### Requirement: Operator cannot manage tariffs
A non-admin user SHALL NOT be able to create, update, or delete tariffs.

#### Scenario: Operator attempts mutation
- **WHEN** an operator attempts to create, update, or delete a tariff
- **THEN** the system rejects the request with a forbidden error

