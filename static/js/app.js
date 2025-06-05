class BlockchainApp {
    constructor() {
        this.isOnline = false;
        this.lastSync = null;
        this.initializeApp();
    }

    async initializeApp() {
        this.updateNetworkStatus();
        this.setupEventListeners();
        await this.loadInitialData();
        this.startPeriodicSync();
    }

    updateNetworkStatus() {
        const modeIndicator = document.getElementById('mode-indicator');
        const syncStatus = document.getElementById('sync-status');
        
        // Verificar status da rede
        fetch('/api/mode')
            .then(response => response.json())
            .then(data => {
                this.isOnline = data.online;
                modeIndicator.textContent = this.isOnline ? 'Online' : 'Offline';
                modeIndicator.className = this.isOnline ? 'online' : 'offline';
            })
            .catch(() => {
                this.isOnline = false;
                modeIndicator.textContent = 'Offline';
                modeIndicator.className = 'offline';
            });

        // Atualizar status de sincronização
        if (this.lastSync) {
            const lastSyncDate = new Date(this.lastSync).toLocaleString();
            syncStatus.textContent = `Última sincronização: ${lastSyncDate}`;
        }
    }

    setupEventListeners() {
        // Navegação
        document.querySelectorAll('.sidebar a').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                this.navigateTo(e.target.getAttribute('href').substring(1));
            });
        });

        // Monitor de conexão
        window.addEventListener('online', () => this.handleConnectivityChange(true));
        window.addEventListener('offline', () => this.handleConnectivityChange(false));
    }

    async loadInitialData() {
        try {
            // Carregar estatísticas
            const stats = await this.fetchWithCache('/api/stats');
            this.updateStats(stats);

            // Carregar blocos recentes
            const blocks = await this.fetchWithCache('/api/blocks');
            this.updateBlocks(blocks);

            // Carregar contratos pendentes
            const contracts = await this.fetchWithCache('/api/contracts/pending');
            this.updateContracts(contracts);

            this.lastSync = new Date();
            this.updateNetworkStatus();
        } catch (error) {
            console.error('Erro ao carregar dados iniciais:', error);
        }
    }

    async fetchWithCache(url) {
        try {
            const response = await fetch(url);
            return await response.json();
        } catch (error) {
            // Tentar recuperar do cache se offline
            const cache = await caches.open('blockchain-logistics-v1');
            const cachedResponse = await cache.match(url);
            if (cachedResponse) {
                return await cachedResponse.json();
            }
            throw error;
        }
    }

    updateStats(stats) {
        document.getElementById('total-blocks').textContent = stats.total_blocks;
        document.getElementById('active-contracts').textContent = stats.total_contracts;
        document.getElementById('network-status').textContent = 
            stats.online_mode ? 'Conectado' : 'Desconectado';
    }

    updateBlocks(blocks) {
        const container = document.getElementById('blocks-container');
        container.innerHTML = blocks.map(block => `
            <div class="block-item">
                <h3>Bloco ${block.hash.substring(0, 8)}...</h3>
                <p>Contrato: ${block.contract_id}</p>
                <p>Data: ${block.timestamp}</p>
                <p>Origem: ${block.start_coords.join(', ')}</p>
                <p>Destino: ${block.end_coords.join(', ')}</p>
            </div>
        `).join('');
    }

    updateContracts(contracts) {
        const container = document.getElementById('contracts-container');
        container.innerHTML = contracts.map(contract => `
            <div class="contract-item">
                <h3>Contrato ${contract.id}</h3>
                <p>Status: ${contract.status}</p>
                <p>Origem: ${contract.pickup_location.join(', ')}</p>
                <p>Destino: ${contract.delivery_location.join(', ')}</p>
            </div>
        `).join('');
    }

    navigateTo(section) {
        // Esconder todas as seções
        document.querySelectorAll('main section').forEach(s => {
            s.classList.add('hidden');
        });

        // Mostrar seção selecionada
        document.getElementById(section).classList.remove('hidden');

        // Atualizar navegação
        document.querySelectorAll('.sidebar a').forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === `#${section}`) {
                link.classList.add('active');
            }
        });
    }

    handleConnectivityChange(isOnline) {
        this.isOnline = isOnline;
        this.updateNetworkStatus();
        if (isOnline) {
            this.loadInitialData();
        }
    }

    startPeriodicSync() {
        // Sincronizar a cada 30 segundos se online
        setInterval(() => {
            if (this.isOnline) {
                this.loadInitialData();
            }
        }, 30000);
    }
}

// Inicializar aplicação
window.addEventListener('load', () => {
    window.app = new BlockchainApp();
});

// Gerenciamento de Abas
function setupTabs() {
    const tabs = document.querySelectorAll('.sidebar a');
    const sections = document.querySelectorAll('main section');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            
            // Remover classe active de todas as abas
            tabs.forEach(t => t.classList.remove('active'));
            
            // Adicionar classe active na aba clicada
            tab.classList.add('active');
            
            // Esconder todas as seções
            sections.forEach(section => section.classList.remove('active-section'));
            
            // Mostrar seção correspondente
            const targetId = tab.getAttribute('href').substring(1);
            document.getElementById(targetId).classList.add('active-section');
        });
    });
}

// Atualização de Estatísticas
async function updateStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        document.getElementById('total-blocks').textContent = data.total_blocks;
        document.getElementById('active-contracts').textContent = data.total_contracts;
        document.getElementById('token-supply').textContent = `${data.total_supply} LGC`;
        
        const modeIndicator = document.getElementById('mode-indicator');
        modeIndicator.textContent = data.online_mode ? 'Online' : 'Offline';
        modeIndicator.className = data.online_mode ? 'online' : 'offline';
        
        document.getElementById('sync-status').textContent = 
            `Última sincronização: ${data.last_update}`;
    } catch (error) {
        console.error('Erro ao atualizar estatísticas:', error);
    }
}

// Atualização de Blocos
async function updateBlocks() {
    try {
        const response = await fetch('/api/blocks');
        const blocks = await response.json();
        
        const container = document.getElementById('blocks-container');
        container.innerHTML = blocks.map(block => UI.createBlockCard(block)).join('');
    } catch (error) {
        console.error('Erro ao atualizar blocos:', error);
    }
}

// Atualização de Contratos
async function updateContracts() {
    try {
        const response = await fetch('/api/contracts/pending');
        const contracts = await response.json();
        
        const container = document.getElementById('contracts-container');
        container.innerHTML = contracts.map(contract => UI.createContractCard(contract)).join('');
    } catch (error) {
        console.error('Erro ao atualizar contratos:', error);
    }
}

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    // Configurar navegação
    setupTabs();
    
    // Atualizar dados iniciais
    updateStats();
    updateBlocks();
    updateContracts();
    
    // Configurar atualizações periódicas
    setInterval(updateStats, 10000);  // 10 segundos
    setInterval(updateBlocks, 30000); // 30 segundos
    setInterval(updateContracts, 60000); // 1 minuto
}); 