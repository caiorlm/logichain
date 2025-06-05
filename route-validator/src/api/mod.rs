use actix_web::{web, App, HttpServer, HttpResponse, Responder};
use serde::{Serialize, Deserialize};
use crate::core::{RouteValidator, GeoPoint, RouteConfig};
use crate::storage::LocalStorage;
use crate::blockchain::BlockchainIntegrator;

#[derive(Deserialize)]
struct StartRouteRequest {
    contract_id: String,
    tolerance_radius: f32,
    max_error: f32,
}

#[derive(Deserialize)]
struct AddPointRequest {
    latitude: f64,
    longitude: f64,
    speed: Option<f32>,
    accuracy: Option<f32>,
}

#[derive(Serialize)]
struct RouteResponse {
    status: String,
    points: Vec<GeoPoint>,
    proof_hash: Option<String>,
}

pub struct AppState {
    storage: LocalStorage,
    validator: RouteValidator,
    blockchain: BlockchainIntegrator,
}

async fn start_route(
    data: web::Json<StartRouteRequest>,
    state: web::Data<AppState>,
) -> impl Responder {
    let config = RouteConfig {
        contract_id: data.contract_id.clone(),
        tolerance_radius: data.tolerance_radius,
        max_error: data.max_error,
    };

    let validator = RouteValidator::new(config);
    
    match state.storage.save_route(&validator) {
        Ok(_) => HttpResponse::Ok().json(RouteResponse {
            status: validator.get_status().to_string(),
            points: Vec::new(),
            proof_hash: None,
        }),
        Err(_) => HttpResponse::InternalServerError().finish(),
    }
}

async fn add_point(
    data: web::Json<AddPointRequest>,
    state: web::Data<AppState>,
) -> impl Responder {
    let point = GeoPoint {
        latitude: data.latitude,
        longitude: data.longitude,
        timestamp: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs(),
        speed: data.speed,
        accuracy: data.accuracy,
    };

    match state.validator.add_point(point) {
        Ok(status) => {
            if let Err(_) = state.storage.save_route(&state.validator) {
                return HttpResponse::InternalServerError().finish();
            }

            HttpResponse::Ok().json(RouteResponse {
                status: status.to_string(),
                points: state.validator.get_points().to_vec(),
                proof_hash: None,
            })
        },
        Err(_) => HttpResponse::BadRequest().finish(),
    }
}

async fn end_route(state: web::Data<AppState>) -> impl Responder {
    match state.validator.generate_proof() {
        Ok(proof) => {
            // Envia para blockchain
            if let Ok(_) = state.blockchain.submit_proof(&state.validator) {
                HttpResponse::Ok().json(RouteResponse {
                    status: state.validator.get_status().to_string(),
                    points: state.validator.get_points().to_vec(),
                    proof_hash: Some(proof),
                })
            } else {
                HttpResponse::InternalServerError().finish()
            }
        },
        Err(_) => HttpResponse::BadRequest().finish(),
    }
}

pub async fn start_server(
    storage: LocalStorage,
    validator: RouteValidator,
    blockchain: BlockchainIntegrator,
) -> std::io::Result<()> {
    let state = web::Data::new(AppState {
        storage,
        validator,
        blockchain,
    });

    HttpServer::new(move || {
        App::new()
            .app_data(state.clone())
            .route("/start", web::post().to(start_route))
            .route("/point", web::post().to(add_point))
            .route("/end", web::post().to(end_route))
    })
    .bind("127.0.0.1:8080")?
    .run()
    .await
} 