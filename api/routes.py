from flask import Flask, jsonify, request
from blockchain.core.blockchain import Blockchain
from blockchain.core.contract import Contract

app = Flask(__name__)
blockchain = Blockchain()

@app.route('/coordinates', methods=['GET'])
def get_coordinates():
    """Get all coordinates or filter by lat/lng."""
    lat = request.args.get('lat', type=int)
    lng = request.args.get('lng', type=int)
    
    if lat is not None and lng is not None:
        coord = blockchain.coordinate_grid.get_coordinate(lat, lng)
        return jsonify(coord if coord else {})
    
    # Retorna coordenadas com atividade
    active_coords = {
        hash: data for hash, data in blockchain.coordinate_grid.grid.items()
        if data['statistics']['total_contracts'] > 0
    }
    return jsonify(active_coords)

@app.route('/coordinates/<lat>/<lng>/contracts', methods=['GET'])
def get_coordinate_contracts(lat, lng):
    """Get all contracts for a coordinate."""
    status = request.args.get('status')
    coord = blockchain.coordinate_grid.get_coordinate(int(lat), int(lng))
    
    if not coord:
        return jsonify({'error': 'Coordinate not found'}), 404
        
    if status:
        contracts = blockchain.coordinate_grid.get_contracts_by_status(int(lat), int(lng), status)
    else:
        contracts = coord['contracts']
        
    return jsonify({
        'coordinate': {'lat': lat, 'lng': lng},
        'contracts': contracts
    })

@app.route('/contracts/<contract_hash>', methods=['GET'])
def get_contract(contract_hash):
    """Get contract details by hash."""
    # Busca em todas as coordenadas (pode ser otimizado com índice)
    for coord_data in blockchain.coordinate_grid.grid.values():
        for contract in coord_data['contracts']:
            if contract['contract_hash'] == contract_hash:
                return jsonify(contract)
    
    return jsonify({'error': 'Contract not found'}), 404

@app.route('/contracts', methods=['POST'])
def create_contract():
    """Create new delivery contract."""
    data = request.json
    
    try:
        contract_hash = blockchain.initiate_contract(
            initiator=data['initiator'],
            coordinates={
                'lat': data['lat'],
                'lng': data['lng']
            },
            contract_data=data['contract_data']
        )
        
        if contract_hash:
            return jsonify({
                'status': 'success',
                'contract_hash': contract_hash
            })
        
        return jsonify({'error': 'Failed to create contract'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/contracts/<contract_hash>/accept', methods=['POST'])
def accept_contract(contract_hash):
    """Accept an existing contract."""
    data = request.json
    
    success = blockchain.accept_contract(
        contract_hash=contract_hash,
        acceptor=data['acceptor'],
        coordinates={
            'lat': data['lat'],
            'lng': data['lng']
        }
    )
    
    if success:
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Failed to accept contract'}), 400

@app.route('/contracts/<contract_hash>/checkpoint', methods=['POST'])
def add_checkpoint(contract_hash):
    """Add POD checkpoint to contract."""
    data = request.json
    
    success = blockchain.add_pod_checkpoint(
        contract_hash=contract_hash,
        coordinates={
            'lat': data['lat'],
            'lng': data['lng']
        },
        checkpoint_data=data['checkpoint_data']
    )
    
    if success:
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Failed to add checkpoint'}), 400

@app.route('/contracts/<contract_hash>/complete', methods=['POST'])
def complete_contract(contract_hash):
    """Complete a contract with final POD."""
    data = request.json
    
    success = blockchain.complete_contract(
        contract_hash=contract_hash,
        coordinates={
            'lat': data['lat'],
            'lng': data['lng']
        },
        final_pod=data['final_pod'],
        mining_data=data['mining_data']
    )
    
    if success:
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Failed to complete contract'}), 400

@app.route('/statistics', methods=['GET'])
def get_statistics():
    """Get global statistics."""
    stats = {
        'total_coordinates': len(blockchain.coordinate_grid.grid),
        'active_coordinates': sum(
            1 for coord in blockchain.coordinate_grid.grid.values()
            if coord['statistics']['total_contracts'] > 0
        ),
        'total_contracts': sum(
            coord['statistics']['total_contracts']
            for coord in blockchain.coordinate_grid.grid.values()
        ),
        'successful_deliveries': sum(
            coord['statistics']['successful_deliveries']
            for coord in blockchain.coordinate_grid.grid.values()
        )
    }
    return jsonify(stats)

if __name__ == '__main__':
    app.run(debug=True) 