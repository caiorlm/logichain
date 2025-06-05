class BlockchainAPI {
    static async getBlocks() {
        try {
            const response = await fetch('/api/blocks');
            return await response.json();
        } catch (error) {
            console.error('Erro ao buscar blocos:', error);
            return [];
        }
    }

    static async getStats() {
        try {
            const response = await fetch('/api/stats');
            return await response.json();
        } catch (error) {
            console.error('Erro ao buscar estatísticas:', error);
            return {
                total_blocks: 0,
                total_contracts: 0,
                online_mode: false,
                last_update: new Date().toISOString()
            };
        }
    }

    static async getPendingContracts() {
        try {
            const response = await fetch('/api/contracts/pending');
            return await response.json();
        } catch (error) {
            console.error('Erro ao buscar contratos pendentes:', error);
            return [];
        }
    }

    static async getNetworkMode() {
        try {
            const response = await fetch('/api/mode');
            return await response.json();
        } catch (error) {
            console.error('Erro ao verificar modo da rede:', error);
            return { online: false };
        }
    }

    static validateBlock(block) {
        return block && block.hash && block.timestamp && 
               block.start_coords && block.end_coords && block.contract_id;
    }

    static validateContract(contract) {
        return contract && contract.id && contract.status &&
               contract.pickup_location && contract.delivery_location;
    }

    static async syncWithNetwork() {
        const mode = await this.getNetworkMode();
        if (!mode.online) {
            console.log('Modo offline - usando dados em cache');
            return false;
        }

        try {
            await Promise.all([
                this.getBlocks(),
                this.getStats(),
                this.getPendingContracts()
            ]);
            return true;
        } catch (error) {
            console.error('Erro na sincronização:', error);
            return false;
        }
    }
}

class Blockchain {
    constructor() {
        this.blocks = [];
        this.setupEventListeners();
        this.loadBlocks();
    }

    setupEventListeners() {
        // Atualizar blocos quando a aba for selecionada
        document.querySelector('nav a[href="#blocks"]').addEventListener('click', () => {
            this.loadBlocks();
        });

        // Atualizar a cada 30 segundos
        setInterval(() => this.loadBlocks(), 30000);
    }

    async loadBlocks() {
        try {
            const response = await fetch('/api/blocks');
            const data = await response.json();
            
            if (Array.isArray(data)) {
                this.blocks = data;
                this.updateBlocksUI();
            }
        } catch (error) {
            console.error('Erro ao carregar blocos:', error);
            UI.showError('Erro ao carregar blocos');
        }
    }

    updateBlocksUI() {
        const container = document.getElementById('blocks-container');
        if (!container) return;
        
        container.innerHTML = ''; // Limpar conteúdo atual
        
        if (this.blocks.length === 0) {
            container.innerHTML = '<p class="empty-state">Nenhum bloco minerado ainda.</p>';
            return;
        }

        this.blocks.forEach(block => {
            const blockElement = document.createElement('div');
            blockElement.className = 'block-card';
            
            // Formatar timestamp
            const date = new Date(block.timestamp * 1000);
            const formattedDate = date.toLocaleString();
            
            // Criar conteúdo do bloco
            blockElement.innerHTML = `
                <div class="block-header">
                    <span class="block-number">Bloco #${block.height || '?'}</span>
                    <span class="block-timestamp">${formattedDate}</span>
                </div>
                <div class="block-body">
                    <p class="block-hash">Hash: ${this._truncateHash(block.hash)}</p>
                    <p class="block-prev">Bloco Anterior: ${this._truncateHash(block.previous_hash) || 'Genesis'}</p>
                    <p class="block-nonce">Nonce: ${block.nonce}</p>
                    ${this._formatTransactions(block.transactions)}
                </div>
                <div class="block-footer">
                    <span class="block-status ${block.validation_status === 'Validado' ? 'validated' : ''}">${
                        block.validation_status
                    }</span>
                    ${block.pod_proof ? `<span class="pod-badge">PoD</span>` : ''}
                </div>
            `;
            
            container.appendChild(blockElement);
        });
    }

    _formatTransactions(transactions) {
        if (!transactions) return '<p class="no-transactions">Sem transações</p>';
        
        try {
            // Se transactions for string, tentar fazer parse
            const txs = typeof transactions === 'string' ? JSON.parse(transactions) : transactions;
            
            if (!Array.isArray(txs) || txs.length === 0) {
                return '<p class="no-transactions">Sem transações</p>';
            }
            
            return `
                <div class="transactions-list">
                    <h4>Transações (${txs.length})</h4>
                    <ul>
                        ${txs.map(tx => `
                            <li class="transaction-item">
                                <span class="tx-hash">${this._truncateHash(tx.hash)}</span>
                                <span class="tx-amount">${this._formatAmount(tx.amount)} LGC</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
            `;
        } catch (error) {
            console.error('Erro ao formatar transações:', error);
            return '<p class="no-transactions">Erro ao carregar transações</p>';
        }
    }

    _formatAmount(amount) {
        return parseFloat(amount).toFixed(6);
    }

    _truncateHash(hash) {
        if (!hash) return '-';
        return `${hash.substring(0, 8)}...${hash.substring(hash.length - 8)}`;
    }
}

// Inicializar blockchain quando documento estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    window.blockchain = new Blockchain();
}); 