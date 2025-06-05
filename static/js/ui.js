// UI Helper Functions
class UI {
    static showLoading() {
        // Implementar indicador de carregamento
    }

    static hideLoading() {
        // Implementar remoção do indicador
    }

    static showError(message) {
        // Criar elemento de notificação
        const notification = document.createElement('div');
        notification.className = 'notification error';
        notification.textContent = message;
        
        // Adicionar ao DOM
        document.body.appendChild(notification);
        
        // Remover após 3 segundos
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    static showSuccess(message) {
        // Criar elemento de notificação
        const notification = document.createElement('div');
        notification.className = 'notification success';
        notification.textContent = message;
        
        // Adicionar ao DOM
        document.body.appendChild(notification);
        
        // Remover após 3 segundos
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    static formatDate(timestamp) {
        return new Date(timestamp * 1000).toLocaleString();
    }

    static formatCoordinates(coords) {
        if (!Array.isArray(coords) || coords.length !== 2) {
            return 'Coordenadas inválidas';
        }
        return `${coords[0].toFixed(6)}, ${coords[1].toFixed(6)}`;
    }

    static truncateHash(hash) {
        if (!hash) return '-';
        return `${hash.substring(0, 8)}...${hash.substring(hash.length - 8)}`;
    }

    static updateTheme(isDark = false) {
        document.body.classList.toggle('dark-theme', isDark);
    }

    static createBlockCard(block) {
        const isGenesis = block.contract_id === 'genesis';
        return `
            <div class="block-item ${isGenesis ? 'genesis-block' : ''}" data-hash="${block.hash}">
                <div class="block-header">
                    <h3>${isGenesis ? 'Bloco Genesis' : 'Bloco'} ${UI.truncateHash(block.hash)}</h3>
                    <span class="timestamp">${UI.formatDate(block.timestamp)}</span>
                </div>
                <div class="block-content">
                    <p><strong>Contrato:</strong> ${block.contract_id}</p>
                    <p><strong>Hash Anterior:</strong> ${UI.truncateHash(block.previous_hash)}</p>
                    <p><strong>Hash da Entrega:</strong> ${UI.truncateHash(block.delivery_hash)}</p>
                    <p><strong>Origem:</strong> ${UI.formatCoordinates(block.start_coords)}</p>
                    <p><strong>Destino:</strong> ${UI.formatCoordinates(block.end_coords)}</p>
                    <p><strong>Status:</strong> <span class="status ${block.validation_status}">${block.validation_status}</span></p>
                    <p><strong>Criado em:</strong> ${UI.formatDate(block.created_at)}</p>
                    ${block.validated_at ? `<p><strong>Validado em:</strong> ${UI.formatDate(block.validated_at)}</p>` : ''}
                </div>
            </div>
        `;
    }

    static createContractCard(contract) {
        return `
            <div class="contract-item" data-id="${contract.id}">
                <div class="contract-header">
                    <h3>Contrato ${contract.id}</h3>
                    <span class="status ${contract.status}">${contract.status}</span>
                </div>
                <div class="contract-content">
                    <p><strong>Origem:</strong> ${UI.formatCoordinates(contract.pickup_location)}</p>
                    <p><strong>Destino:</strong> ${UI.formatCoordinates(contract.delivery_location)}</p>
                    <p><strong>Criado em:</strong> ${UI.formatDate(contract.timestamp)}</p>
                </div>
            </div>
        `;
    }

    static setupNavigation() {
        // Adicionar listeners para navegação
        document.querySelectorAll('nav a').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                
                // Remover classe active de todos os links
                document.querySelectorAll('nav a').forEach(l => l.classList.remove('active'));
                
                // Adicionar classe active ao link clicado
                link.classList.add('active');
                
                // Esconder todas as seções
                document.querySelectorAll('main > section').forEach(section => {
                    section.classList.add('hidden');
                });
                
                // Mostrar seção correspondente
                const targetId = link.getAttribute('href').substring(1);
                const targetSection = document.getElementById(targetId);
                if (targetSection) {
                    targetSection.classList.remove('hidden');
                }
            });
        });
    }

    static updateNetworkStatus(isOnline) {
        const indicator = document.getElementById('mode-indicator');
        if (indicator) {
            indicator.className = isOnline ? 'online' : 'offline';
            indicator.textContent = isOnline ? 'Online' : 'Offline';
        }
    }

    static updateSyncStatus(lastSync) {
        const status = document.getElementById('sync-status');
        if (status) {
            status.textContent = `Última sincronização: ${this.formatDate(lastSync)}`;
        }
    }

    static updateStats(stats) {
        if (stats.total_blocks) {
            document.getElementById('total-blocks').textContent = stats.total_blocks;
        }
        if (stats.total_contracts) {
            document.getElementById('active-contracts').textContent = stats.total_contracts;
        }
        if (stats.total_supply) {
            document.getElementById('token-supply').textContent = `${stats.total_supply.toFixed(6)} LGC`;
        }
        if (stats.last_update) {
            this.updateSyncStatus(new Date(stats.last_update).getTime() / 1000);
        }
        if (typeof stats.online_mode === 'boolean') {
            this.updateNetworkStatus(stats.online_mode);
        }
    }
}

// Inicializar UI quando documento estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    UI.setupNavigation();
    
    // Carregar estatísticas iniciais
    fetch('/api/stats')
        .then(response => response.json())
        .then(stats => UI.updateStats(stats))
        .catch(error => console.error('Erro ao carregar estatísticas:', error));
}); 