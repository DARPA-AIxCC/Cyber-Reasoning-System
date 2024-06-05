use axum::extract::Path;
use axum::response::IntoResponse;
use axum::routing::{get, post};
use axum::{http::StatusCode, Json, Router};
use base64::engine::general_purpose;
use base64::Engine;
use lib_iapi::{
    status_accepted_cpv, status_accepted_gp, status_accepted_vd, status_health_ok, status_rejected,
    status_unknown,
};
use lib_iapi::{GeneratePatchCheckRequest, ProofOfVulnerabilityDiscovery};
use log::info;
use tokio::net::TcpListener;
use uuid::Uuid;
use uuid::Version::Random;

pub type Result<T> = core::result::Result<T, Error>;
pub type Error = Box<dyn std::error::Error>;

async fn get_health() -> impl IntoResponse {
    println!("Health called");

    (StatusCode::OK, Json(status_health_ok()))
}

async fn submit_proof_of_vulnerability_discovery(
    Json(payload): Json<ProofOfVulnerabilityDiscovery>,
) -> impl IntoResponse {
    println!("submission called: {payload:#?}");
    // GUID value
    if payload.pou.commit_sha1.len() != 40 {
        return (StatusCode::OK, Json(status_unknown("Invalid sha1 length")));
    }

    // Check if valid ID: "id_**"
    if let Some(id_value) = payload.pou.sanitizer.strip_prefix("id_") {
        if id_value.parse::<u64>().is_err() {
            return (StatusCode::OK, Json(status_unknown("Invalid sanitizer ID")));
        }
    } else {
        return (StatusCode::OK, Json(status_unknown("Invalid sanitizer ID")));
    }

    // Check if data field is valid
    if general_purpose::STANDARD.decode(payload.pov.data).is_err() {
        return (StatusCode::OK, Json(status_rejected()));
    }

    (StatusCode::OK, Json(status_accepted_vd(Uuid::new_v4())))
}

async fn get_proof_of_vulnerability_status(Path(vd_uuid): Path<String>) -> impl IntoResponse {
    println!("vds with path called: {vd_uuid}");

    if let Err(error_message) = validate_uuid(vd_uuid) {
        return (
            StatusCode::OK,
            Json(status_unknown(error_message.to_string().as_str())),
        );
    }

    (StatusCode::OK, Json(status_accepted_cpv(Uuid::new_v4())))
}

/// Validates the UUID and returns a String with the error, otherwise none
fn validate_uuid(vd_uuid: String) -> Result<()> {
    match Uuid::parse_str(vd_uuid.as_str()) {
        Ok(id) => {
            if id.get_version() != Some(Random) {
                // Wrong version, need Random aka v4
                Err("SelfDefined(Wrong UUID version)".into())
            } else {
                Ok(())
            }
        }
        Err(_) => Err("SelfDefined(Not a UUID string)".into()),
    }
}

async fn get_patch_validation_status(Path(gp_uuid): Path<String>) -> impl IntoResponse {
    println!("get patch validation status");

    if let Err(error_message) = validate_uuid(gp_uuid) {
        return (
            StatusCode::OK,
            Json(status_unknown(error_message.to_string().as_str())),
        );
    }

    (StatusCode::OK, Json(status_accepted_gp(Uuid::new_v4())))
}

async fn submit_patch(Json(payload): Json<GeneratePatchCheckRequest>) -> impl IntoResponse {
    println!("validate patch");

    if let Err(error_message) = validate_uuid(payload.cpv_uuid) {
        return (
            StatusCode::OK,
            Json(status_unknown(error_message.to_string().as_str())),
        );
    }

    (StatusCode::OK, Json(status_accepted_gp(Uuid::new_v4())))
}
#[tokio::main]
async fn main() -> Result<()> {
    let listener = TcpListener::bind("127.0.0.1:8080").await.unwrap();
    info!("{:<12} - {:?}\n", "LISTENING", listener.local_addr());

    let routes = Router::new()
        .route("/health/", get(get_health))
        .route(
            "/submission/vds/:vd_uuid",
            get(get_proof_of_vulnerability_status),
        )
        .route(
            "/submission/vds/",
            post(submit_proof_of_vulnerability_discovery),
        )
        .route("/submission/gp/:vd_uuid", get(get_patch_validation_status))
        .route("/submission/gp/", post(submit_patch));

    axum::serve(listener, routes.into_make_service())
        .await
        .unwrap();

    Ok(())
}
