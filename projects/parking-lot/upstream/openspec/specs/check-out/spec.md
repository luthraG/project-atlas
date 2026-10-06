# check-out Specification

## Purpose
TBD - created by archiving change check-out. Update Purpose after archive.
## Requirements
### Requirement: Close an open session and compute its fare
An authenticated user SHALL be able to check out an open parking session by
its id, closing it with the current time as exit time and charging the fare
computed by the `billing` capability.

#### Scenario: Check out an open session
- **WHEN** an authenticated user checks out a session that is currently open
- **THEN** the system stamps the session's exit time as the current time,
  computes the fare for the elapsed stay via the category's tariffs, sets the
  session's status to closed, records the charged amount and a generated
  ticket number, and returns the updated session

### Requirement: Unknown session is rejected
The system SHALL reject a check-out for a session id that does not exist.

#### Scenario: Unknown session id
- **WHEN** a user checks out a session id that has no matching parking
  session
- **THEN** the system rejects the request with a not-found error

### Requirement: Already-closed session is rejected
The system SHALL reject a check-out for a session that is already closed.

#### Scenario: Session already checked out
- **WHEN** a user checks out a session whose status is already closed
- **THEN** the system rejects the request with a conflict error

### Requirement: Unauthenticated check-out is rejected
The system SHALL reject a check-out request from an unauthenticated caller.

#### Scenario: Missing credentials
- **WHEN** an unauthenticated caller attempts to check out a session
- **THEN** the system rejects the request with an unauthorized error

### Requirement: Check-out accepts a client-supplied exit time
The system SHALL accept an optional client-supplied exit time for a
check-out and use it instead of the server's current time when present.

#### Scenario: Client exit time supplied
- **WHEN** a check-out request includes a `client_exit_time`
- **THEN** the system uses that time (not the current server time) as the
  session's `exit_time` for fare calculation and storage

#### Scenario: Client exit time omitted
- **WHEN** a check-out request omits `client_exit_time`
- **THEN** the system uses the current server time, unchanged from today's
  behavior

### Requirement: Offline check-out queues instead of failing
When a check-out attempt fails due to a network failure (not a
business-rule rejection), the system SHALL capture the device's local time
at that moment and queue the check-out for automatic replay using that
captured time, instead of failing the operator's action.

#### Scenario: Check out while offline
- **WHEN** an authenticated user checks out an open session while the
  device has no connectivity
- **THEN** the app captures the current device time, queues the check-out
  for replay with that time, and shows a pending-sync result with no
  amount or ticket number yet

#### Scenario: Queued check-out replays with the original attempt time
- **WHEN** connectivity is restored after a check-out was queued
- **THEN** the app resubmits the check-out with the originally captured
  exit time, so the fare reflects the moment the operator acted, not the
  moment connectivity returned

#### Scenario: Business-rule rejection still fails immediately
- **WHEN** a check-out is attempted for a session that does not exist or is
  already closed, regardless of connectivity
- **THEN** the system rejects it immediately and does NOT queue it for
  replay

