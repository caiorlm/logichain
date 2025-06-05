import time
import tkinter as tk
from tkinter import ttk
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import threading

class NodeStatus(Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SYNCING = "SYNCING"
    SUSPICIOUS = "SUSPICIOUS"

@dataclass
class BlockInfo:
    hash: str
    height: int
    miner: str
    timestamp: float
    tx_count: int
    size: int
    score: float
    is_confirmed: bool

@dataclass
class NodeInfo:
    node_id: str
    status: NodeStatus
    last_seen: float
    block_height: int
    peer_count: int
    is_mining: bool

class OnlineViewer:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Blockchain Network Monitor")
        
        # Data
        self.blocks: Dict[str, BlockInfo] = {}
        self.nodes: Dict[str, NodeInfo] = {}
        self.selected_block: Optional[str] = None
        self.selected_node: Optional[str] = None
        
        # Update thread
        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop)
        
        # UI Setup
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI components"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Left panel - Network status
        network_frame = ttk.LabelFrame(main_frame, text="Network Status", padding="5")
        network_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Node list
        self.node_tree = ttk.Treeview(
            network_frame,
            columns=("status", "height", "peers"),
            show="headings"
        )
        self.node_tree.heading("status", text="Status")
        self.node_tree.heading("height", text="Height")
        self.node_tree.heading("peers", text="Peers")
        self.node_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Node scrollbar
        node_scroll = ttk.Scrollbar(
            network_frame,
            orient=tk.VERTICAL,
            command=self.node_tree.yview
        )
        node_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.node_tree.configure(yscrollcommand=node_scroll.set)
        
        # Node details
        node_details = ttk.LabelFrame(network_frame, text="Node Details", padding="5")
        node_details.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        self.node_details_text = tk.Text(node_details, height=5, width=40)
        self.node_details_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Center panel - Blockchain view
        chain_frame = ttk.LabelFrame(main_frame, text="Blockchain", padding="5")
        chain_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Block list
        self.block_tree = ttk.Treeview(
            chain_frame,
            columns=("height", "miner", "txs", "time"),
            show="headings"
        )
        self.block_tree.heading("height", text="Height")
        self.block_tree.heading("miner", text="Miner")
        self.block_tree.heading("txs", text="Txs")
        self.block_tree.heading("time", text="Time")
        self.block_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Block scrollbar
        block_scroll = ttk.Scrollbar(
            chain_frame,
            orient=tk.VERTICAL,
            command=self.block_tree.yview
        )
        block_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.block_tree.configure(yscrollcommand=block_scroll.set)
        
        # Block details
        block_details = ttk.LabelFrame(chain_frame, text="Block Details", padding="5")
        block_details.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        self.block_details_text = tk.Text(block_details, height=5, width=40)
        self.block_details_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Right panel - Transaction pool
        pool_frame = ttk.LabelFrame(main_frame, text="Transaction Pool", padding="5")
        pool_frame.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Transaction list
        self.tx_tree = ttk.Treeview(
            pool_frame,
            columns=("hash", "from", "to", "amount"),
            show="headings"
        )
        self.tx_tree.heading("hash", text="Hash")
        self.tx_tree.heading("from", text="From")
        self.tx_tree.heading("to", text="To")
        self.tx_tree.heading("amount", text="Amount")
        self.tx_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Transaction scrollbar
        tx_scroll = ttk.Scrollbar(
            pool_frame,
            orient=tk.VERTICAL,
            command=self.tx_tree.yview
        )
        tx_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.tx_tree.configure(yscrollcommand=tx_scroll.set)
        
        # Status bar
        status_frame = ttk.Frame(main_frame, padding="5")
        status_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E))
        
        self.status_label = ttk.Label(status_frame, text="Connected")
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        self.sync_progress = ttk.Progressbar(
            status_frame,
            orient=tk.HORIZONTAL,
            mode="determinate"
        )
        self.sync_progress.grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        # Event bindings
        self.node_tree.bind("<<TreeviewSelect>>", self._on_node_select)
        self.block_tree.bind("<<TreeviewSelect>>", self._on_block_select)
        self.tx_tree.bind("<<TreeviewSelect>>", self._on_tx_select)
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        network_frame.rowconfigure(0, weight=1)
        network_frame.columnconfigure(0, weight=1)
        
        chain_frame.rowconfigure(0, weight=1)
        chain_frame.columnconfigure(0, weight=1)
        
        pool_frame.rowconfigure(0, weight=1)
        pool_frame.columnconfigure(0, weight=1)
        
        status_frame.columnconfigure(1, weight=1)
        
    def start(self):
        """Start the viewer"""
        self.running = True
        self.update_thread.start()
        self.root.mainloop()
        
    def stop(self):
        """Stop the viewer"""
        self.running = False
        self.update_thread.join()
        
    def _update_loop(self):
        """Background update loop"""
        while self.running:
            try:
                self._update_data()
                self._update_ui()
                time.sleep(1)
            except Exception as e:
                print(f"Error in update loop: {e}")
                
    def _update_data(self):
        """Update blockchain data"""
        try:
            # Update node info
            self._update_nodes()
            
            # Update blocks
            self._update_blocks()
            
            # Update transaction pool
            self._update_transactions()
            
        except Exception as e:
            print(f"Error updating data: {e}")
            
    def _update_nodes(self):
        """Update node information"""
        # TODO: Implement node data update
        pass
        
    def _update_blocks(self):
        """Update block information"""
        # TODO: Implement block data update
        pass
        
    def _update_transactions(self):
        """Update transaction pool"""
        # TODO: Implement transaction data update
        pass
        
    def _update_ui(self):
        """Update UI with current data"""
        try:
            # Update node list
            self._update_node_list()
            
            # Update block list
            self._update_block_list()
            
            # Update transaction list
            self._update_tx_list()
            
            # Update status
            self._update_status()
            
        except Exception as e:
            print(f"Error updating UI: {e}")
            
    def _update_node_list(self):
        """Update node treeview"""
        try:
            # Clear existing items
            for item in self.node_tree.get_children():
                self.node_tree.delete(item)
                
            # Add nodes
            for node_id, info in self.nodes.items():
                self.node_tree.insert(
                    "",
                    tk.END,
                    values=(
                        info.status.value,
                        info.block_height,
                        info.peer_count
                    )
                )
                
        except Exception as e:
            print(f"Error updating node list: {e}")
            
    def _update_block_list(self):
        """Update block treeview"""
        try:
            # Clear existing items
            for item in self.block_tree.get_children():
                self.block_tree.delete(item)
                
            # Add blocks
            sorted_blocks = sorted(
                self.blocks.values(),
                key=lambda b: b.height,
                reverse=True
            )
            
            for block in sorted_blocks:
                self.block_tree.insert(
                    "",
                    tk.END,
                    values=(
                        block.height,
                        block.miner,
                        block.tx_count,
                        time.strftime(
                            "%H:%M:%S",
                            time.localtime(block.timestamp)
                        )
                    )
                )
                
        except Exception as e:
            print(f"Error updating block list: {e}")
            
    def _update_tx_list(self):
        """Update transaction treeview"""
        # TODO: Implement transaction list update
        pass
        
    def _update_status(self):
        """Update status bar"""
        try:
            # Count active nodes
            active_nodes = len([
                n for n in self.nodes.values()
                if n.status == NodeStatus.ACTIVE
            ])
            
            # Get sync status
            syncing_nodes = len([
                n for n in self.nodes.values()
                if n.status == NodeStatus.SYNCING
            ])
            
            # Update status text
            self.status_label.config(
                text=(
                    f"Connected | "
                    f"{active_nodes} active nodes | "
                    f"{syncing_nodes} syncing"
                )
            )
            
            # Update progress bar
            if syncing_nodes > 0:
                self.sync_progress["value"] = 50  # TODO: Real progress
            else:
                self.sync_progress["value"] = 100
                
        except Exception as e:
            print(f"Error updating status: {e}")
            
    def _on_node_select(self, event):
        """Handle node selection"""
        try:
            selection = self.node_tree.selection()
            if not selection:
                return
                
            item = selection[0]
            node_id = self.node_tree.item(item)["values"][0]
            
            if node_id in self.nodes:
                self.selected_node = node_id
                self._show_node_details(self.nodes[node_id])
                
        except Exception as e:
            print(f"Error handling node selection: {e}")
            
    def _on_block_select(self, event):
        """Handle block selection"""
        try:
            selection = self.block_tree.selection()
            if not selection:
                return
                
            item = selection[0]
            height = self.block_tree.item(item)["values"][0]
            
            # Find block by height
            block = next(
                (b for b in self.blocks.values() if b.height == height),
                None
            )
            
            if block:
                self.selected_block = block.hash
                self._show_block_details(block)
                
        except Exception as e:
            print(f"Error handling block selection: {e}")
            
    def _on_tx_select(self, event):
        """Handle transaction selection"""
        # TODO: Implement transaction selection
        pass
        
    def _show_node_details(self, node: NodeInfo):
        """Show detailed node information"""
        try:
            details = {
                "Node ID": node.node_id,
                "Status": node.status.value,
                "Last Seen": time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(node.last_seen)
                ),
                "Block Height": node.block_height,
                "Peer Count": node.peer_count,
                "Mining": "Yes" if node.is_mining else "No"
            }
            
            self.node_details_text.delete("1.0", tk.END)
            self.node_details_text.insert(
                tk.END,
                json.dumps(details, indent=2)
            )
            
        except Exception as e:
            print(f"Error showing node details: {e}")
            
    def _show_block_details(self, block: BlockInfo):
        """Show detailed block information"""
        try:
            details = {
                "Hash": block.hash,
                "Height": block.height,
                "Miner": block.miner,
                "Timestamp": time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(block.timestamp)
                ),
                "Transactions": block.tx_count,
                "Size": f"{block.size} bytes",
                "Score": f"{block.score:.2f}",
                "Status": "Confirmed" if block.is_confirmed else "Pending"
            }
            
            self.block_details_text.delete("1.0", tk.END)
            self.block_details_text.insert(
                tk.END,
                json.dumps(details, indent=2)
            )
            
        except Exception as e:
            print(f"Error showing block details: {e}")
            
if __name__ == "__main__":
    root = tk.Tk()
    viewer = OnlineViewer(root)
    viewer.start() 