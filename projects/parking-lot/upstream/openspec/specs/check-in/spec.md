# check-in Specification

## Purpose
TBD - created by archiving change check-in. Update Purpose after archive.
## Requirements
### Requirement: Check in a vehicle
An authenticated user SHALL be able to check in a vehicle by plate, opening a
parking session and optionally attaching evidence photos.

#### Scenario: Check in an existing vehicle
- **WHEN** an authenticated user checks in a vehicle with a known plate and one
  or more photos
- **THEN** the system creates an open parking session with the current time as
  entry time, stores each photo, and returns the session with its photos

#### Scenario: Check in without photos
- **WHEN** an authenticated user checks in a vehicle with a known plate and no
  photos
- **THEN** the system creates the open parking session with no evidence photos

### Requirement: Unknown plate is rejected
The system SHALL reject a check-in for a plate that does not match any
registered vehicle.

#### Scenario: Unknown plate
- **WHEN** a user checks in a plate that has no matching vehicle
- **THEN** the system rejects the request with a not-found error

### Requirement: Duplicate open session is rejected
The system SHALL reject a check-in for a vehicle that already has an open
parking session.

#### Scenario: Vehicle already checked in
- **WHEN** a user checks in a vehicle that already has an open session
- **THEN** the system rejects the request with a conflict error

### Requirement: List open sessions
An authenticated user SHALL be able to list all currently open parking
sessions.

#### Scenario: Fetch open sessions
- **WHEN** an authenticated user requests the open session list
- **THEN** the system returns every session with status open, including vehicle,
  operator, and entry time

### Requirement: Unauthenticated check-in is rejected
The system SHALL reject a check-in request from an unauthenticated caller.

#### Scenario: Missing credentials
- **WHEN** an unauthenticated caller attempts to check in a vehicle
- **THEN** the system rejects the request with an unauthorized error

### Requirement: Offline check-in queues instead of failing
When a check-in attempt fails due to a network failure (not a business-rule
rejection), the system SHALL queue it for automatic replay instead of
failing the operator's action.

#### Scenario: Check in while offline
- **WHEN** an authenticated user checks in a known-plate vehicle (with or
  without photos) while the device has no connectivity
- **THEN** the app persists the photos locally, queues the check-in for
  replay, and shows the session with a pending-sync status instead of an
  error

#### Scenario: Queued check-in replays once online
- **WHEN** connectivity is restored after a check-in was queued
- **THEN** the app resubmits the same plate and photos, and the session
  becomes a normal open session once the server confirms it

#### Scenario: Business-rule rejection still fails immediately
- **WHEN** a check-in is attempted for an unknown plate or a vehicle that
  already has an open session, regardless of connectivity
- **THEN** the system rejects it immediately and does NOT queue it for
  replay

