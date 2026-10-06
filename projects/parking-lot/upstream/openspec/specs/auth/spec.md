# auth Specification

## Purpose
TBD - created by archiving change auth. Update Purpose after archive.
## Requirements
### Requirement: Login with username and PIN
The system SHALL authenticate an operator by username and PIN and SHALL create a
session containing the user identity and role when credentials are valid.

#### Scenario: Successful login
- **WHEN** an operator submits a valid username and PIN
- **THEN** the system creates a session with the user id, username, and role

#### Scenario: Invalid credentials
- **WHEN** an operator submits an unknown username or a wrong PIN
- **THEN** the system does not create a session and returns an authentication failure

### Requirement: Session persistence
The system SHALL persist the current session locally so that the operator remains
authenticated across app restarts and while offline.

#### Scenario: Session restored after restart
- **WHEN** the app starts with a previously stored session
- **THEN** the system restores the session without prompting for credentials

#### Scenario: No session on first launch
- **WHEN** the app starts with no stored session
- **THEN** the system reports an unauthenticated state

### Requirement: Logout
The system SHALL clear the current session when the operator logs out.

#### Scenario: Operator logs out
- **WHEN** the operator triggers logout
- **THEN** the session is removed and the app returns to the unauthenticated state

### Requirement: Role availability
The system SHALL expose the operator's role (`admin` or `operator`) as part of the
authenticated session so the app can gate features by role.

#### Scenario: Role is part of the session
- **WHEN** a session is created or restored
- **THEN** the session includes a role value of either `admin` or `operator`

### Requirement: PIN is never stored in plaintext
The system SHALL store only a hashed form of the PIN, never the plaintext.

#### Scenario: Storage contains no plaintext PIN
- **WHEN** a user record or local cache is inspected
- **THEN** the plaintext PIN is not present and only a hash is stored

