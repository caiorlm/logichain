import unittest
import asyncio
import socket
from unittest.mock import Mock, patch
from blockchain.network.nat_traversal import NATTraversal, NATInfo, NATType
import pytest

class TestNATTraversal(unittest.TestCase):
    def setUp(self):
        self.nat = NATTraversal()
        self.test_stun_servers = [
            'stun.test.com:19302',
            'stun1.test.com:19302'
        ]
        
    @patch('stun.get_ip_info')
    async def test_discover_nat_type(self, mock_stun):
        # Mock STUN response
        mock_stun.return_value = (
            "Full Cone",
            "123.45.67.89",
            12345
        )
        
        nat_info = await self.nat._discover_nat_type()
        self.assertEqual(nat_info.nat_type, NATType.FULL_CONE)
        self.assertEqual(nat_info.external_ip, "123.45.67.89")
        self.assertEqual(nat_info.external_port, 12345)
        
    @patch('socket.socket')
    async def test_hole_punching(self, mock_socket):
        # Mock socket
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        
        # Mock NAT info
        self.nat.nat_info = NATInfo(
            nat_type=NATType.FULL_CONE,
            external_ip="123.45.67.89",
            external_port=12345,
            local_ip="192.168.1.100",
            local_port=54321,
            stun_server="stun.test.com:19302"
        )
        
        await self.nat._start_hole_punching()
        
        # Verifica se criou 5 sockets
        self.assertEqual(len(self.nat._punch_sockets), 5)
        self.assertEqual(len(self.nat.hole_punch_ports), 5)
        
    async def test_peer_registration(self):
        peer_info = NATInfo(
            nat_type=NATType.FULL_CONE,
            external_ip="98.76.54.32",
            external_port=23456,
            local_ip="192.168.1.200",
            local_port=65432,
            stun_server="stun.test.com:19302"
        )
        
        await self.nat.register_peer("peer1", peer_info)
        self.assertIn("peer1", self.nat.peers)
        self.assertEqual(self.nat.peers["peer1"], peer_info)
        
    @patch('socket.socket')
    async def test_connect_to_peer(self, mock_socket):
        # Mock socket e resposta
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        
        # Configura mock para recvfrom
        mock_sock.recvfrom.return_value = (b'init-ack', ('98.76.54.32', 23456))
        
        # Registra peer
        peer_info = NATInfo(
            nat_type=NATType.FULL_CONE,
            external_ip="98.76.54.32",
            external_port=23456,
            local_ip="192.168.1.200",
            local_port=65432,
            stun_server="stun.test.com:19302"
        )
        await self.nat.register_peer("peer1", peer_info)
        
        # Inicia hole punching
        self.nat._punch_sockets["12345"] = mock_sock
        self.nat.hole_punch_ports = [12345]
        
        # Tenta conexão
        result = await self.nat.connect_to_peer("peer1")
        self.assertIsNotNone(result)
        mock_sock.sendto.assert_called_with(b'init', ('98.76.54.32', 23456))
        
    async def test_error_handling(self):
        # Testa peer desconhecido
        with self.assertRaises(ValueError):
            await self.nat.connect_to_peer("unknown_peer")
            
        # Testa hole punching sem NAT info
        with self.assertRaises(Exception):
            await self.nat._start_hole_punching()
            
    def test_cleanup(self):
        # Mock sockets
        mock_sock1 = Mock()
        mock_sock2 = Mock()
        
        self.nat._punch_sockets = {
            "12345": mock_sock1,
            "12346": mock_sock2
        }
        
        # Para o serviço
        asyncio.run(self.nat.stop())
        
        # Verifica se sockets foram fechados
        mock_sock1.close.assert_called_once()
        mock_sock2.close.assert_called_once()
        self.assertEqual(len(self.nat._punch_sockets), 0)

@pytest.mark.asyncio
async def test_nat_traversal_init():
    """Testa inicialização do NAT Traversal"""
    nat = NATTraversal()
    assert nat.stun_servers == [
        'stun.l.google.com:19302',
        'stun1.l.google.com:19302',
        'stun2.l.google.com:19302'
    ]
    assert nat.nat_info is None
    assert nat.hole_punch_ports == []
    assert nat.peers == {}
    assert not nat._running
    assert nat._punch_sockets == {}

@pytest.mark.asyncio
@patch('stun.get_ip_info')
async def test_nat_traversal_start_stop(mock_get_ip_info):
    """Testa ciclo de vida do NAT Traversal"""
    # Mock da resposta do STUN
    mock_get_ip_info.return_value = (
        'Full Cone',
        '1.2.3.4',
        12345
    )
    
    nat = NATTraversal()
    await nat.start()
    assert nat._running
    assert nat.nat_info is not None
    assert len(nat.hole_punch_ports) > 0
    assert len(nat._punch_sockets) > 0
    
    await nat.stop()
    assert not nat._running
    assert nat._punch_sockets == {}

@pytest.mark.asyncio
async def test_nat_traversal_peer_registration():
    """Testa registro de peers"""
    nat = NATTraversal()
    peer_info = NATInfo(
        nat_type=NATType.FULL_CONE,
        external_ip="1.2.3.4",
        external_port=12345,
        local_ip="192.168.1.2",
        local_port=54321,
        stun_server="stun.test.com:19302"
    )
    
    await nat.register_peer("peer1", peer_info)
    assert "peer1" in nat.peers
    assert nat.peers["peer1"] == peer_info

@pytest.mark.asyncio
@patch('stun.get_ip_info')
async def test_nat_traversal_peer_connection(mock_get_ip_info):
    """Testa conexão entre peers"""
    # Mock das respostas do STUN
    mock_get_ip_info.side_effect = [
        ('Full Cone', '1.2.3.4', 12345),
        ('Full Cone', '5.6.7.8', 54321)
    ]
    
    nat1 = NATTraversal()
    nat2 = NATTraversal()
    
    # Inicializa os NATs
    await nat1.start()
    await nat2.start()
    
    # Registra os peers
    await nat1.register_peer("nat2", nat2.nat_info)
    await nat2.register_peer("nat1", nat1.nat_info)
    
    # Mock do recebimento de dados
    async def mock_recvfrom(*args, **kwargs):
        return b'init-ack', ('5.6.7.8', 54321)
    
    with patch.object(nat1, '_async_recvfrom', side_effect=mock_recvfrom):
        # Tenta estabelecer conexão
        sock1 = await nat1.connect_to_peer("nat2")
        assert sock1 is not None
    
    # Limpa
    await nat1.stop()
    await nat2.stop()

if __name__ == '__main__':
    unittest.main() 