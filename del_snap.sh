#!/bin/bash

# Check if the correct number of arguments is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <file_with_snapshot_ids>"
    exit 1
fi

file_with_snapshot_ids=$1

# Check if the file exists
if [ ! -f "$file_with_snapshot_ids" ]; then
    echo "Error: File '$file_with_snapshot_ids' not found."
    exit 1
fi

# Read the file line by line
while IFS= read -r snapshot_id || [[ -n "$snapshot_id" ]]; do
    # Skip empty lines
    [ -z "$snapshot_id" ] && continue
    
    # Delete the snapshot
    if az snapshot delete --ids "$snapshot_id" --no-wait; then
        echo "Snapshot with ID '$snapshot_id' has been successfully deleted."
    else
        echo "Failed to delete snapshot with ID '$snapshot_id'. Please check the ID and your permissions."
    fi
done < "$file_with_snapshot_ids"
