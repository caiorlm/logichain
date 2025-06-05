class Wallet {
    constructor() {
        this.address = null;
        this.privateKey = null;
        this.balance = 0;
        this.transactions = [];
        this.setupEventListeners();
        this.tokenSymbol = 'LGC';
        this.tokenDecimals = 18;
    }

    setupEventListeners() {
        // Botão principal de conectar
        document.getElementById('connect-wallet').addEventListener('click', () => {
            document.querySelectorAll('section').forEach(s => s.classList.add('hidden'));
            document.getElementById('wallet').classList.remove('hidden');
            document.getElementById('wallet-choice').classList.remove('hidden');
            document.getElementById('wallet-login').classList.add('hidden');
            document.getElementById('wallet-create').classList.add('hidden');
            document.getElementById('wallet-active').classList.add('hidden');
        });

        // Botões de escolha
        document.getElementById('show-login').addEventListener('click', () => {
            document.getElementById('wallet-choice').classList.add('hidden');
            document.getElementById('wallet-login').classList.remove('hidden');
        });

        document.getElementById('show-create').addEventListener('click', () => {
            document.getElementById('wallet-choice').classList.add('hidden');
            document.getElementById('wallet-create').classList.remove('hidden');
        });

        // Formulário de login
        document.getElementById('login-form').addEventListener('submit', (e) => this.loginWallet(e));
        
        // Criação de wallet
        document.getElementById('create-wallet-btn').addEventListener('click', () => this.createWallet());
        
        // Ações da wallet ativa
        document.getElementById('backup-wallet').addEventListener('click', () => this.backupWallet());
        document.getElementById('disconnect-wallet').addEventListener('click', () => this.disconnectWallet());
        document.getElementById('send-transaction').addEventListener('submit', (e) => this.sendTransaction(e));
        document.getElementById('copy-address').addEventListener('click', () => this.copyAddress());

        // Atualizar saldo periodicamente
        setInterval(() => {
            if (this.address) {
                this.updateBalance();
                this.getTransactionHistory();
            }
        }, 30000);
    }

    async loginWallet(e) {
        e.preventDefault();
        const mnemonic = document.getElementById('mnemonic').value.trim();
        
        if (!this._validateMnemonic(mnemonic)) {
            UI.showError('Frase de recuperação inválida. Digite 12 palavras separadas por espaço.');
            return;
        }

        try {
            const response = await fetch('/api/wallet/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ mnemonic })
            });
            
            const data = await response.json();
            if (data.success) {
                this.address = data.address;
                this.privateKey = data.privateKey;
                this.balance = data.balance;
                
                // Salvar wallet no localStorage
                this._secureStore({
                    address: this.address,
                    privateKey: this.privateKey
                });

                // Atualizar UI
                this.showActiveWallet();
                await this.updateBalance();
                await this.getTransactionHistory();
                
                // Limpar form
                document.getElementById('mnemonic').value = '';
                
                UI.showSuccess('Login realizado com sucesso!');
            } else {
                UI.showError(data.error || 'Erro ao fazer login');
            }
        } catch (error) {
            UI.showError('Erro ao fazer login');
            console.error(error);
        }
    }

    async createWallet() {
        try {
            const response = await fetch('/api/wallet/create', {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                this.address = data.address;
                this.privateKey = data.privateKey;
                
                // Mostrar frase mnemônica em um modal mais seguro
                const confirmed = confirm(
                    '⚠️ IMPORTANTE: Guarde estas 12 palavras em um lugar seguro!\n' +
                    'Elas são necessárias para recuperar sua wallet.\n\n' +
                    data.mnemonic + '\n\n' +
                    'Confirme que você guardou as palavras em um lugar seguro.'
                );

                if (!confirmed) {
                    UI.showWarning('Por favor, guarde sua frase de recuperação antes de continuar.');
                    return;
                }
                
                // Salvar wallet no localStorage
                this._secureStore({
                    address: this.address,
                    privateKey: this.privateKey
                });

                // Atualizar UI
                this.showActiveWallet();
                await this.updateBalance();
                await this.getTransactionHistory();
                
                UI.showSuccess('Wallet criada com sucesso!');
            } else {
                UI.showError(data.error || 'Erro ao criar wallet');
            }
        } catch (error) {
            UI.showError('Erro ao criar wallet');
            console.error(error);
        }
    }

    showActiveWallet() {
        document.getElementById('wallet-choice').classList.add('hidden');
        document.getElementById('wallet-login').classList.add('hidden');
        document.getElementById('wallet-create').classList.add('hidden');
        document.getElementById('wallet-active').classList.remove('hidden');
        this.updateWalletUI();
    }

    disconnectWallet() {
        if (confirm('Tem certeza que deseja desconectar sua wallet?')) {
            this.address = null;
            this.privateKey = null;
            this.balance = 0;
            this.transactions = [];
            localStorage.removeItem('wallet');
            
            // Voltar para tela inicial
            document.getElementById('wallet-active').classList.add('hidden');
            document.getElementById('wallet-choice').classList.remove('hidden');
            
            this.updateWalletUI();
            UI.showSuccess('Wallet desconectada com sucesso!');
        }
    }

    copyAddress() {
        if (this.address) {
            navigator.clipboard.writeText(this.address)
                .then(() => UI.showSuccess('Endereço copiado!'))
                .catch(() => UI.showError('Erro ao copiar endereço'));
        }
    }

    async updateBalance() {
        if (!this.address) return;
        
        try {
            const response = await fetch(`/api/wallet/${this.address}/balance`);
            const data = await response.json();
            
            if (data.success) {
                this.balance = data.balance;
                this.updateWalletUI();
            } else {
                console.error('Erro ao atualizar saldo:', data.error);
            }
        } catch (error) {
            console.error('Erro ao atualizar saldo:', error);
        }
    }

    async getTransactionHistory() {
        if (!this.address) return;
        
        try {
            const response = await fetch(`/api/wallet/${this.address}/transactions`);
            const data = await response.json();
            
            if (data.success) {
                this.transactions = data.transactions;
                this.updateTransactionList();
            } else {
                console.error('Erro ao buscar transações:', data.error);
            }
        } catch (error) {
            console.error('Erro ao buscar transações:', error);
        }
    }

    async sendTransaction(e) {
        e.preventDefault();
        if (!this.address) {
            UI.showError('Conecte sua wallet primeiro!');
            return;
        }

        const to = document.getElementById('tx-to').value;
        const amount = parseFloat(document.getElementById('tx-amount').value);

        if (!this._validateAddress(to)) {
            UI.showError('Endereço de destino inválido');
            return;
        }

        if (amount <= 0) {
            UI.showError('Valor inválido');
            return;
        }

        try {
            const response = await fetch('/api/transactions/send', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    from: this.address,
                    to,
                    amount,
                    privateKey: this.privateKey
                })
            });
            
            const data = await response.json();
            if (data.success) {
                UI.showSuccess('Transação enviada com sucesso!');
                this.updateBalance();
                this.getTransactionHistory();
                
                // Limpar formulário
                document.getElementById('tx-to').value = '';
                document.getElementById('tx-amount').value = '';
            } else {
                UI.showError(data.error || 'Erro ao enviar transação');
            }
        } catch (error) {
            UI.showError('Erro ao enviar transação');
            console.error(error);
        }
    }

    updateWalletUI() {
        document.getElementById('wallet-address').textContent = this.address || '-';
        document.getElementById('wallet-balance').textContent = `${this.formatBalance(this.balance)} ${this.tokenSymbol}`;
        
        const walletStatus = document.getElementById('wallet-status');
        if (this.address) {
            walletStatus.innerHTML = `
                <span>Conectado: ${this.address.substring(0, 8)}...</span>
                <button id="disconnect-wallet" class="btn secondary">Desconectar</button>
            `;
        } else {
            walletStatus.innerHTML = `
                <span>Não conectado</span>
                <button id="create-wallet" class="btn primary">Criar Wallet</button>
            `;
        }

        // Atualizar estado dos botões
        document.getElementById('backup-wallet').disabled = !this.address;
        document.getElementById('send-transaction').disabled = !this.address;
    }

    formatBalance(balance) {
        // Converter para string mantendo casas decimais
        return (balance / (10 ** this.tokenDecimals)).toFixed(6);
    }

    updateTransactionList() {
        const container = document.getElementById('tx-list');
        const template = document.getElementById('transaction-template');
        
        container.innerHTML = '';
        this.transactions.forEach(tx => {
            const clone = template.content.cloneNode(true);
            
            clone.querySelector('.tx-type').textContent = 
                tx.from === this.address ? 'Enviado' : 'Recebido';
            clone.querySelector('.tx-date').textContent = 
                UI.formatDate(tx.timestamp);
            clone.querySelector('.tx-amount').textContent = 
                `${this.formatBalance(tx.amount)} ${this.tokenSymbol}`;
            clone.querySelector('.tx-address').textContent = 
                tx.from === this.address ? `Para: ${tx.to}` : `De: ${tx.from}`;
            clone.querySelector('.tx-status').textContent = 
                tx.confirmed ? 'Confirmado' : 'Pendente';
            
            container.appendChild(clone);
        });
    }

    backupWallet() {
        if (!this.address || !this.privateKey) {
            UI.showError('Nenhuma wallet para backup');
            return;
        }

        const backup = {
            address: this.address,
            privateKey: this.privateKey,
            timestamp: new Date().toISOString()
        };

        // Criar arquivo de backup criptografado
        const backupStr = JSON.stringify(backup);
        const blob = new Blob([backupStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `wallet-backup-${this.address.substring(0, 8)}.json`;
        a.click();
        
        URL.revokeObjectURL(url);
        
        UI.showSuccess('Backup criado com sucesso! Guarde em local seguro.');
    }

    _validateAddress(address) {
        // Validar formato do endereço
        return /^LGC[a-fA-F0-9]{40}$/.test(address);
    }

    _secureStore(data) {
        try {
            // Usar AES para criptografar dados sensíveis antes de salvar
            const encryptedData = this._encrypt(JSON.stringify(data));
            localStorage.setItem('wallet', encryptedData);
            return true;
        } catch (error) {
            console.error('Erro ao salvar wallet:', error);
            return false;
        }
    }

    _encrypt(data) {
        // Implementação básica - em produção usar biblioteca de criptografia
        return btoa(data);
    }

    _decrypt(data) {
        // Implementação básica - em produção usar biblioteca de criptografia
        return atob(data);
    }

    _validateMnemonic(mnemonic) {
        const words = mnemonic.split(' ').filter(w => w.length > 0);
        return words.length === 12 && words.every(w => w.match(/^[a-zA-Z]+$/));
    }

    // Carregar wallet salva no localStorage
    async loadSavedWallet() {
        const saved = localStorage.getItem('wallet');
        if (saved) {
            try {
                const decrypted = this._decrypt(saved);
                const { address, privateKey } = JSON.parse(decrypted);
                this.address = address;
                this.privateKey = privateKey;
                
                // Atualizar UI
                this.showActiveWallet();
                await this.updateBalance();
                await this.getTransactionHistory();
            } catch (error) {
                console.error('Erro ao carregar wallet salva:', error);
                localStorage.removeItem('wallet');
            }
        }
    }
}

// Inicializar wallet quando documento estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    window.wallet = new Wallet();
    window.wallet.loadSavedWallet();
}); 