import os
import asyncio
import json
import datetime
import getpass
from collections import defaultdict
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

console = Console()

# Global variables
user_id = getpass.getuser()
timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
log_dir = "logs"
log_file = os.path.join(log_dir, f"snapshot_creation_log_{user_id}_{timestamp}.txt")
summary_file = os.path.join(log_dir, f"snapshot_summary_{user_id}_{timestamp}.txt")
input_file = "snap_rid_list.txt"
output_file = f"snapshot_resource_ids_{timestamp}.txt"
chg_number = ""
semaphore = asyncio.Semaphore(10)
successful_snapshots = []
failed_snapshots = []

def write_log(message):
    console.print(message)  # Print to console for immediate feedback
    with open(log_file, "a") as f:
        f.write(f"{datetime.datetime.now()}: {message}\n")

def extract_vm_info(file_path):
    if not os.path.exists(file_path):
        write_log(f"[bold red]Error: Input file '{file_path}' not found.[/bold red]")
        return None

    vm_list = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    resource_id, vm_name = parts[0], parts[1]
                    vm_list.append((resource_id, vm_name))
                else:
                    write_log(f"[bold yellow]Warning: Invalid line in input file: {line.strip()}[/bold yellow]")
    except Exception as e:
        write_log(f"[bold red]Error reading input file: {str(e)}[/bold red]")
        return None

    if not vm_list:
        write_log("[bold red]Error: No valid VM information found in the input file.[/bold red]")
        return None

    return vm_list

async def run_az_command(command, max_retries=3, delay=5):
    for attempt in range(max_retries):
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            return stdout.decode().strip(), stderr.decode().strip(), process.returncode
        else:
            write_log(f"Command failed (attempt {attempt + 1}): {command}")
            write_log(f"Error: {stderr.decode().strip()}")
            if attempt < max_retries - 1:
                write_log(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
    return "", stderr.decode().strip(), process.returncode

def write_snapshot_rid(snapshot_id):
    with open(output_file, "a") as f:
        f.write(f"{snapshot_id}\n")

async def process_vm(resource_id, vm_name, progress, task):
    async with semaphore:
        write_log(f"Processing VM: {vm_name}")
        write_log(f"Resource ID: {resource_id}")

        # Get resource group and disk ID for the VM
        stdout, stderr, returncode = await run_az_command(
            f"az vm show --ids {resource_id} --query '{{resourceGroup:resourceGroup, diskId:storageProfile.osDisk.managedDisk.id}}' -o json"
        )
        if returncode != 0:
            write_log(f"Failed to get VM details for {vm_name}")
            write_log(f"Error: {stderr}")
            failed_snapshots.append((vm_name, "Failed to get VM details"))
            progress.update(task, completed=100)
            return

        vm_details = json.loads(stdout)
        resource_group = vm_details['resourceGroup']
        disk_id = vm_details['diskId']

        snapshot_name = f"RH_{chg_number}_{vm_name}_{timestamp}"
        stdout, stderr, returncode = await run_az_command(
            f"az snapshot create --name {snapshot_name} --resource-group {resource_group} --source {disk_id}"
        )
        
        if returncode != 0:
            write_log(f"Failed to create snapshot for VM: {vm_name}")
            write_log(f"Error: {stderr}")
            failed_snapshots.append((vm_name, "Failed to create snapshot"))
        else:
            write_log(f"Snapshot created: {snapshot_name}")
            
            snapshot_data = json.loads(stdout)
            snapshot_id = snapshot_data.get('id')
            if snapshot_id:
                write_snapshot_rid(snapshot_id)
                write_log(f"Snapshot resource ID added to {output_file}: {snapshot_id}")
                successful_snapshots.append((vm_name, snapshot_name))
            else:
                write_log(f"Warning: Could not extract snapshot resource ID for {snapshot_name}")
                failed_snapshots.append((vm_name, "Failed to extract snapshot ID"))

        progress.update(task, completed=100)

def group_vms_by_subscription(vm_list):
    grouped_vms = defaultdict(list)
    for resource_id, vm_name in vm_list:
        subscription_id = resource_id.split("/")[2]
        grouped_vms[subscription_id].append((resource_id, vm_name))
    return grouped_vms

async def main():
    global chg_number

    console.print("[cyan]Azure Snapshot Creator[/cyan]")
    console.print("=========================")

    # Create log directory
    os.makedirs(log_dir, exist_ok=True)

    # Get input from user
    chg_number = console.input("Enter the CHG number: ")
    
    write_log(f"CHG Number: {chg_number}")

    vm_list = extract_vm_info(input_file)
    if vm_list is None:
        return

    total_vms = len(vm_list)
    write_log(f"Total VMs to process: {total_vms}")

    grouped_vms = group_vms_by_subscription(vm_list)

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        expand=True
    )
    
    vm_tasks = {}
    for subscription_id, vms in grouped_vms.items():
        for resource_id, vm_name in vms:
            vm_tasks[vm_name] = progress.add_task(f"[cyan]{vm_name}", total=100)

    overall_task = progress.add_task("[bold green]Overall Progress", total=total_vms)

    with Live(Panel(progress), refresh_per_second=4) as live:
        for subscription_id, vms in grouped_vms.items():
            # Switch to the current subscription
            stdout, stderr, returncode = await run_az_command(f"az account set --subscription {subscription_id}")
            if returncode != 0:
                write_log(f"Failed to set subscription ID: {subscription_id}")
                write_log(f"Error: {stderr}")
                for _, vm_name in vms:
                    failed_snapshots.append((vm_name, "Failed to set subscription"))
                    progress.update(vm_tasks[vm_name], completed=100)
                    progress.update(overall_task, advance=1)
                continue

            write_log(f"Switched to subscription: {subscription_id}")

            tasks = []
            for resource_id, vm_name in vms:
                task = asyncio.create_task(process_vm(resource_id, vm_name, progress, vm_tasks[vm_name]))
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            progress.update(overall_task, advance=len(vms))

    # Display summary table
    table = Table(title="Snapshot Creation Summary")
    table.add_column("Category", style="cyan")
    table.add_column("Count", style="magenta")
    table.add_row("Total VMs Processed", str(total_vms))
    table.add_row("Successful Snapshots", str(len(successful_snapshots)))
    table.add_row("Failed Snapshots", str(len(failed_snapshots)))
    console.print(table)

    # Write summary to file
    with open(summary_file, "w") as f:
        f.write("Snapshot Creation Summary\n")
        f.write("=========================\n\n")
        f.write(f"Total VMs processed: {total_vms}\n")
        f.write(f"Successful snapshots: {len(successful_snapshots)}\n")
        f.write(f"Failed snapshots: {len(failed_snapshots)}\n\n")
        f.write("Successful snapshots:\n")
        for vm, snapshot in successful_snapshots:
            f.write(f"- {vm}: {snapshot}\n")
        f.write("\nFailed snapshots:\n")
        for vm, error in failed_snapshots:
            f.write(f"- {vm}: {error}\n")

    console.print("\n[bold green]Snapshot creation process completed.[/bold green]")
    console.print(f"Detailed log: {log_file}")
    console.print(f"Summary: {summary_file}")
    console.print(f"Snapshot resource IDs: {output_file}")

if __name__ == "__main__":
    asyncio.run(main())