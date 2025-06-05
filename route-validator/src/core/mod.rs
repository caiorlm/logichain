use serde::{Serialize, Deserialize};
use sha2::{Sha256, Digest};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GeoPoint {
    pub latitude: f64,
    pub longitude: f64,
    pub timestamp: u64,
    pub speed: Option<f32>,
    pub accuracy: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RouteConfig {
    pub contract_id: String,
    pub tolerance_radius: f32,
    pub max_error: f32,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ValidationStatus {
    Started,
    InProgress,
    Completed,
    Failed,
}

#[derive(Debug)]
pub enum ValidationError {
    PointOutOfBounds,
    RouteIncomplete,
    InvalidTimestamp,
}

pub struct RouteValidator {
    config: RouteConfig,
    points: Vec<GeoPoint>,
    status: ValidationStatus,
    proof_hash: Option<String>,
}

impl RouteValidator {
    pub fn new(config: RouteConfig) -> Self {
        Self {
            config,
            points: Vec::new(),
            status: ValidationStatus::Started,
            proof_hash: None,
        }
    }

    pub fn add_point(&mut self, point: GeoPoint) -> Result<ValidationStatus, ValidationError> {
        // Valida timestamp
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();
            
        if point.timestamp > now + 5 || point.timestamp < now - 5 {
            return Err(ValidationError::InvalidTimestamp);
        }

        // Valida precisão se disponível
        if let Some(accuracy) = point.accuracy {
            if accuracy > self.config.max_error {
                return Err(ValidationError::PointOutOfBounds);
            }
        }

        // Adiciona ponto
        self.points.push(point);
        self.status = ValidationStatus::InProgress;
        
        Ok(self.status.clone())
    }

    pub fn generate_proof(&mut self) -> Result<String, ValidationError> {
        if self.points.len() < 2 {
            return Err(ValidationError::RouteIncomplete);
        }

        // Gera hash da rota
        let mut hasher = Sha256::new();
        
        for point in &self.points {
            let point_data = format!(
                "{},{},{},{}",
                point.latitude,
                point.longitude,
                point.timestamp,
                point.accuracy.unwrap_or(0.0)
            );
            hasher.update(point_data.as_bytes());
        }

        let proof = format!("{:x}", hasher.finalize());
        self.proof_hash = Some(proof.clone());
        self.status = ValidationStatus::Completed;
        
        Ok(proof)
    }

    pub fn get_status(&self) -> ValidationStatus {
        self.status.clone()
    }

    pub fn get_points(&self) -> &[GeoPoint] {
        &self.points
    }
} 