"""
Dashboard frontend for LogiChain explorer.
Implements a web interface for blockchain data visualization.
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

class ExplorerDashboard:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        
    def run(self):
        """Run the dashboard"""
        st.set_page_config(
            page_title="LogiChain Explorer",
            page_icon="🔗",
            layout="wide"
        )
        
        st.title("LogiChain Explorer")
        
        # Sidebar
        st.sidebar.title("Navigation")
        page = st.sidebar.radio(
            "Select Page",
            ["Overview", "Blocks", "Transactions", "Staking", "Governance"]
        )
        
        # Refresh data
        if st.sidebar.button("Refresh Data"):
            st.experimental_rerun()
            
        # Display selected page
        if page == "Overview":
            self.show_overview()
        elif page == "Blocks":
            self.show_blocks()
        elif page == "Transactions":
            self.show_transactions()
        elif page == "Staking":
            self.show_staking()
        else:
            self.show_governance()
            
    def show_overview(self):
        """Show blockchain overview"""
        try:
            # Get stats
            stats = requests.get(f"{self.api_url}/stats").json()
            
            # Display metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Block Height", stats["height"])
                st.metric("Total Transactions", stats["total_transactions"])
                
            with col2:
                st.metric("Active Nodes", stats["active_nodes"])
                st.metric(
                    "Average Block Time",
                    f"{stats['average_block_time']:.2f}s"
                )
                
            with col3:
                st.metric("Current Difficulty", stats["current_difficulty"])
                st.metric("Total Supply", stats["total_supply"])
                
            # Latest block info
            st.subheader("Latest Block")
            st.json(stats["latest_block"])
            
            # Get additional stats
            staking = requests.get(f"{self.api_url}/staking").json()
            governance = requests.get(f"{self.api_url}/governance").json()
            
            # Display charts
            col1, col2 = st.columns(2)
            
            with col1:
                # Staking distribution
                fig = px.pie(
                    values=list(staking["total_staked"].values()),
                    names=list(staking["total_staked"].keys()),
                    title="Stake Distribution"
                )
                st.plotly_chart(fig)
                
            with col2:
                # Governance activity
                fig = go.Figure(data=[
                    go.Bar(
                        x=["Total", "Active"],
                        y=[
                            governance["total_proposals"],
                            governance["active_proposals"]
                        ],
                        name="Proposals"
                    )
                ])
                fig.update_layout(title="Governance Activity")
                st.plotly_chart(fig)
                
        except Exception as e:
            st.error(f"Error loading overview: {str(e)}")
            
    def show_blocks(self):
        """Show block explorer"""
        st.subheader("Block Explorer")
        
        # Search block
        block_hash = st.text_input("Search Block by Hash")
        if block_hash:
            try:
                block = requests.get(
                    f"{self.api_url}/blocks/{block_hash}"
                ).json()
                st.json(block)
            except Exception as e:
                st.error(f"Error loading block: {str(e)}")
                
        # Recent blocks
        st.subheader("Recent Blocks")
        try:
            stats = requests.get(f"{self.api_url}/stats").json()
            height = stats["height"]
            
            blocks = []
            for i in range(max(0, height - 10), height + 1):
                try:
                    block = requests.get(
                        f"{self.api_url}/blocks/{i}"
                    ).json()
                    blocks.append(block)
                except:
                    continue
                    
            if blocks:
                df = pd.DataFrame(blocks)
                st.dataframe(df)
                
        except Exception as e:
            st.error(f"Error loading recent blocks: {str(e)}")
            
    def show_transactions(self):
        """Show transaction explorer"""
        st.subheader("Transaction Explorer")
        
        # Search transaction
        tx_hash = st.text_input("Search Transaction by Hash")
        if tx_hash:
            try:
                tx = requests.get(
                    f"{self.api_url}/transactions/{tx_hash}"
                ).json()
                st.json(tx)
            except Exception as e:
                st.error(f"Error loading transaction: {str(e)}")
                
        # Search address
        address = st.text_input("Search Address")
        if address:
            try:
                addr_info = requests.get(
                    f"{self.api_url}/address/{address}"
                ).json()
                
                # Display address info
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Balance", addr_info["balance"])
                    st.metric("Transaction Count", addr_info["transaction_count"])
                    
                with col2:
                    if addr_info["stake"]:
                        st.metric("Staked Amount", addr_info["stake"]["amount"])
                        st.metric("Rewards Claimed", addr_info["stake"]["rewards_claimed"])
                        
                # Display transactions
                st.subheader("Recent Transactions")
                df = pd.DataFrame(addr_info["transactions"])
                st.dataframe(df)
                
            except Exception as e:
                st.error(f"Error loading address: {str(e)}")
                
    def show_staking(self):
        """Show staking dashboard"""
        st.subheader("Staking Dashboard")
        
        try:
            stats = requests.get(f"{self.api_url}/staking").json()
            
            # Display metrics
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Total Staked", sum(stats["total_staked"].values()))
                st.metric("Active Stakes", stats["active_stakes"])
                
            with col2:
                st.metric(
                    "Total Rewards",
                    stats["total_rewards_distributed"]
                )
                st.metric(
                    "Average APY",
                    f"{stats['average_apy']:.2%}"
                )
                
            # Stake distribution chart
            fig = px.pie(
                values=list(stats["total_staked"].values()),
                names=list(stats["total_staked"].keys()),
                title="Stake Distribution by Type"
            )
            st.plotly_chart(fig)
            
        except Exception as e:
            st.error(f"Error loading staking stats: {str(e)}")
            
    def show_governance(self):
        """Show governance dashboard"""
        st.subheader("Governance Dashboard")
        
        try:
            stats = requests.get(f"{self.api_url}/governance").json()
            
            # Display metrics
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Total Proposals", stats["total_proposals"])
                st.metric("Active Proposals", stats["active_proposals"])
                
            with col2:
                st.metric("Total Voters", stats["total_voters"])
                st.metric("Total Votes Cast", stats["total_votes_cast"])
                
            # Governance activity chart
            fig = go.Figure(data=[
                go.Bar(
                    x=["Total", "Active"],
                    y=[stats["total_proposals"], stats["active_proposals"]],
                    name="Proposals"
                )
            ])
            fig.update_layout(title="Proposal Status")
            st.plotly_chart(fig)
            
        except Exception as e:
            st.error(f"Error loading governance stats: {str(e)}")

if __name__ == "__main__":
    dashboard = ExplorerDashboard()
    dashboard.run() 