class Miner {
    constructor() {
        this.isRunning = false;
        this.worker = null;
        this.startTime = null;
        this.hashCount = 0;
        this.totalMined = 0;
        this.lastReward = 0;
        this.totalRewards = 0;
        this.setupEventListeners();
    }

    setupEventListeners() {
        document.getElementById('start-mining').addEventListener('click', () => this.startMining());
        document.getElementById('stop-mining').addEventListener('click', () => this.stopMining());
    }

    async startMining() {
        if (this.isRunning) return;
        
        // Verificar se tem wallet conectada
        if (!window.wallet?.address) {
            UI.showError('Conecte uma wallet antes de minerar!');
            return;
        }

        try {
            // Iniciar worker de mineração
            this.worker = new Worker('/static/js/mining-worker.js');
            this.worker.onmessage = (e) => this.handleWorkerMessage(e);
            
            // Configurar mineração
            const response = await fetch('/api/mining/config');
            const config = await response.json();
            
            this.worker.postMessage({
                type: 'start',
                address: window.wallet.address,
                difficulty: config.difficulty,
                blockTemplate: config.blockTemplate
            });

            this.isRunning = true;
            this.startTime = Date.now();
            this.hashCount = 0;
            
            // Atualizar UI
            document.getElementById('mining-status').textContent = 'Minerando';
            document.getElementById('start-mining').disabled = true;
            document.getElementById('stop-mining').disabled = false;
            
            // Iniciar atualização do hash rate
            this.updateHashRate();
        } catch (error) {
            UI.showError('Erro ao iniciar mineração');
            console.error(error);
        }
    }

    stopMining() {
        if (!this.isRunning) return;
        
        this.worker?.terminate();
        this.worker = null;
        this.isRunning = false;
        
        // Atualizar UI
        document.getElementById('mining-status').textContent = 'Parado';
        document.getElementById('start-mining').disabled = false;
        document.getElementById('stop-mining').disabled = true;
        document.getElementById('current-hashrate').textContent = '0 H/s';
    }

    handleWorkerMessage(e) {
        const { type, data } = e.data;
        
        switch (type) {
            case 'hash':
                this.hashCount++;
                break;
                
            case 'solution':
                this.submitSolution(data);
                break;
                
            case 'error':
                console.error('Erro no worker:', data);
                break;
        }
    }

    async submitSolution(solution) {
        try {
            const response = await fetch('/api/mining/submit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    address: window.wallet.address,
                    nonce: solution.nonce,
                    hash: solution.hash,
                    timestamp: solution.timestamp
                })
            });
            
            const result = await response.json();
            if (result.success) {
                this.totalMined++;
                this.lastReward = result.reward;
                this.totalRewards += result.reward;
                
                // Atualizar UI
                document.getElementById('mined-blocks').textContent = this.totalMined;
                document.getElementById('last-reward').textContent = `${this.lastReward} LGC`;
                document.getElementById('total-rewards').textContent = `${this.totalRewards} LGC`;
                
                // Atualizar saldo da wallet
                window.wallet?.updateBalance();
                
                UI.showSuccess(`Bloco minerado! Recompensa: ${result.reward} LGC`);
            }
        } catch (error) {
            console.error('Erro ao submeter solução:', error);
        }
    }

    updateHashRate() {
        if (!this.isRunning) return;
        
        const elapsed = (Date.now() - this.startTime) / 1000;
        const hashRate = this.hashCount / elapsed;
        
        document.getElementById('current-hashrate').textContent = 
            `${this.formatHashRate(hashRate)}`;
        document.getElementById('hash-rate').textContent = 
            `${this.formatHashRate(hashRate)}`;
            
        setTimeout(() => this.updateHashRate(), 1000);
    }

    formatHashRate(hashRate) {
        if (hashRate >= 1e9) {
            return `${(hashRate / 1e9).toFixed(2)} GH/s`;
        } else if (hashRate >= 1e6) {
            return `${(hashRate / 1e6).toFixed(2)} MH/s`;
        } else if (hashRate >= 1e3) {
            return `${(hashRate / 1e3).toFixed(2)} KH/s`;
        } else {
            return `${Math.floor(hashRate)} H/s`;
        }
    }
}

// Inicializar minerador quando documento estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    window.miner = new Miner();
}); 