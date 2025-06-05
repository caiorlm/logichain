use std::sync::mpsc::{channel, Sender, Receiver};
use std::time::{SystemTime, UNIX_EPOCH};
use crate::core::GeoPoint;

#[derive(Debug)]
pub enum GPSError {
    DeviceError,
    ReadError,
    InvalidData,
}

pub struct GPSConfig {
    pub device_path: String,
    pub collection_interval_ms: u64,
    pub min_accuracy: f32,
}

pub struct GPSCollector {
    config: GPSConfig,
    tx: Sender<GeoPoint>,
}

impl GPSCollector {
    pub fn new(config: GPSConfig) -> Result<(Self, Receiver<GeoPoint>), GPSError> {
        let (tx, rx) = channel();
        
        Ok((Self { config, tx }, rx))
    }

    pub fn start_collection(&self) {
        let tx = self.tx.clone();
        let config = self.config.clone();

        std::thread::spawn(move || {
            loop {
                if let Ok(point) = Self::read_gps_data(&config) {
                    tx.send(point).ok();
                }

                std::thread::sleep(std::time::Duration::from_millis(
                    config.collection_interval_ms
                ));
            }
        });
    }

    fn read_gps_data(config: &GPSConfig) -> Result<GeoPoint, GPSError> {
        // Simulação de leitura GPS (em produção, usar biblioteca GPS real)
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        Ok(GeoPoint {
            latitude: 0.0,
            longitude: 0.0,
            timestamp: now,
            speed: Some(0.0),
            accuracy: Some(config.min_accuracy),
        })
    }
} 