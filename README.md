# Azure Snapshot Manager

Azure Snapshot Manager is a Python script that allows you to search for and manage Azure snapshots across multiple subscriptions. It provides functionality to search for snapshots based on date range and keywords, and optionally delete the found snapshots.

![GitHub release (latest by date)](https://img.shields.io/github/v/release/dagz55/azure-snapshot-finder)
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/dagz55/azure-snapshot-finder/ci.yml)
![GitHub License](https://img.shields.io/github/license/dagz55/azure-snapshot-finder)
![GitHub contributors](https://img.shields.io/github/contributors/dagz55/azure-snapshot-finder)
![GitHub forks](https://img.shields.io/github/forks/dagz55/azure-snapshot-finder?style=social)
![GitHub stars](https://img.shields.io/github/stars/dagz55/azure-snapshot-finder?style=social)
![GitHub issues](https://img.shields.io/github/issues/dagz55/azure-snapshot-finder)
![GitHub Release Date](https://img.shields.io/github/release-date/dagz55/azure-snapshot-finder)

[![Discord](https://img.shields.io/discord/1283470437761810535?label=Discord&logo=discord)](https://discord.gg/9vDsFXbp)

Join our Discord community to discuss and collaborate with other users.

## Features

- Search for snapshots across multiple Azure subscriptions
- Filter snapshots by date range and keywords
- Display detailed information about found snapshots in a single, dynamic, growing table for all subscriptions
- Export search results to CSV
- Delete found snapshots with enhanced progress tracking and error handling
- Comprehensive logging of all operations, including detailed deletion logs
- Automatic handling of Azure login process
- Optimized performance for handling large numbers of snapshots across multiple subscriptions

## Prerequisites

- Python 3.7 or higher
- Azure CLI installed and configured
- Required Python packages: `rich`, `azure-cli`

## Installation

1. Clone this repository or download the `get_del_snap.py` script.
2. Install the required packages:

```
pip install rich azure-cli
```

## Usage

Run the script using Python:

```
python get_del_snap.py
```

Follow the interactive prompts to:

1. Log in to Azure (if not already logged in)
2. Specify the date range for snapshot search
3. Enter an optional keyword filter
4. View search results in a unified, dynamic table across all subscriptions
5. Export results to CSV (optional)
6. Delete found snapshots (optional) with detailed progress tracking

## Logging

The script logs all operations to a file named `azure_snapshot_manager_YYYYMMDD_USERNAME.log` in the same directory as the script. Additionally, if snapshots are deleted, a detailed deletion log is created in the `logs` directory.

## Security Note

This script requires Azure CLI authentication and will use your current Azure CLI login. Ensure you have the necessary permissions to list and delete snapshots in the subscriptions you're working with.

## Caution

The deletion feature permanently removes snapshots. Use this feature with caution and ensure you have necessary backups before deleting any snapshots. The script provides detailed information about the snapshots to be deleted and requires confirmation before proceeding.

## Contributing

Contributions to improve the Azure Snapshot Manager are welcome. Please feel free to submit pull requests or create issues for bugs and feature requests.

## License

This project is licensed under the MIT License.

## Changelog

For a detailed list of changes and version history, please refer to the [CHANGELOG.md](CHANGELOG.md) file.

## Version

Current version: 1.3.1

## Prerequisites

- Python 3.7+
- Azure CLI installed and configured
- Required Python packages (install using `pip install -r requirements.txt`):
  - asyncio
  - rich

## Notes

- The script requires appropriate Azure permissions to list and delete snapshots.
- Use caution when deleting snapshots, as this action cannot be undone.
- The script now handles subscription permission issues more gracefully, logging warnings instead of errors for subscriptions where the user lacks necessary permissions.