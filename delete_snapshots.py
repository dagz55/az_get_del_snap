# delete_snapshots.py

import os
import time
import subprocess
import json
import logging
import traceback
from datetime import datetime
from typing import List, Dict, Any

# Set up logging
logging.basicConfig(filename='azure_manager.log', level=logging.DEBUG,
                    format='%(asctime)s:%(levelname)s:%(message)s')

def run_az_command(command):
    try:
        if isinstance(command, list):
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            return result.stdout.strip()
        else:
            with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
                stdout, stderr = process.communicate()
            if process.returncode != 0:
                return f"Error: {stderr.strip()}"
            return stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {e.cmd}. Error: {e.stderr}")
        raise
    except Exception as e:
        logging.error(f"Error in run_az_command: {str(e)}")
        return f"Error: {str(e)}"

def check_az_login():
    try:
        result = run_az_command("az account show")
        if result.startswith("Error:"):
            logging.warning("Not logged in to Azure.")
            return False
        return True
    except Exception as e:
        logging.error(f"Error checking Azure login status: {str(e)}")
        return False

def get_subscription_names():
    command = "az account list --query '[].{id:id, name:name}' -o json"
    result = run_az_command(command)
    if result and not result.startswith("Error:"):
        subscriptions = json.loads(result)
        return {sub['id']: sub['name'] for sub in subscriptions}
    return {}

def switch_subscription(subscription, current_subscription):
    if subscription != current_subscription:
        try:
            run_az_command(['az', 'account', 'set', '--subscription', subscription])
            logging.info(f"Switched to subscription: {subscription}")
            return subscription
        except Exception as e:
            logging.error(f"Failed to switch to subscription {subscription}: {str(e)}")
            raise
    return current_subscription

def get_resource_groups_from_snapshots(snapshot_ids):
    resource_groups = set()
    for snapshot_id in snapshot_ids:
        parts = snapshot_id.split('/')
        if len(parts) >= 5:
            resource_groups.add((parts[2], parts[4]))  # (subscription_id, resource_group)
    return resource_groups

def check_and_remove_scope_locks(resource_groups):
    removed_locks = []
    current_subscription = None
    for subscription_id, resource_group in resource_groups:
        current_subscription = switch_subscription(subscription_id, current_subscription)
        command = f"az lock list --resource-group {resource_group} --query '[].{{name:name, level:level}}' -o json"
        locks = json.loads(run_az_command(command))
        for lock in locks:
            if lock['level'] == 'CanNotDelete':
                remove_command = f"az lock delete --name {lock['name']} --resource-group {resource_group}"
                result = run_az_command(remove_command)
                if not result.startswith("Error:"):
                    removed_locks.append((subscription_id, resource_group, lock['name']))
                    logging.info(f"Removed lock '{lock['name']}' from resource group '{resource_group}'")
                else:
                    logging.error(f"Failed to remove lock '{lock['name']}' from resource group '{resource_group}': {result}")
    return removed_locks

def check_snapshot_exists(snapshot_id):
    command = f"az snapshot show --ids {snapshot_id}"
    result = run_az_command(command)
    return not result.startswith("Error:")

def process_snapshot(snapshot_id, subscription_names):
    try:
        parts = snapshot_id.split('/')
        if len(parts) < 9:
            logging.error(f"Invalid snapshot ID format: {snapshot_id}")
            return None, "invalid", (snapshot_id, "Invalid snapshot ID format")

        subscription_id = parts[2]
        subscription_name = subscription_names.get(subscription_id, subscription_id)
        snapshot_name = parts[-1]

        # Check if snapshot exists
        if not check_snapshot_exists(snapshot_id):
            return subscription_name, "non-existent", snapshot_name

        return subscription_name, "valid", snapshot_name
    except Exception as e:
        logging.error(f"Error processing snapshot {snapshot_id}: {str(e)}")
        return None, "error", (snapshot_id, str(e))

def delete_snapshot(snapshot_id):
    command = f"az snapshot delete --ids {snapshot_id}"
    result = run_az_command(command)
    return not result.startswith("Error:")

def pre_validate_snapshots(snapshot_ids, subscription_names):
    valid_snapshots = []
    results = {}
    for snapshot_id in snapshot_ids:
        subscription_name, status, data = process_snapshot(snapshot_id, subscription_names)
        if subscription_name:
            if subscription_name not in results:
                results[subscription_name] = {}
            if status not in results[subscription_name]:
                results[subscription_name][status] = []
            results[subscription_name][status].append(data)
            if status == "valid":
                valid_snapshots.append(snapshot_id)
        else:
            if "Unknown" not in results:
                results["Unknown"] = {}
            if status not in results["Unknown"]:
                results["Unknown"][status] = []
            results["Unknown"][status].append(data)
    return valid_snapshots, results

def delete_valid_snapshots(valid_snapshots, subscription_names):
    results = {}
    for snapshot_id in valid_snapshots:
        parts = snapshot_id.split('/')
        subscription_id = parts[2]
        subscription_name = subscription_names.get(subscription_id, subscription_id)
        snapshot_name = parts[-1]
        success = delete_snapshot(snapshot_id)
        if subscription_name not in results:
            results[subscription_name] = {}
        if success:
            if "deleted" not in results[subscription_name]:
                results[subscription_name]["deleted"] = []
            results[subscription_name]["deleted"].append(snapshot_name)
            logging.info(f"Deleted snapshot '{snapshot_name}' in subscription '{subscription_name}'")
        else:
            if "failed" not in results[subscription_name]:
                results[subscription_name]["failed"] = []
            results[subscription_name]["failed"].append((snapshot_name, "Deletion failed"))
            logging.error(f"Failed to delete snapshot '{snapshot_name}' in subscription '{subscription_name}'")
    return results

def restore_scope_locks(removed_locks):
    current_subscription = None
    restored_locks = []
    for subscription_id, resource_group, lock_name in removed_locks:
        current_subscription = switch_subscription(subscription_id, current_subscription)
        command = f"az lock create --name {lock_name} --resource-group {resource_group} --lock-type CanNotDelete"
        result = run_az_command(command)
        if not result.startswith("Error:"):
            restored_locks.append((subscription_id, resource_group, lock_name))
            logging.info(f"Restored lock '{lock_name}' to resource group '{resource_group}'")
        else:
            logging.error(f"Failed to restore lock '{lock_name}' to resource group '{resource_group}': {result}")
    return restored_locks

def generate_log_file(results, total_runtime):
    user_id = os.getenv('USER', 'unknown')
    current_time = datetime.now().strftime("%Y%m%d-%H%M%S")
    logs_dir = "logs"
    os.makedirs(logs_dir, exist_ok=True)
    log_filename = os.path.join(logs_dir, f"snapshot_deletion_log_{user_id}_{current_time}.txt")
    try:
        with open(log_filename, 'w') as log_file:
            log_file.write("Snapshot Deletion Log\n")
            log_file.write("=====================\n\n")
            log_file.write(f"User: {user_id}\n")
            log_file.write(f"Date and Time: {current_time}\n\n")
            log_file.write("Summary:\n")
            for subscription_name, data in results.items():
                log_file.write(f"\nSubscription: {subscription_name}\n")
                log_file.write(f"  Valid Snapshots: {len(data.get('valid', []))}\n")
                log_file.write(f"  Non-existent Snapshots: {len(data.get('non-existent', []))}\n")
                log_file.write(f"  Deleted Snapshots: {len(data.get('deleted', []))}\n")
                log_file.write(f"  Failed Deletions: {len(data.get('failed', []))}\n")
            log_file.write(f"\nTotal Runtime: {total_runtime:.2f} seconds\n")
    except Exception as e:
        logging.error(f"Failed to write log file: {str(e)}")
        return None
    return log_filename

def main(snapshot_ids: List[str]) -> Dict[str, Any]:
    try:
        if not check_az_login():
            return {"error": "Not logged in to Azure. Please run 'az login'."}

        start_time = time.time()

        subscription_names = get_subscription_names()
        if not subscription_names:
            logging.warning("Failed to fetch subscription names. Using IDs instead.")

        valid_snapshots, pre_validation_results = pre_validate_snapshots(snapshot_ids, subscription_names)

        if not valid_snapshots:
            results = pre_validation_results
        else:
            resource_groups = get_resource_groups_from_snapshots(valid_snapshots)
            removed_locks = check_and_remove_scope_locks(resource_groups)
            deletion_results = delete_valid_snapshots(valid_snapshots, subscription_names)
            restored_locks = restore_scope_locks(removed_locks)

            # Merge pre-validation results with deletion results
            results = pre_validation_results
            for subscription, data in deletion_results.items():
                if subscription in results:
                    results[subscription].update(data)
                else:
                    results[subscription] = data

        end_time = time.time()
        total_runtime = end_time - start_time

        log_filename = generate_log_file(results, total_runtime)

        return {
            "results": results,
            "log_file": log_filename,
            "total_runtime": total_runtime
        }

    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}\n{traceback.format_exc()}")
        return {"error": str(e)}

if __name__ == "__main__":
    import sys
    import json

    # Read snapshot IDs from command line arguments or stdin
    if len(sys.argv) > 1:
        # Assume snapshot IDs are passed as command line arguments
        snapshot_ids = sys.argv[1:]
    else:
        # Read snapshot IDs from stdin
        input_data = sys.stdin.read()
        snapshot_ids = json.loads(input_data)

    result = main(snapshot_ids)
    print(json.dumps(result))