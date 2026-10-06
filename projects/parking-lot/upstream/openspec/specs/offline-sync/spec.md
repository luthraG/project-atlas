# offline-sync Specification

## Purpose
TBD - created by archiving change offline-sync. Update Purpose after archive.
## Requirements
### Requirement: Queue an update or delete while offline
When `update` or `delete` on a vehicle, tariff, or category fails with a
network failure, the system SHALL apply the change to the local cache and
queue it for later replay instead of failing the operation.

#### Scenario: Update a vehicle while offline
- **WHEN** an admin updates a vehicle's color while the device has no
  connectivity
- **THEN** the system updates the local cache with the merged result,
  queues the mutation, and returns the merged vehicle without raising an
  error

#### Scenario: Delete a tariff while offline
- **WHEN** an admin deletes a tariff while the device has no connectivity
- **THEN** the system removes the tariff from the local cache, queues the
  mutation, and completes without raising an error

### Requirement: Replay queued mutations on reconnect
The system SHALL replay every queued mutation against the backend once
connectivity is restored, removing each one from the queue only after it
succeeds.

#### Scenario: Connectivity restored
- **WHEN** the device regains connectivity after queuing an update
- **THEN** the system sends the queued update to the backend and removes it
  from the queue on success

### Requirement: One failed replay does not block others
A queued mutation that still fails to replay (e.g. connectivity flaps again
mid-flush) SHALL remain queued without preventing any other queued mutation
from being replayed in the same pass.

#### Scenario: One poison entry among several
- **WHEN** the queue holds two independent mutations and replaying the
  first still fails with a network error
- **THEN** the system leaves the first mutation queued and still replays
  and clears the second mutation

### Requirement: Scope limited to update/delete on reference data
Only `update` and `delete` mutations on vehicles, tariffs, and categories
SHALL be queued. Check-in, check-out, monthly-passes, and every `create`
mutation SHALL remain unaffected (remote-only, unchanged failure behavior).

#### Scenario: Check-out stays remote-only
- **WHEN** an operator attempts to check out a vehicle while offline
- **THEN** the system rejects the request immediately (no queuing), since
  `exit_time` must be captured at the moment of closing

#### Scenario: Vehicle creation stays remote-only
- **WHEN** an admin attempts to create a new vehicle while offline
- **THEN** the system rejects the request immediately (no queuing), since a
  create requires a server-assigned id

### Requirement: Outbox replays queued check-ins and check-outs
The sync outbox SHALL support queuing and replaying check-in creates and
check-out closes, in addition to the existing vehicle/tariff/category
update/delete entries.

#### Scenario: One stuck entry does not block another
- **WHEN** a queued check-in and a queued check-out are both pending and
  one keeps failing with a network failure during a flush
- **THEN** the other entry is still replayed in the same flush pass

#### Scenario: Successful check-in replay cleans up local photo storage
- **WHEN** a queued check-in is successfully replayed
- **THEN** the app deletes the photos it had persisted locally for that
  queued entry

