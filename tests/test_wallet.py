import unittest
import tempfile
from pathlib import Path
from blockchain.core.wallet import Wallet

class TestWallet(unittest.TestCase):
    def setUp(self):
        # Criar uma nova carteira para cada teste
        self.wallet = Wallet.create_new()
        
    def test_create_new_wallet(self):
        """Testa criação de nova carteira"""
        self.assertIsNotNone(self.wallet.private_key)
        self.assertIsNotNone(self.wallet.address)
        self.assertTrue(self.wallet.address.startswith('0x'))
        self.assertEqual(len(self.wallet.address), 42)  # 0x + 40 chars
        self.assertIsNotNone(self.wallet.mnemonic)
        self.assertEqual(len(self.wallet.mnemonic.split()), 24)  # 24 palavras
        
    def test_recover_from_mnemonic(self):
        """Testa recuperação de carteira via mnemônico"""
        mnemonic = self.wallet.mnemonic
        recovered = Wallet.from_mnemonic(mnemonic)
        
        self.assertEqual(self.wallet.address, recovered.address)
        self.assertEqual(self.wallet.private_key, recovered.private_key)
        
    def test_sign_and_verify(self):
        """Testa assinatura e verificação de mensagens"""
        message = "Teste de mensagem"
        
        # Assinar mensagem
        signature = self.wallet.sign(message)
        self.assertIsNotNone(signature)
        
        # Verificar assinatura válida
        self.assertTrue(self.wallet.verify(message, signature))
        
        # Verificar assinatura inválida
        self.assertFalse(self.wallet.verify("Mensagem errada", signature))
        self.assertFalse(self.wallet.verify(message, "assinatura_invalida"))
        
    def test_save_and_load(self):
        """Testa salvamento e carregamento de carteira"""
        # Criar arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            wallet_path = Path(tmp.name)
        
        try:
            # Salvar carteira
            self.wallet.save(wallet_path)
            
            # Carregar carteira
            loaded = Wallet.load(wallet_path)
            
            # Verificar se dados são iguais
            self.assertEqual(self.wallet.address, loaded.address)
            self.assertEqual(self.wallet.private_key, loaded.private_key)
            self.assertEqual(self.wallet.mnemonic, loaded.mnemonic)
            
            # Testar assinatura com carteira carregada
            message = "Teste após carregar"
            signature = self.wallet.sign(message)
            self.assertTrue(loaded.verify(message, signature))
            
        finally:
            # Limpar arquivo temporário
            wallet_path.unlink()
            
    def test_invalid_mnemonic(self):
        """Testa recuperação com mnemônico inválido"""
        with self.assertRaises(ValueError):
            Wallet.from_mnemonic("palavras aleatorias que não formam um mnemônico válido")

    def test_wallet_address_format(self):
        """Testa o novo formato de endereço LOGI"""
        address = self.wallet.address
        
        # Verifica formato
        self.assertTrue(address.startswith("LOGI"), "Endereço deve começar com LOGI")
        self.assertEqual(len(address), 36, "Endereço deve ter 36 caracteres (LOGI + 32 chars)")
        self.assertTrue(all(c in "0123456789abcdef" for c in address[4:]), "Hash deve ser hexadecimal")
        
        # Testa unicidade
        wallet2 = Wallet.create_new()
        self.assertNotEqual(self.wallet.address, wallet2.address, "Endereços devem ser únicos")
        
        # Testa persistência
        wallet_json = self.wallet.to_dict()
        loaded_wallet = Wallet.from_dict(wallet_json)
        self.assertEqual(self.wallet.address, loaded_wallet.address, "Endereço deve persistir após serialização")

if __name__ == '__main__':
    unittest.main() 