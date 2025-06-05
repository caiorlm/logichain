import time
import asyncio
from typing import Dict, List
from blockchain.security.secure_lora import SecureLoRaProtocol, LoRaMessage
from blockchain.security.proof_of_delivery import SecurePoD
from blockchain.identity.node_identity import NodeIdentity

class ReplayAttackSimulator:
    def __init__(self):
        self.lora = SecureLoRaProtocol()
        self.pod = SecurePoD()
        self.identity = NodeIdentity()
        self.captured_packets: List[bytes] = []
        
    async def simulate_normal_transaction(self) -> Dict:
        """Simulate a normal transaction to capture"""
        # Create legitimate message
        message = LoRaMessage(
            source="node1",
            destination="node2",
            timestamp=time.time(),
            data={"amount": 100, "type": "transfer"},
            message_type="TRANSACTION",
            sequence=1
        )
        
        # Encrypt and capture packet
        encrypted = self.lora.encrypt_packet(message)
        self.captured_packets.append(encrypted)
        
        # Legitimate decryption
        decrypted = self.lora.decrypt_packet(
            encrypted,
            message.source,
            message.destination
        )
        
        return {
            "success": True,
            "original": message,
            "decrypted": decrypted
        }
        
    async def attempt_replay_attack(self) -> Dict:
        """Attempt to replay a captured packet"""
        if not self.captured_packets:
            return {
                "success": False,
                "reason": "No captured packets"
            }
            
        # Try to replay first captured packet
        packet = self.captured_packets[0]
        
        try:
            # Attempt to decrypt replayed packet
            decrypted = self.lora.decrypt_packet(
                packet,
                "node1",
                "node2"
            )
            
            return {
                "success": True,
                "replayed": decrypted,
                "detected": False
            }
            
        except Exception as e:
            return {
                "success": False,
                "reason": str(e),
                "detected": True
            }
            
    async def run_attack_sequence(self):
        """Run full attack simulation"""
        print("Starting replay attack simulation...")
        
        # 1. Normal transaction
        print("\n1. Simulating normal transaction...")
        normal = await self.simulate_normal_transaction()
        print(f"Normal transaction: {normal}")
        
        # Wait a bit
        await asyncio.sleep(1)
        
        # 2. Attempt replay
        print("\n2. Attempting replay attack...")
        replay = await self.attempt_replay_attack()
        print(f"Replay attempt: {replay}")
        
        # 3. Analysis
        print("\n3. Analysis:")
        if replay["detected"]:
            print("✅ Replay attack was successfully detected")
            print(f"Detection reason: {replay['reason']}")
        else:
            print("❌ WARNING: Replay attack was successful!")
            print("System is vulnerable to replay attacks")
            
async def main():
    simulator = ReplayAttackSimulator()
    await simulator.run_attack_sequence()

if __name__ == "__main__":
    asyncio.run(main()) 