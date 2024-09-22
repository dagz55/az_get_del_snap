import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from rich.console import Console
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.console import Group
from collections import defaultdict
import getpass
import time
import csv

console = Console()
COLOR_SCALE = ["green", "yellow", "red"]

# Configure logging
current_date = datetime.now().strftime("%Y%m%d")
current_user = getpass.getuser()
log_file = f'filtsnap{current_date}_{current_user}.log'
logging.basicConfig(
    level=logging.ERROR,
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
overall_task = overall_progress.add_task(description="[cyan]Searching subscriptions...", total=100, subscription="")

async def run_az_command(command):
    logger.info(f"Running Azure command: {command}")
    try:
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
        snapshots = json.loads(result)
        if keyword:
            snapshots = [s for s in snapshots if keyword.lower() in s['name'].lower()]
        logger.info(f"Found {len(snapshots)} snapshots in subscription {subscription_id}")
        return snapshots
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

async def main():
    logger.info("Starting Azure Snapshot Finder")
    console.print("[bold cyan]Welcome to the Azure Snapshot Finder![/bold cyan]")

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

    console.print("\n[bold green]Snapshot search complete![/bold green]")
    logger.info("Azure Snapshot Finder completed successfully")

    # Log additional information
    logger.info(f"Total snapshots found: {total_snapshots}")
    logger.info(f"Runtime: {runtime:.2f} seconds")
    logger.info("Snapshot search complete")

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