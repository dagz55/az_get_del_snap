# Azure Snapshot Manager

Azure Snapshot Manager is a Python script that helps manage Azure snapshots across multiple subscriptions. It allows users to search for snapshots within a specified date range, filter by keyword, and optionally delete snapshots.

## Features

- Search for snapshots across multiple Azure subscriptions
- Filter snapshots by date range and keyword
- Display snapshot details in a user-friendly table format
- Export snapshot information to CSV
- Delete snapshots with proper error handling and logging
- Automatic handling of Azure login and subscription switching
- Improved error handling for subscription permission issues

## Prerequisites

- Python 3.7+
- Azure CLI installed and configured
- Required Python packages (install using `pip install -r requirements.txt`):
  - asyncio
  - rich

## Usage

1. Ensure you have the Azure CLI installed and you're logged in (`az login`).
2. Run the script:

   ```
   python get_del_snap.py
   ```

3. Follow the prompts to:
   - Enter a date range for snapshot search
   - Optionally enter a keyword filter
   - Choose whether to export results to CSV
   - Choose whether to delete found snapshots

## Output

The script provides:
- A live progress bar during the search process
- A summary table of snapshots found per subscription
- Detailed tables for each subscription's snapshots
- Option to export results to CSV
- Deletion confirmation and results (if chosen)

## Logging

The script logs its activities to a file named `azure_snapshot_manager_YYYYMMDD_username.log` in the current directory. It now includes improved error handling and logging for subscription permission issues.

## Notes

- The script requires appropriate Azure permissions to list and delete snapshots.
- Use caution when deleting snapshots, as this action cannot be undone.
- The script now handles subscription permission issues more gracefully, logging warnings instead of errors for subscriptions where the user lacks necessary permissions.

## Contributing

Contributions to improve the Azure Snapshot Manager are welcome. Please submit a pull request or create an issue to discuss proposed changes.

## License

This project is licensed under the MIT License - see the LICENSE file for details.