// Web Worker para mineração
let mining = false;
let difficulty = 0;
let blockTemplate = null;
let minerAddress = null;

self.onmessage = function(e) {
    const { type, address, difficulty: diff, blockTemplate: template } = e.data;
    
    switch (type) {
        case 'start':
            minerAddress = address;
            difficulty = diff;
            blockTemplate = template;
            mining = true;
            mine();
            break;
            
        case 'stop':
            mining = false;
            break;
    }
};

async function mine() {
    if (!mining) return;
    
    try {
        const block = {
            ...blockTemplate,
            miner: minerAddress,
            timestamp: Date.now(),
            nonce: 0
        };
        
        while (mining) {
            block.nonce++;
            const hash = calculateHash(block);
            
            // Notificar progresso
            self.postMessage({ type: 'hash' });
            
            // Verificar se encontrou solução
            if (checkDifficulty(hash, difficulty)) {
                self.postMessage({
                    type: 'solution',
                    data: {
                        nonce: block.nonce,
                        hash: hash,
                        timestamp: block.timestamp
                    }
                });
                
                // Aguardar novo template
                break;
            }
            
            // Evitar bloqueio da UI
            if (block.nonce % 1000 === 0) {
                await new Promise(resolve => setTimeout(resolve, 0));
            }
        }
    } catch (error) {
        self.postMessage({
            type: 'error',
            data: error.message
        });
    }
}

function calculateHash(block) {
    // Implementação simplificada do SHA-256
    const data = JSON.stringify(block);
    return sha256(data);
}

function checkDifficulty(hash, difficulty) {
    // Verificar se o hash começa com o número correto de zeros
    const prefix = '0'.repeat(difficulty);
    return hash.startsWith(prefix);
}

// Implementação do SHA-256 (versão simplificada para exemplo)
function sha256(data) {
    // Esta é uma implementação simplificada
    // Em produção, use uma biblioteca criptográfica real
    let hash = 0;
    for (let i = 0; i < data.length; i++) {
        const char = data.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash;
    }
    return hash.toString(16).padStart(64, '0');
} 