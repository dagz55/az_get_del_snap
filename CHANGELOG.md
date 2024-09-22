# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.1] - 2024-09-23

### Added
- Improved error handling for subscription permission issues
- Warning log for subscriptions where user lacks snapshot listing permissions

### Changed
- Updated `get_snapshots` function to handle AuthorizationFailed errors gracefully
- Improved logging to reduce unnecessary error messages

## [1.3.0] - 2024-09-22

### Added
- Initial release of Azure Snapshot Manager
- Search functionality for Azure snapshots across multiple subscriptions
- Date range and keyword filtering for snapshots
- Live progress display using rich library
- CSV export option for search results
- Snapshot deletion capability with proper error handling
- Detailed logging of all operations
- Automatic Azure login check and subscription management

## [1.2.1] - 2024-09-20
### Changed
- Refactored the script to use a single, growing table for displaying snapshot search results across all subscriptions.
- Updated the main function to create and update a unified snapshot table.
- Improved the Live display to show the growing table throughout the entire process.

### Fixed
- Resolved the issue of creating multiple tables for each subscription.

## [1.2.0] - 2024-09-20
### Added
- Integrated snapshot deletion functionality into the main script.
- Enhanced progress tracking with detailed progress bars for each operation.
- Improved error handling and logging for snapshot deletion process.
- Added option to delete found snapshots after the search process.

### Changed
- Refactored the script to use a single, growing table for displaying snapshot search results.
- Improved overall script structure to align more closely with gf_snap.py while maintaining deletion functionality.
- Updated logging configuration for better consistency and readability.

### Improved
- Enhanced user interface with more detailed result displays and progress indicators.
- Optimized performance for handling large numbers of snapshots across multiple subscriptions.

## [1.1.0] - 2024-09-13
### Added
- Azure login validation before executing main functions.
- Automatic `az login` process if the user is not logged in.

## [1.0.0] - 2024-09-11
### Added
- Initial release of Azure Snapshot Finder.
- Integrated Azure CLI commands to fetch snapshots across multiple subscriptions.
- Prompt for start and end dates to filter snapshots.
- Optional keyword filter to search snapshots by name.
- Rich console output using progress bars, tables, and status updates.
- Snapshot details displayed in a table, including name, resource group, creation date, age, and status.
- Color-coded age of snapshots (green, yellow, red).
- Logs saved to a file with detailed information on CLI commands and errors.
- Optional export to CSV functionality.

## Example output from generated *.csv file:

name,resourceGroup,timeCreated,createdBy,subscription,diskState,id
RH_CHG0650053_ebis-perimeter-dev-proxy-vm-dgm011a5f_20240911075519,AZ-RESIBM-NONPROD-01-EBIS-DEV-WESTUS-RG-01,2024-09-11T07:57:28.4164315+00:00,,az-resibm-nonprod-01,Unattached,/subscriptions/3f64d803-6d97-4d15-aad3-aaac35bd5c3f/resourceGroups/AZ-RESIBM-NONPROD-01-EBIS-DEV-WESTUS-RG-01/providers/Microsoft.
RH_CHG0650053_ebis-perimeter-dev-proxy-vm-dgm011a60_20240911075519,AZ-RESIBM-NONPROD-01-EBIS-DEV-WESTUS-RG-01,2024-09-11T07:57:42.0416825+00:00,,az-resibm-nonprod-01,Unattached,/subscriptions/3f64d803-6d97-4d15-aad3-aaac35bd5c3f/resourceGroups/AZ-RESIBM-NONPROD-01-EBIS-DEV-WESTUS-RG-01/providers/Microsoft.
RH_CHG0650053_ebis-seas-dev-app-vm-dgm011a5e_20240911075519,AZ-RESIBM-NONPROD-01-EBIS-DEV-WESTUS-RG-01,2024-09-11T07:57:14.7757025+00:00,,az-resibm-nonprod-01,Unattached,/subscriptions/3f64d803-6d97-4d15-aad3-aaac35bd5c3f/resourceGroups/AZ-RESIBM-NONPROD-01-EBIS-DEV-WESTUS-RG-01/providers/Microsoft.Compute
RH_CHG0650053_ebis-sterling-dev-app-vm-dgm011a55_20240911075519,AZ-RESIBM-NONPROD-01-EBIS-DEV-WESTUS-RG-01,2024-09-11T07:56:46.9784196+00:00,,az-resibm-nonprod-01,Unattached,/subscriptions/3f64d803-6d97-4d15-aad3-aaac35bd5c3f/resourceGroups/AZ-RESIBM-NONPROD-01-EBIS-DEV-WESTUS-RG-01/providers/Microsoft.Com
RH_CHG0650053_ebis-sterling-dev-app-vm-dgm011a56_20240911075519,AZ-RESIBM-NONPROD-01-EBIS-DEV-WESTUS-RG-01,2024-09-11T07:57:00.9785631+00:00,,az-resibm-nonprod-01,Unattached,/subscriptions/3f64d803-6d97-4d15-aad3-aaac35bd5c3f/resourceGroups/AZ-RESIBM-NONPROD-01-EBIS-DEV-WESTUS-RG-01/providers/Microsoft.Com
RH_PATCH_CHG0650053_dgm01117e,AZ-PHIAPP-NONPROD-01-EBSE-DEV-WESTUS-RG-01,2024-09-11T01:04:15.2418214+00:00,,az-phiapp-nonprod-01,Unattached,/subscriptions/bcf4edc6-1301-4194-b225-89ef5b975474/resourceGroups/AZ-PHIAPP-NONPROD-01-EBSE-DEV-WESTUS-RG-01/providers/Microsoft.Compute/snapshots/RH_PATCH_CHG0650053
RH_PATCH_CHG0641776_pgm0119e5,AZ-CORE-PROD-01-IMCV-PROD-EASTUS-RG-01,2024-09-04T16:22:38.8178869+00:00,,az-core-prod-01,Unattached,/subscriptions/5cdb8a38-5edf-4090-9e49-c28ecb16d982/resourceGroups/AZ-CORE-PROD-01-IMCV-PROD-EASTUS-RG-01/providers/Microsoft.Compute/snapshots/RH_PATCH_CHG0641776_pgm0119e5
RH_PATCH_CHG0641776_pgm0119e6,AZ-CORE-PROD-01-IMCV-PROD-EASTUS-RG-01,2024-09-04T16:23:07.6144211+00:00,,az-core-prod-01,Unattached,/subscriptions/5cdb8a38-5edf-4090-9e49-c28ecb16d982/resourceGroups/AZ-CORE-PROD-01-IMCV-PROD-EASTUS-RG-01/providers/Microsoft.Compute/snapshots/RH_PATCH_CHG0641776_pgm0119e6