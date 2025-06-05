"""
LogiChain DAG Inspector
CLI tool for inspecting and debugging mesh state DAG
"""

import click
import json
import time
from rich.console import Console
from rich.tree import Tree
from rich.table import Table
from rich.panel import Panel
from typing import Dict, List, Optional

from ..mesh.mesh_history import MeshHistory
from ..mesh.snapshot import StateSnapshot
from ..crypto.key_manager import KeyManager

console = Console()

class DAGInspector:
    """DAG inspection and debugging tool"""
    
    def __init__(self, mesh_history: MeshHistory):
        self.mesh = mesh_history
        
    def print_tree(self):
        """Print visual tree of DAG"""
        if not self.mesh.genesis_hash:
            console.print("[red]No genesis state found")
            return
            
        tree = Tree(f"[blue]Genesis ({self.mesh.genesis_hash[:8]})")
        
        def add_children(node: Tree, state_hash: str, seen: set):
            if state_hash in seen:
                node.add(f"[red]LOOP -> {state_hash[:8]}")
                return
                
            seen.add(state_hash)
            state = self.mesh.states[state_hash]
            
            for child in state.children:
                child_state = self.mesh.states[child]
                is_head = child in self.mesh.heads
                
                # Create node label
                label = f"[{'green' if is_head else 'yellow'}]{child[:8]}"
                label += f" (d={child_state.depth})"
                
                child_node = node.add(label)
                add_children(child_node, child, seen.copy())
                
        add_children(tree, self.mesh.genesis_hash, set())
        console.print(tree)
        
    def print_stats(self):
        """Print DAG statistics"""
        stats = Table(title="DAG Statistics")
        
        stats.add_column("Metric", style="cyan")
        stats.add_column("Value", style="green")
        
        # Basic stats
        stats.add_row("Total States", str(len(self.mesh.states)))
        stats.add_row("Active Heads", str(len(self.mesh.heads)))
        stats.add_row("Max Depth", str(max(s.depth for s in self.mesh.states.values())))
        
        # Time range
        times = [s.timestamp for s in self.mesh.states.values()]
        if times:
            start = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(min(times)))
            end = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(max(times)))
            stats.add_row("Time Range", f"{start} to {end}")
            
        # Transaction stats
        total_tx = sum(len(s.snapshot.transactions) for s in self.mesh.states.values())
        stats.add_row("Total Transactions", str(total_tx))
        
        console.print(stats)
        
    def print_state(self, state_hash: str):
        """Print detailed state information"""
        if state_hash not in self.mesh.states:
            console.print(f"[red]State not found: {state_hash}")
            return
            
        state = self.mesh.states[state_hash]
        
        # Create state panel
        panel = Panel(
            title=f"State {state_hash[:16]}",
            title_align="left",
            style="blue"
        )
        
        # Build content
        content = []
        content.append(f"[cyan]Node ID:[/] {state.snapshot.node_id}")
        content.append(f"[cyan]Timestamp:[/] {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(state.timestamp))}")
        content.append(f"[cyan]Depth:[/] {state.depth}")
        content.append(f"[cyan]Parents:[/] {', '.join(p[:8] for p in state.parents)}")
        content.append(f"[cyan]Children:[/] {', '.join(c[:8] for c in state.children)}")
        content.append(f"[cyan]Is Head:[/] {'Yes' if state_hash in self.mesh.heads else 'No'}")
        
        # Transaction details
        txs = state.snapshot.transactions
        content.append(f"\n[cyan]Transactions ({len(txs)}):[/]")
        for tx in txs:
            content.append(f"  [yellow]{tx.tx_hash[:8]}[/] from {tx.sender_id}")
            content.append(f"    Path: {' -> '.join(h.node_id for h in tx.sync_path)}")
            
        panel.renderable = "\n".join(content)
        console.print(panel)
        
@click.group()
def cli():
    """LogiChain DAG Inspector"""
    pass
    
@cli.command()
def tree():
    """Show visual tree of DAG"""
    mesh = load_mesh_history()
    inspector = DAGInspector(mesh)
    inspector.print_tree()
    
@cli.command()
def stats():
    """Show DAG statistics"""
    mesh = load_mesh_history()
    inspector = DAGInspector(mesh)
    inspector.print_stats()
    
@cli.command()
@click.argument('state_hash')
def state(state_hash: str):
    """Show detailed state information"""
    mesh = load_mesh_history()
    inspector = DAGInspector(mesh)
    inspector.print_state(state_hash)
    
def load_mesh_history() -> MeshHistory:
    """Load mesh history from storage"""
    # TODO: Implement actual storage
    # For now return empty history
    return MeshHistory()
    
if __name__ == '__main__':
    cli() 