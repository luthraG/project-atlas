# plate-scanning Specification

## Purpose
TBD - created by archiving change plate-scanning. Update Purpose after archive.
## Requirements
### Requirement: Scan a plate from the camera
An authenticated user SHALL be able to capture a vehicle plate using the device
camera and on-device OCR, receiving a normalized candidate plate string.

#### Scenario: Successful OCR scan
- **WHEN** the user captures a clear image of a plate
- **THEN** the OCR adapter extracts text, the system normalizes it, and returns the
  candidate plate in uppercase with no surrounding whitespace

#### Scenario: OCR returns no usable text
- **WHEN** the OCR adapter returns no text or text that fails plate validation
- **THEN** the system reports a scan failure and prompts the user to retry or enter
  the plate manually

### Requirement: Manual plate entry fallback
The system SHALL provide a manual plate entry that always succeeds in producing a
normalized plate, so the operator is never blocked by camera or OCR failures.

#### Scenario: Operator enters plate manually
- **WHEN** the user types a plate and submits it
- **THEN** the system normalizes the input and returns it as the candidate plate

### Requirement: Plate normalization and validation
The system SHALL normalize any captured or entered plate to uppercase with no
internal spaces or surrounding whitespace, and SHALL reject empty plates.

#### Scenario: Normalize a scanned plate
- **WHEN** the OCR returns "  abc 123 "
- **THEN** the system produces "ABC123"

#### Scenario: Reject an empty plate
- **WHEN** the OCR or manual entry yields an empty string after normalization
- **THEN** the system rejects it with a validation error

### Requirement: Scanner is pluggable
The plate scanning capability SHALL expose an abstract `PlateScanner` port so the
OCR implementation can be replaced without affecting the scanning flow.

#### Scenario: Replace the OCR adapter
- **WHEN** a different scanner implementation is registered in the DI container
- **THEN** the scanning flow uses the new implementation without code changes in the
  cubit or presentation layer

### Requirement: Scan result is a candidate, not a confirmation
The scan result SHALL be a candidate plate that the operator can review and edit
before it is used, preventing OCR errors from silently creating wrong lookups.

#### Scenario: Operator edits a scanned plate
- **WHEN** the OCR returns a candidate plate with a likely error
- **THEN** the operator can edit the candidate in a text field before confirming

