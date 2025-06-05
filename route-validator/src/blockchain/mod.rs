use ed25519_dalek::{Keypair, PublicKey, SecretKey, Signature};
use sha2::{Sha256, Digest};
use crate::core::{RouteValidator, GeoPoint};

#[derive(Debug)]
pub enum BlockchainError {
    SigningError,
    ValidationError,
    NetworkError,
}

pub struct BlockchainConfig {
    pub network_url: String,
    pub contract_address: String,
}

pub struct BlockchainIntegrator {
    config: BlockchainConfig,
    keypair: Keypair,
}

impl BlockchainIntegrator {
    pub fn new(config: BlockchainConfig, secret_key: &[u8]) -> Result<Self, BlockchainError> {
        let keypair = Keypair::from_bytes(secret_key)
            .map_err(|_| BlockchainError::SigningError)?;

        Ok(Self { config, keypair })
    }

    pub fn sign_point(&self, point: &GeoPoint) -> Result<Signature, BlockchainError> {
        let message = format!(
            "{},{},{},{}",
            point.latitude,
            point.longitude,
            point.timestamp,
            point.accuracy.unwrap_or(0.0)
        );

        Ok(self.keypair.sign(message.as_bytes()))
    }

    pub fn submit_proof(&self, validator: &RouteValidator) -> Result<String, BlockchainError> {
        // Gera proof of delivery
        let proof = validator.generate_proof()
            .map_err(|_| BlockchainError::ValidationError)?;

        // Assina o proof
        let signature = self.keypair.sign(proof.as_bytes());

        // Prepara payload
        let payload = ProofPayload {
            contract_id: validator.contract_id().to_string(),
            proof_hash: proof.clone(),
            signature: signature.to_bytes().to_vec(),
            public_key: self.keypair.public.to_bytes().to_vec(),
            points: validator.get_points().to_vec(),
        };

        // Em produção: enviar para blockchain
        // Por enquanto apenas retorna o hash
        Ok(proof)
    }
}

#[derive(Debug)]
struct ProofPayload {
    contract_id: String,
    proof_hash: String,
    signature: Vec<u8>,
    public_key: Vec<u8>,
    points: Vec<GeoPoint>,
} 