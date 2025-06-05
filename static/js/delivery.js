class DeliverySystem {
    constructor() {
        this.currentDelivery = null;
        this.photos = [];
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Botões principais
        document.getElementById('start-delivery').addEventListener('click', () => this.startDelivery());
        document.getElementById('complete-delivery').addEventListener('click', () => this.completeDelivery());
        document.getElementById('add-photo').addEventListener('click', () => this.addPhoto());
        
        // Formulário de entrega
        document.getElementById('delivery-form').addEventListener('submit', (e) => this.submitDelivery(e));
    }

    async startDelivery() {
        if (!window.wallet?.address) {
            UI.showError('Conecte sua wallet primeiro!');
            return;
        }

        try {
            // Gerar ID único para a entrega
            const deliveryId = `DEL${Date.now()}${Math.random().toString(36).substring(7)}`;
            
            // Pegar coordenadas atuais
            const position = await this.getCurrentPosition();
            
            this.currentDelivery = {
                id: deliveryId,
                contract_id: document.getElementById('contract-id').value,
                driver_address: window.wallet.address,
                receiver_address: document.getElementById('receiver-address').value,
                pickup_coords: [position.coords.latitude, position.coords.longitude],
                pickup_time: Math.floor(Date.now() / 1000),
                photos: []
            };
            
            // Atualizar UI
            document.getElementById('delivery-status').textContent = 'Em andamento';
            document.getElementById('pickup-coords').textContent = 
                `${position.coords.latitude.toFixed(6)}, ${position.coords.longitude.toFixed(6)}`;
            document.getElementById('pickup-time').textContent = 
                new Date().toLocaleString();
                
            UI.showSuccess('Entrega iniciada!');
            
        } catch (error) {
            UI.showError('Erro ao iniciar entrega: ' + error.message);
            console.error(error);
        }
    }

    async completeDelivery() {
        if (!this.currentDelivery) {
            UI.showError('Nenhuma entrega em andamento');
            return;
        }

        try {
            // Pegar coordenadas finais
            const position = await this.getCurrentPosition();
            
            // Calcular distância
            const distance = this.calculateDistance(
                this.currentDelivery.pickup_coords,
                [position.coords.latitude, position.coords.longitude]
            );
            
            // Completar dados da entrega
            this.currentDelivery.delivery_coords = [
                position.coords.latitude,
                position.coords.longitude
            ];
            this.currentDelivery.delivery_time = Math.floor(Date.now() / 1000);
            this.currentDelivery.distance_km = distance;
            
            // Atualizar UI
            document.getElementById('delivery-coords').textContent = 
                `${position.coords.latitude.toFixed(6)}, ${position.coords.longitude.toFixed(6)}`;
            document.getElementById('delivery-time').textContent = 
                new Date().toLocaleString();
            document.getElementById('distance').textContent = 
                `${distance.toFixed(2)} km`;
                
            // Mostrar modal de assinatura
            this.showSignatureModal();
            
        } catch (error) {
            UI.showError('Erro ao completar entrega: ' + error.message);
            console.error(error);
        }
    }

    async addPhoto() {
        if (!this.currentDelivery) {
            UI.showError('Inicie uma entrega primeiro');
            return;
        }

        try {
            // Simular upload para IPFS (implementar integração real depois)
            const photoHash = `QmHash${Date.now()}${Math.random().toString(36).substring(7)}`;
            
            this.currentDelivery.photos.push(photoHash);
            
            // Atualizar UI
            const photoList = document.getElementById('photo-list');
            const li = document.createElement('li');
            li.textContent = `Foto ${this.currentDelivery.photos.length}`;
            photoList.appendChild(li);
            
            UI.showSuccess('Foto adicionada!');
            
        } catch (error) {
            UI.showError('Erro ao adicionar foto: ' + error.message);
            console.error(error);
        }
    }

    showSignatureModal() {
        const modal = document.getElementById('signature-modal');
        modal.style.display = 'block';
        
        // Botão de confirmar
        document.getElementById('confirm-signature').onclick = () => {
            const receiverKey = document.getElementById('receiver-key').value;
            this.submitDelivery(receiverKey);
            modal.style.display = 'none';
        };
        
        // Botão de cancelar
        document.getElementById('cancel-signature').onclick = () => {
            modal.style.display = 'none';
        };
    }

    async submitDelivery(receiverKey) {
        if (!this.currentDelivery) {
            UI.showError('Nenhuma entrega para finalizar');
            return;
        }

        try {
            const response = await fetch('/api/delivery/submit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    contract_id: this.currentDelivery.contract_id,
                    delivery_id: this.currentDelivery.id,
                    driver_address: this.currentDelivery.driver_address,
                    receiver_address: this.currentDelivery.receiver_address,
                    pickup_coords: this.currentDelivery.pickup_coords,
                    delivery_coords: this.currentDelivery.delivery_coords,
                    pickup_time: this.currentDelivery.pickup_time,
                    delivery_time: this.currentDelivery.delivery_time,
                    distance_km: this.currentDelivery.distance_km,
                    photos: this.currentDelivery.photos,
                    driver_key: window.wallet.privateKey,
                    receiver_key: receiverKey
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                UI.showSuccess('Entrega finalizada com sucesso!');
                
                // Limpar entrega atual
                this.currentDelivery = null;
                
                // Atualizar UI
                document.getElementById('delivery-status').textContent = 'Concluída';
                document.getElementById('photo-list').innerHTML = '';
                
                // Atualizar saldo da wallet
                if (window.wallet) {
                    window.wallet.updateBalance();
                }
            } else {
                UI.showError(data.error || 'Erro ao finalizar entrega');
            }
            
        } catch (error) {
            UI.showError('Erro ao finalizar entrega: ' + error.message);
            console.error(error);
        }
    }

    getCurrentPosition() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject(new Error('Geolocalização não suportada'));
                return;
            }
            
            navigator.geolocation.getCurrentPosition(resolve, reject, {
                enableHighAccuracy: true,
                timeout: 5000,
                maximumAge: 0
            });
        });
    }

    calculateDistance(pickup, delivery) {
        const R = 6371; // Raio da Terra em km
        
        const lat1 = this.toRad(pickup[0]);
        const lon1 = this.toRad(pickup[1]);
        const lat2 = this.toRad(delivery[0]);
        const lon2 = this.toRad(delivery[1]);
        
        const dlon = lon2 - lon1;
        const dlat = lat2 - lat1;
        
        const a = Math.sin(dlat/2) * Math.sin(dlat/2) +
                Math.cos(lat1) * Math.cos(lat2) *
                Math.sin(dlon/2) * Math.sin(dlon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        
        return R * c;
    }

    toRad(degrees) {
        return degrees * Math.PI / 180;
    }

    async getDeliveryHistory(address) {
        try {
            const response = await fetch(`/api/delivery/history/${address}`);
            const data = await response.json();
            
            if (data.success) {
                this.updateDeliveryList(data.proofs);
            } else {
                console.error('Erro ao buscar histórico:', data.error);
            }
        } catch (error) {
            console.error('Erro ao buscar histórico:', error);
        }
    }

    updateDeliveryList(proofs) {
        const container = document.getElementById('delivery-list');
        const template = document.getElementById('delivery-template');
        
        container.innerHTML = '';
        
        proofs.forEach(proof => {
            const clone = template.content.cloneNode(true);
            
            clone.querySelector('.delivery-id').textContent = proof.delivery_id;
            clone.querySelector('.delivery-contract').textContent = proof.contract_id;
            clone.querySelector('.delivery-distance').textContent = 
                `${proof.distance_km.toFixed(2)} km`;
            clone.querySelector('.delivery-reward').textContent = 
                `${proof.reward.toFixed(6)} LGC`;
            clone.querySelector('.delivery-status').textContent = 
                proof.block_hash ? 'Confirmada' : 'Pendente';
            
            const pickupTime = new Date(proof.pickup_time * 1000);
            const deliveryTime = new Date(proof.delivery_time * 1000);
            
            clone.querySelector('.delivery-pickup').textContent = 
                pickupTime.toLocaleString();
            clone.querySelector('.delivery-complete').textContent = 
                deliveryTime.toLocaleString();
            
            container.appendChild(clone);
        });
    }
}

// Inicializar sistema quando documento estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    window.delivery = new DeliverySystem();
    
    // Carregar histórico se wallet estiver conectada
    if (window.wallet?.address) {
        window.delivery.getDeliveryHistory(window.wallet.address);
    }
}); 