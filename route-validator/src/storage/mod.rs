use rusqlite::{Connection, Result as SqlResult, params};
use crate::core::{GeoPoint, RouteValidator, ValidationStatus};
use std::path::Path;

pub struct LocalStorage {
    conn: Connection,
}

impl LocalStorage {
    pub fn new<P: AsRef<Path>>(path: P) -> SqlResult<Self> {
        let conn = Connection::open(path)?;
        
        // Cria tabelas se não existirem
        conn.execute(
            "CREATE TABLE IF NOT EXISTS routes (
                id TEXT PRIMARY KEY,
                contract_id TEXT NOT NULL,
                status TEXT NOT NULL,
                start_time INTEGER NOT NULL,
                end_time INTEGER,
                proof_hash TEXT
            )",
            [],
        )?;

        conn.execute(
            "CREATE TABLE IF NOT EXISTS points (
                id INTEGER PRIMARY KEY,
                route_id TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                speed REAL,
                accuracy REAL,
                FOREIGN KEY(route_id) REFERENCES routes(id)
            )",
            [],
        )?;

        Ok(Self { conn })
    }

    pub fn save_route(&self, validator: &RouteValidator) -> SqlResult<()> {
        let tx = self.conn.transaction()?;

        // Insere rota
        tx.execute(
            "INSERT INTO routes (id, contract_id, status, start_time)
             VALUES (?1, ?2, ?3, ?4)",
            params![
                validator.id(),
                validator.contract_id(),
                validator.get_status().to_string(),
                validator.get_points().first().map(|p| p.timestamp).unwrap_or(0)
            ],
        )?;

        // Insere pontos
        for point in validator.get_points() {
            tx.execute(
                "INSERT INTO points (route_id, latitude, longitude, timestamp, speed, accuracy)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
                params![
                    validator.id(),
                    point.latitude,
                    point.longitude,
                    point.timestamp,
                    point.speed,
                    point.accuracy
                ],
            )?;
        }

        tx.commit()?;
        Ok(())
    }

    pub fn update_route_status(&self, route_id: &str, status: ValidationStatus) -> SqlResult<()> {
        self.conn.execute(
            "UPDATE routes SET status = ?1 WHERE id = ?2",
            params![status.to_string(), route_id],
        )?;
        Ok(())
    }

    pub fn get_route(&self, route_id: &str) -> SqlResult<Option<RouteValidator>> {
        // Implementar recuperação da rota do banco
        // Por enquanto retorna None
        Ok(None)
    }
} 