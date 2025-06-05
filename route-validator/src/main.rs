mod core;
mod gps;
mod storage;
mod blockchain;
mod api;
mod cli;

use crate::core::RouteValidator;
use crate::gps::GPSCollector;
use crate::storage::LocalStorage;
use crate::blockchain::BlockchainIntegrator;

#[tokio::main]
async fn main() {
    println!("Route Validator v1.0");
    
    // Inicializa componentes
    let storage = LocalStorage::new("routes.db").expect("Failed to initialize storage");
    let validator = RouteValidator::new();
    let blockchain = BlockchainIntegrator::new();
    
    // Inicia API REST
    api::start_server(storage.clone(), validator.clone(), blockchain.clone()).await;
} 