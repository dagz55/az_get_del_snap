import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
import getpass
import time
import csv
import os
from typing import List, Dict, Any
from rich.console import Console
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.console import Group
from collections import defaultdict

console = Console()
COLOR_SCALE = ["green", "yellow", "red"]

# Configure logging
current_date = datetime.now().strftime("%Y%m%d")
current_user = getpass.getuser()
log_file = f'azure_snapshot_manager_{current_date}_{current_user}.log'
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"Logging to file: {log_file}")

# Create overall progress bar
overall_progress = Progress(
    SpinnerColumn(),
    "[progress.description]{task.description}",
    BarColumn(),
    "[progress.percentage]{task.percentage:>3.0f}%",
    "•",
    TextColumn("[bold blue]{task.fields[subscription]}"),
    TimeRemainingColumn(),
    console=console
)
overall_task = overall_progress.add_task(description="[cyan]Processing...", total=100, subscription="")

async def run_az_command(command):
    logger.info(f"Running Azure command: {command}")
    try:
        if isinstance(command, list):
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        else:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            logger.info("Command executed successfully")
            return stdout.decode().strip()
        else:
            error_message = stderr.decode().strip()
            logger.error(f"Error running command: {command}")
            logger.error(f"Error message: {error_message}")
            console.print(f"[red]Error running command: {command}[/red]")
            console.print(f"[red]Error message: {error_message}[/red]")
            return None
    except Exception as e:
        logger.exception(f"An error occurred while running command: {command}")
        console.print(f"[bold red]An error occurred: {str(e)}[/bold red]")
        return None

async def check_az_login():
    logger.info("Checking Azure login status")
    result = await run_az_command("az account show")
    if result:
        logger.info("User is already logged in to Azure")
        return True
    else:
        logger.warning("User is not logged in to Azure")
        return False

async def perform_az_login():
    logger.info("Initiating Azure login process")
    console.print("[yellow]You are not logged in to Azure. Initiating login process...[/yellow]")
    result = await run_az_command("az login --scope https://management.core.windows.net//.default")
    if result:
        logger.info("Azure login successful")
        console.print("[green]Azure login successful[/green]")
        return True
    else:
        logger.error("Azure login failed")
        console.print("[bold red]Azure login failed.[/bold red]")
        console.print("[yellow]Please ensure you have the Azure CLI installed and configured correctly.[/yellow]")
        console.print("[yellow]You may need to run 'az login --scope https://management.core.windows.net//.default' manually if the issue persists.[/yellow]")
        return False

async def get_subscriptions():
    logger.info("Fetching Azure subscriptions")
    result = await run_az_command("az account list --query '[].{name:name, id:id}' -o json")
    if result:
        subscriptions = json.loads(result)
        logger.info(f"Found {len(subscriptions)} subscriptions")
        return subscriptions
    logger.warning("No subscriptions found")
    return []

async def get_snapshots(subscription_id, start_date, end_date, keyword=None):
    logger.info(f"Fetching snapshots for subscription {subscription_id} between {start_date} and {end_date}")
    query = f"[?timeCreated >= '{start_date}' && timeCreated <= '{end_date}'].{{name:name, resourceGroup:resourceGroup, timeCreated:timeCreated, diskState:diskState, id:id, createdBy:tags.createdBy}}"
    command = f"az snapshot list --subscription {subscription_id} --query \"{query}\" -o json"
    result = await run_az_command(command)
    if result:
        try:
            snapshots = json.loads(result)
            if keyword:
                snapshots = [s for s in snapshots if keyword.lower() in s['name'].lower()]
            logger.info(f"Found {len(snapshots)} snapshots in subscription {subscription_id}")
            return snapshots
        except json.JSONDecodeError:
            if "AuthorizationFailed" in result:
                logger.warning(f"No permission to list snapshots in subscription {subscription_id}. Skipping.")
            else:
                logger.error(f"Error parsing result from Azure CLI for subscription {subscription_id}: {result}")
            return []
    logger.warning(f"No snapshots found in subscription {subscription_id}")
    return []

def get_age_color(created_date):
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(created_date)).days
    if age < 30:
        return COLOR_SCALE[0]
    elif age < 90:
        return COLOR_SCALE[1]
    else:
        return COLOR_SCALE[2]

def create_snapshot_table(snapshots, subscription_name):
    table = Table(title=f"Snapshots in {subscription_name}")
    table.add_column("Name", style="cyan")
    table.add_column("Resource Group", style="magenta")
    table.add_column("Time Created", style="green")
    table.add_column("Age (days)", style="yellow")
    table.add_column("Created By", style="blue")
    table.add_column("Status", style="red")

    for snapshot in snapshots:
        created_date = datetime.fromisoformat(snapshot['timeCreated'])
        age = (datetime.now(timezone.utc) - created_date).days
        age_color = get_age_color(snapshot['timeCreated'])
        created_by = snapshot.get('createdBy', 'N/A')
        status = snapshot.get('diskState', 'N/A')

        table.add_row(
            snapshot['name'],
            snapshot['resourceGroup'],
            snapshot['timeCreated'],
            f"[{age_color}]{age}[/{age_color}]",
            created_by,
            status
        )

    return table

def display_snapshots(snapshots, subscription_name):
    if not snapshots:
        console.print(f"[yellow]No snapshots found in subscription: {subscription_name}[/yellow]")
    else:
        table = create_snapshot_table(snapshots, subscription_name)
        console.print(table)

def get_default_date_range():
    today = datetime.now(timezone.utc)
    start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
    return start_of_month.isoformat(), end_of_month.isoformat()

async def delete_snapshots(snapshot_ids: List[str]) -> Dict[str, Any]:
    try:
        if not await check_az_login():
            return {"error": "Not logged in to Azure. Please run 'az login'."}

        start_time = time.time()

        subscription_names = {sub['id']: sub['name'] for sub in await get_subscriptions()}
        if not subscription_names:
            logger.warning("Failed to fetch subscription names. Using IDs instead.")

        valid_snapshots, pre_validation_results = await pre_validate_snapshots(snapshot_ids, subscription_names)

        if not valid_snapshots:
            results = pre_validation_results
        else:
            resource_groups = get_resource_groups_from_snapshots(valid_snapshots)
            removed_locks = await check_and_remove_scope_locks(resource_groups)
            deletion_results = await delete_valid_snapshots(valid_snapshots, subscription_names)
            restored_locks = await restore_scope_locks(removed_locks)

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
        logger.error(f"An unexpected error occurred: {str(e)}")
        return {"error": str(e)}

async def pre_validate_snapshots(snapshot_ids, subscription_names):
    valid_snapshots = []
    results = {}
    with Progress(console=console) as progress:
        task = progress.add_task("[cyan]Validating snapshots...", total=len(snapshot_ids))
        for snapshot_id in snapshot_ids:
            subscription_name, status, data = await process_snapshot(snapshot_id, subscription_names)
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
            progress.update(task, advance=1)
    return valid_snapshots, results

async def process_snapshot(snapshot_id, subscription_names):
    try:
        parts = snapshot_id.split('/')
        if len(parts) < 9:
            logger.error(f"Invalid snapshot ID format: {snapshot_id}")
            return None, "invalid", (snapshot_id, "Invalid snapshot ID format")

        subscription_id = parts[2]
        subscription_name = subscription_names.get(subscription_id, subscription_id)
        snapshot_name = parts[-1]

        # Check if snapshot exists
        if not await check_snapshot_exists(snapshot_id):
            return subscription_name, "non-existent", snapshot_name

        return subscription_name, "valid", snapshot_name
    except Exception as e:
        logger.error(f"Error processing snapshot {snapshot_id}: {str(e)}")
        return None, "error", (snapshot_id, str(e))

async def check_snapshot_exists(snapshot_id):
    command = f"az snapshot show --ids {snapshot_id}"
    result = await run_az_command(command)
    return result is not None and not result.startswith("Error:")

def get_resource_groups_from_snapshots(snapshot_ids):
    resource_groups = set()
    for snapshot_id in snapshot_ids:
        parts = snapshot_id.split('/')
        if len(parts) >= 5:
            resource_groups.add((parts[2], parts[4]))  # (subscription_id, resource_group)
    return resource_groups

async def check_and_remove_scope_locks(resource_groups):
    removed_locks = []
    current_subscription = None
    with Progress(console=console) as progress:
        task = progress.add_task("[cyan]Checking and removing scope locks...", total=len(resource_groups))
        for subscription_id, resource_group in resource_groups:
            current_subscription = await switch_subscription(subscription_id, current_subscription)
            command = f"az lock list --resource-group {resource_group} --query '[].{{name:name, level:level}}' -o json"
            locks = json.loads(await run_az_command(command))
            for lock in locks:
                if lock['level'] == 'CanNotDelete':
                    remove_command = f"az lock delete --name {lock['name']} --resource-group {resource_group}"
                    result = await run_az_command(remove_command)
                    if result is not None and not result.startswith("Error:"):
                        removed_locks.append((subscription_id, resource_group, lock['name']))
                        logger.info(f"Removed lock '{lock['name']}' from resource group '{resource_group}'")
                    else:
                        logger.error(f"Failed to remove lock '{lock['name']}' from resource group '{resource_group}': {result}")
            progress.update(task, advance=1)
    return removed_locks

async def switch_subscription(subscription, current_subscription):
    if subscription != current_subscription:
        try:
            await run_az_command(['az', 'account', 'set', '--subscription', subscription])
            logger.info(f"Switched to subscription: {subscription}")
            return subscription
        except Exception as e:
            logger.error(f"Failed to switch to subscription {subscription}: {str(e)}")
            raise
    return current_subscription

async def delete_valid_snapshots(valid_snapshots, subscription_names):
    results = {}
    with Progress(console=console) as progress:
        task = progress.add_task("[cyan]Deleting snapshots...", total=len(valid_snapshots))
        for snapshot_id in valid_snapshots:
            parts = snapshot_id.split('/')
            subscription_id = parts[2]
            subscription_name = subscription_names.get(subscription_id, subscription_id)
            snapshot_name = parts[-1]
            success = await delete_snapshot(snapshot_id)
            if subscription_name not in results:
                results[subscription_name] = {}
            if success:
                if "deleted" not in results[subscription_name]:
                    results[subscription_name]["deleted"] = []
                results[subscription_name]["deleted"].append(snapshot_name)
                logger.info(f"Deleted snapshot '{snapshot_name}' in subscription '{subscription_name}'")
            else:
                if "failed" not in results[subscription_name]:
                    results[subscription_name]["failed"] = []
                results[subscription_name]["failed"].append((snapshot_name, "Deletion failed"))
                logger.error(f"Failed to delete snapshot '{snapshot_name}' in subscription '{subscription_name}'")
            progress.update(task, advance=1)
    return results

async def delete_snapshot(snapshot_id):
    command = f"az snapshot delete --ids {snapshot_id}"
    result = await run_az_command(command)
    return result is not None and not result.startswith("Error:")

async def restore_scope_locks(removed_locks):
    current_subscription = None
    restored_locks = []
    with Progress(console=console) as progress:
        task = progress.add_task("[cyan]Restoring scope locks...", total=len(removed_locks))
        for subscription_id, resource_group, lock_name in removed_locks:
            current_subscription = await switch_subscription(subscription_id, current_subscription)
            command = f"az lock create --name {lock_name} --resource-group {resource_group} --lock-type CanNotDelete"
            result = await run_az_command(command)
            if result is not None and not result.startswith("Error:"):
                restored_locks.append((subscription_id, resource_group, lock_name))
                logger.info(f"Restored lock '{lock_name}' to resource group '{resource_group}'")
            else:
                logger.error(f"Failed to restore lock '{lock_name}' to resource group '{resource_group}': {result}")
            progress.update(task, advance=1)
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
        logger.error(f"Failed to write log file: {str(e)}")
        return None
    return log_filename

async def main():
    logger.info("Starting Azure Snapshot Manager")
    console.print("[bold cyan]Welcome to the Azure Snapshot Manager![/bold cyan]")

    # Check Azure login status
    if not await check_az_login():
        if not await perform_az_login():
            logger.error("Failed to log in to Azure. Exiting.")
            return

    # Get date range from user or use default
    default_start, default_end = get_default_date_range()
    start_date = Prompt.ask("Enter start date (YYYY-MM-DD)", default=default_start[:10])
    end_date = Prompt.ask("Enter end date (YYYY-MM-DD)", default=default_end[:10])

    # Validate and format dates
    try:
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        start_date = start_datetime.isoformat()
        end_date = end_datetime.isoformat()
        logger.info(f"Date range set: {start_date} to {end_date}")
    except ValueError:
        logger.warning("Invalid date format. Using default date range for the current month.")
        console.print("[bold red]Invalid date format. Using default date range for the current month.[/bold red]")
        start_date, end_date = default_start, default_end

    # Ask for keyword filter
    keyword = Prompt.ask("Enter a keyword to filter snapshots (optional)", default="")

    subscriptions = await get_subscriptions()
    if not subscriptions:
        logger.error("No subscriptions found. User may not be logged in.")
        console.print("[bold red]No subscriptions found. Please make sure you're logged in with 'az login'.[/bold red]")
        return

    all_snapshots = []
    start_time = time.time()

    # Create a growing table
    growing_table = Table(title="[bold cyan]Snapshot Search Results[/bold cyan]", border_style="blue")
    growing_table.add_column("Subscription", style="cyan", header_style="bold cyan")
    growing_table.add_column("Snapshots Found", style="magenta", header_style="bold magenta")
    growing_table.add_column("Status", style="green", header_style="bold green")

    with Live(Panel(Group(overall_progress, growing_table)), refresh_per_second=4) as live:
        for i, subscription in enumerate(subscriptions):
            logger.info(f"Searching in subscription: {subscription['name']}")
            overall_progress.update(overall_task, completed=(i+1)/len(subscriptions)*100, description=f"Searching subscriptions", subscription=f"{i+1}/{len(subscriptions)}")
            snapshots = await get_snapshots(subscription['id'], start_date, end_date, keyword)
            all_snapshots.extend(snapshots)
            
            # Update the growing table
            status = "[bold green]Complete[/bold green]" if snapshots else "[bold red]No snapshots found[/bold red]"
            growing_table.add_row(subscription['name'], f"[bold magenta]{len(snapshots)}[/bold magenta]", status)
            live.update(Panel(Group(overall_progress, growing_table)))

    end_time = time.time()
    runtime = end_time - start_time

    # Display detailed results
    console.print("\n[bold cyan]Detailed Results:[/bold cyan]")
    for subscription in subscriptions:
        subscription_snapshots = [s for s in all_snapshots if subscription['id'] in s['id']]
        display_snapshots(subscription_snapshots, subscription['name'])

    # Log sorted snapshots
    log_sorted_snapshots(all_snapshots)

    total_snapshots = len(all_snapshots)
    summary = Panel(
        f"[bold green]Total snapshots found: {total_snapshots}[/bold green]\n"
        f"[bold yellow]Runtime: {runtime:.2f} seconds[/bold yellow]",
        title="Summary",
        expand=False
    )
    console.print(summary)

    # Export to CSV
    if Prompt.ask("Do you want to export results to CSV?", choices=["y", "n"], default="n") == "y":
        filename = f"snapshot_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['name', 'resourceGroup', 'timeCreated', 'createdBy', 'subscription', 'diskState', 'id']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for snapshot in all_snapshots:
                snapshot['subscription'] = next(sub['name'] for sub in subscriptions if sub['id'] in snapshot['id'])
                writer.writerow({k: snapshot.get(k, 'N/A') for k in fieldnames})
        console.print(f"[green]Results exported to {filename}[/green]")

    # Ask if user wants to delete snapshots
    if Prompt.ask("Do you want to delete snapshots?", choices=["y", "n"], default="n") == "y":
        snapshot_ids_to_delete = [snapshot['id'] for snapshot in all_snapshots]
        deletion_results = await delete_snapshots(snapshot_ids_to_delete)
        
        if "error" in deletion_results:
            console.print(f"[bold red]Error during deletion: {deletion_results['error']}[/bold red]")
        else:
            console.print("\n[bold cyan]Deletion Results:[/bold cyan]")
            for subscription, data in deletion_results['results'].items():
                console.print(f"[bold]{subscription}[/bold]")
                console.print(f"  Deleted: {len(data.get('deleted', []))}")
                console.print(f"  Failed: {len(data.get('failed', []))}")
            
            console.print(f"\n[green]Deletion log file: {deletion_results['log_file']}[/green]")
            console.print(f"[yellow]Total deletion runtime: {deletion_results['total_runtime']:.2f} seconds[/yellow]")

    console.print("\n[bold green]Azure Snapshot Manager completed successfully![/bold green]")
    logger.info("Azure Snapshot Manager completed successfully")

def log_sorted_snapshots(all_snapshots):
    sorted_snapshots = defaultdict(lambda: defaultdict(list))
    for snapshot in all_snapshots:
        subscription_id = snapshot['id'].split('/')[2]
        sorted_snapshots[subscription_id][snapshot['resourceGroup']].append(snapshot['id'])

    logger.info("Sorted Snapshot Resource IDs:")
    for subscription_id, resource_groups in sorted_snapshots.items():
        logger.info(f"Subscription: {subscription_id}")
        for resource_group, snapshot_ids in resource_groups.items():
            logger.info(f"  Resource Group: {resource_group}")
            for snapshot_id in snapshot_ids:
                logger.info(f"    {snapshot_id}")

if __name__ == "__main__":
    asyncio.run(main())