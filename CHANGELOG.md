# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/) and this project adheres to [Semantic Versioning](http://semver.org).

## [Unreleased]

### Added
- Added a custom User-Agent header to allow OctoPrint-Volta plugins to be identified. This can help in preventing unwanted clients to connect to the remote server.
- Added an API URL to the configuration allowing for modifying the Volta Server instance (for testing or deployment purposes).

### Changed
- Replaced the print job success/failure state with a more descriptive status. This makes handling of the print job status easier on the frontend side.
- Refactored the way the verification to the Volta Server is performed. Now it will check at each (significant) event if verification has already been done or not. Previously it was only executed at startup and save but didn't work correctly (especiall at the 'save' event).
- Ensured the internal printer_state is initialized early.

### Fixed

### Removed
- Removed the printer element of the internal state structure as this is part of the encrypted printer ID.


## [0.1.1] - 2018-11-28

### Changed
- Relocated the verification of the API Token earlier in the boot process. It would otherwise render errors when generating the printer ID.

### Removed
- Removed Random Class.
- Removed unused exception parameter.


## [0.1.0] - 2018-11-28
- Initial Release