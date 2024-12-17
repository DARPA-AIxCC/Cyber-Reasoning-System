use crate::state::AppState;
use axum::extract::{DefaultBodyLimit, Path, State};
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::routing::{get, post};
use axum::{Json, Router};
use base64::engine::general_purpose;
use base64::Engine;
use lib_iapi::{
    status_accepted_vd, status_gp, status_health_ok, status_rejected, status_unknown,
    GeneratePatchCheckRequest, ProofOfVulnerabilityDiscovery,
};
use log::info;
use uuid::Uuid;
use uuid::Version::Random;

static ROUTE_HEALTH: &str = "/health/";

pub fn create_app(state: AppState) -> Router {
    Router::new()
        .route(
            "/submission/vds/:vd_uuid",
            get(get_proof_of_vulnerability_status),
        )
        .route(
            "/submission/vds/",
            post(submit_proof_of_vulnerability_discovery),
        )
        .route("/submission/gp/:vd_uuid", get(get_patch_validation_status))
        .route("/submission/gp/", post(submit_patch))
        .route(ROUTE_HEALTH, get(get_health))
        .with_state(state)
        .layer(DefaultBodyLimit::max(3 * 1024 * 1024))
}

async fn get_health(State(state): State<AppState>) -> impl IntoResponse {
    info!("Get: Health");
    // Got health request: forward request to actual server

    match lib_iapi::client::check_health(&state.remote_url).await {
        Ok(status) => {
            info!("Got status {}", status);
            if status.as_str().contains("ok") {
                (StatusCode::OK, Json(status_health_ok()))
            } else {
                (StatusCode::INTERNAL_SERVER_ERROR, Json(status_health_ok()))
            }
        }
        Err(e) => {
            info!("Unknown error: {e:?}");
            (
                StatusCode::SERVICE_UNAVAILABLE,
                Json(status_unknown(format!("Unknown error: {e:?}").as_str())),
            )
        }
    }
}

async fn submit_proof_of_vulnerability_discovery(
    State(state): State<AppState>,
    Json(payload): Json<ProofOfVulnerabilityDiscovery>,
) -> impl IntoResponse {
    info!("Post ProofOfVulnerability: {payload:#?}");
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
    match general_purpose::STANDARD.decode(&payload.pov.data) {
        Ok(decoded_payload) => {
            // Check patch size
            if decoded_payload.len() > 2 * 1024 * 1024 {
                return (
                    StatusCode::BAD_REQUEST,
                    Json(status_unknown(
                        format!("Provided input is too large {}", decoded_payload.len()).as_str(),
                    )),
                );
            }
        }
        Err(_e) => {
            return (StatusCode::BAD_REQUEST, Json(status_rejected()));
        }
    }

    // Cache if not known yet
    // let cache = state.discovery_cache.lock().await;
    //

    // Check for a specific one
    if state.discovery_cache.lock().await.contains(&payload) {
        return (StatusCode::BAD_REQUEST, Json(status_rejected()));
    }

    state.discovery_cache.lock().await.insert(payload.clone());

    match lib_iapi::client::submit_proof_of_vulnerability_discovery2(&state.remote_url, payload)
        .await
    {
        Ok(response) => {
            if let Some(vd_uuid) = response
                .vd_uuid
                .and_then(|s| Uuid::parse_str(s.as_str()).ok())
            {
                (StatusCode::OK, Json(status_accepted_vd(vd_uuid)))
            } else {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(status_unknown("No vd UUID returned")),
                )
            }
        }
        Err(_) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(status_unknown("No vd UUID returned")),
        ),
    }
}

async fn get_proof_of_vulnerability_status(
    Path(vd_uuid): Path<String>,
    State(state): State<AppState>,
) -> impl IntoResponse {
    info!("vds with path called: {vd_uuid}");

    let vd_uuid = match validate_uuid(vd_uuid.as_str()) {
        Ok(uuid) => uuid,
        Err(error_message) => {
            return (
                StatusCode::OK,
                Json(status_unknown(error_message.to_string().as_str())),
            )
        }
    };

    match lib_iapi::client::check_vulnerability_discovery_status(
        &state.remote_url,
        vd_uuid.to_string(),
    )
    .await
    {
        Ok(status) => (StatusCode::OK, Json(status)),
        Err(error) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(status_unknown(error.to_string().as_str())),
        ),
    }
}

async fn get_patch_validation_status(
    Path(gp_uuid): Path<String>,
    State(state): State<AppState>,
) -> impl IntoResponse {
    info!("get patch validation status");

    let gp_uuid = match validate_uuid(gp_uuid.as_str()) {
        Ok(uuid) => uuid,
        Err(error_message) => {
            return (
                StatusCode::OK,
                Json(status_unknown(error_message.to_string().as_str())),
            )
        }
    };

    match lib_iapi::client::check_generated_patch_status(&state.remote_url, gp_uuid.to_string())
        .await
    {
        Ok(status) => (StatusCode::OK, Json(status_gp(gp_uuid, status.status))),
        Err(error) => (
            StatusCode::OK,
            Json(status_unknown(error.to_string().as_str())),
        ),
    }
}

async fn submit_patch(
    State(state): State<AppState>,
    Json(payload): Json<GeneratePatchCheckRequest>,
) -> impl IntoResponse {
    info!("validate patch");

    let cpv_uuid = match validate_uuid(payload.cpv_uuid.as_str()) {
        Ok(uuid) => uuid,
        Err(error_message) => {
            return (
                StatusCode::OK,
                Json(status_unknown(error_message.to_string().as_str())),
            )
        }
    };

    // Check patch size
    if payload.data.len() > 100 * 1024 {
        return (
            StatusCode::BAD_REQUEST,
            Json(status_unknown(
                format!("Provided patch is too large {}", payload.data.len()).as_str(),
            )),
        );
    }

    match lib_iapi::client::submit_generated_patch(
        &state.remote_url,
        cpv_uuid.to_string(),
        payload.data,
    )
    .await
    {
        Ok(response) => (StatusCode::OK, Json(response)),
        Err(error) => (
            StatusCode::OK,
            Json(status_unknown(error.to_string().as_str())),
        ),
    }
}

/// Validates the UUID and returns a String with the error, otherwise none
pub fn validate_uuid(vd_uuid: &str) -> crate::Result<Uuid> {
    match Uuid::parse_str(vd_uuid) {
        Ok(id) => {
            if id.get_version() != Some(Random) {
                // Wrong version, need Random aka v4
                Err("SelfDefined(Wrong UUID version)".into())
            } else {
                Ok(id)
            }
        }
        Err(_) => Err("SelfDefined(Not a UUID string)".into()),
    }
}

#[cfg(test)]
mod test {
    use crate::router::{create_app, ROUTE_HEALTH};
    use crate::state::AppState;
    use crate::validating_router::validating;
    use crate::validating_router::validating::CountingState;
    use axum_test::{TestServer, TestServerConfig};
    use lib_iapi::{IAPIServerResponse, Status};
    use serde_json::json;
    use std::sync::Arc;

    #[tokio::test]
    async fn check_health() {
        // Create test backend server
        let validating_server_config = TestServerConfig::builder().http_transport().build();

        let cs = CountingState::default();

        // Start validating instance, i.e. mimicking remote backend server.
        let validating_app = validating::create_app(cs.clone());
        let validating_server =
            TestServer::new_with_config(validating_app, validating_server_config).unwrap();
        let validating_url = validating_server.server_address().unwrap();

        let app_state = AppState {
            remote_url: validating_url,

            discovery_cache: Arc::new(Default::default()),
        };

        let app = create_app(app_state);
        let server = TestServer::new(app).unwrap();

        // Get the request.
        let response = server.get(ROUTE_HEALTH).await.json::<IAPIServerResponse>();

        assert_eq!(
            response,
            IAPIServerResponse {
                status: Status::Ok,
                vd_uuid: None,
                cpv_uuid: None,
                gp_uuid: None,
            }
        );

        assert_eq!(cs.health(), 1);
    }

    #[tokio::test]
    async fn submit_vds() {
        // Create test backend server
        let validating_server_config = TestServerConfig::builder().http_transport().build();

        let cs = CountingState::default();

        // Start validating instance, i.e. mimicking remote backend server.
        let validating_app = validating::create_app(cs.clone());
        let validating_server =
            TestServer::new_with_config(validating_app, validating_server_config).unwrap();
        let validating_url = validating_server.server_address().unwrap();

        let app_state = AppState {
            remote_url: validating_url,
            discovery_cache: Arc::new(Default::default()),
        };

        let app = create_app(app_state);
        let server = TestServer::new(app).unwrap();

        // Submit discovery request

        let response = server.post("/submission/vds/").json(
            &json!({
                "cp_name":"linux kernel",
                "pou":{
                    "commit_sha1":"2923ffa6e0572ee6572245f980acfcfb872fcf74",
                    "sanitizer":"id_1"
                },
                "pov":{
                    "harness":"id_2",
                    "data":"LS0tIGhlbGxvLmMJMjAxNC0xMC0wNyAxODoxNzo0OS4wMDAwMDAwMDAgKzA1MzANCisrKyBoZWxsb19uZXcuYwkyMDE0LTEwLTA3IDE4OjE3OjU0LjAwMDAwMDAwMCArMDUzMA0KQEAgLTEsNSArMSw2IEBADQogI2luY2x1ZGUgPHN0ZGlvLmg+DQogDQotaW50IG1haW4oKSB7DQoraW50IG1haW4oaW50IGFyZ2MsIGNoYXIgKmFyZ3ZbXSkgew0KIAlwcmludGYoIkhlbGxvIFdvcmxkXG4iKTsNCisJcmV0dXJuIDA7DQogfQ=="
                }
        })).await.json::<IAPIServerResponse>();

        assert_eq!(response.status, Status::Accepted,);
        let vd_uuid = response.vd_uuid.unwrap();

        assert_eq!(cs.submit_proof_of_vulnerability_discovery(), 1);
        assert_eq!(cs.proof_of_vulnerability_status(), 0);

        let path = format!("/submission/vds/{vd_uuid}");
        let r2 = server.get(path.as_str()).await.json::<IAPIServerResponse>();

        assert_eq!(r2.status, Status::Accepted,);

        assert_eq!(cs.proof_of_vulnerability_status(), 1);
    }

    #[tokio::test]
    async fn submit_vds_again() {
        // Create test backend server
        let validating_server_config = TestServerConfig::builder().http_transport().build();

        let cs = CountingState::default();

        // Start validating instance, i.e. mimicking remote backend server.
        let validating_app = validating::create_app(cs.clone());
        let validating_server =
            TestServer::new_with_config(validating_app, validating_server_config).unwrap();
        let validating_url = validating_server.server_address().unwrap();

        let app_state = AppState {
            remote_url: validating_url,
            discovery_cache: Arc::new(Default::default()),
        };

        let app = create_app(app_state);
        let server = TestServer::new(app).unwrap();

        // Submit discovery request

        let _response = server.post("/submission/vds/").json(
            &json!({
                "cp_name":"linux kernel",
                "pou":{
                    "commit_sha1":"2923ffa6e0572ee6572245f980acfcfb872fcf74",
                    "sanitizer":"id_1"
                },
                "pov":{
                    "harness":"id_2",
                    "data":"LS0tIGhlbGxvLmMJMjAxNC0xMC0wNyAxODoxNzo0OS4wMDAwMDAwMDAgKzA1MzANCisrKyBoZWxsb19uZXcuYwkyMDE0LTEwLTA3IDE4OjE3OjU0LjAwMDAwMDAwMCArMDUzMA0KQEAgLTEsNSArMSw2IEBADQogI2luY2x1ZGUgPHN0ZGlvLmg+DQogDQotaW50IG1haW4oKSB7DQoraW50IG1haW4oaW50IGFyZ2MsIGNoYXIgKmFyZ3ZbXSkgew0KIAlwcmludGYoIkhlbGxvIFdvcmxkXG4iKTsNCisJcmV0dXJuIDA7DQogfQ=="
                }
        })).await.json::<IAPIServerResponse>();

        let response = server.post("/submission/vds/").json(
            &json!({
                "cp_name":"linux kernel",
                "pou":{
                    "commit_sha1":"2923ffa6e0572ee6572245f980acfcfb872fcf74",
                    "sanitizer":"id_1"
                },
                "pov":{
                    "harness":"id_2",
                    "data":"LS0tIGhlbGxvLmMJMjAxNC0xMC0wNyAxODoxNzo0OS4wMDAwMDAwMDAgKzA1MzANCisrKyBoZWxsb19uZXcuYwkyMDE0LTEwLTA3IDE4OjE3OjU0LjAwMDAwMDAwMCArMDUzMA0KQEAgLTEsNSArMSw2IEBADQogI2luY2x1ZGUgPHN0ZGlvLmg+DQogDQotaW50IG1haW4oKSB7DQoraW50IG1haW4oaW50IGFyZ2MsIGNoYXIgKmFyZ3ZbXSkgew0KIAlwcmludGYoIkhlbGxvIFdvcmxkXG4iKTsNCisJcmV0dXJuIDA7DQogfQ=="
                }
        })).await.json::<IAPIServerResponse>();
        assert_eq!(response.status, Status::Rejected,);

        assert_eq!(cs.submit_proof_of_vulnerability_discovery(), 1);
        assert_eq!(cs.proof_of_vulnerability_status(), 0);
    }

    #[tokio::test]
    async fn submit_vds_input_too_large() {
        // Create test backend server
        let validating_server_config = TestServerConfig::builder().http_transport().build();

        let cs = CountingState::default();

        // Start validating instance, i.e. mimicking remote backend server.
        let validating_app = validating::create_app(cs.clone());
        let validating_server =
            TestServer::new_with_config(validating_app, validating_server_config).unwrap();
        let validating_url = validating_server.server_address().unwrap();

        let app_state = AppState {
            remote_url: validating_url,
            discovery_cache: Arc::new(Default::default()),
        };

        let app = create_app(app_state);
        let server = TestServer::new(app).unwrap();

        // Submit discovery request
        let data = String::from_utf8(vec![99; 2 * 1024 * 1024 + 1]).unwrap();

        let response = server
            .post("/submission/vds/")
            .json(&json!({
                    "cp_name":"linux kernel",
                    "pou":{
                        "commit_sha1":"2923ffa6e0572ee6572245f980acfcfb872fcf74",
                        "sanitizer":"id_1"
                    },
                    "pov":{
                        "harness":"id_2",
                        "data":data
                    }
            }))
            .await;
        println!("RESPONSE {response:?}");

        let response = server
            .post("/submission/vds/")
            .json(&json!({
                    "cp_name":"linux kernel",
                    "pou":{
                        "commit_sha1":"2923ffa6e0572ee6572245f980acfcfb872fcf74",
                        "sanitizer":"id_1"
                    },
                    "pov":{
                        "harness":"id_2",
                        "data":data
                    }
            }))
            .await
            .json::<IAPIServerResponse>();

        assert_eq!(response.status, Status::Rejected);

        assert_eq!(cs.submit_proof_of_vulnerability_discovery(), 0);
    }

    #[tokio::test]
    async fn submit_patch() {
        // Create test backend server
        let validating_server_config = TestServerConfig::builder().http_transport().build();

        let cs = CountingState::default();

        // Start validating instance, i.e. mimicking remote backend server.
        let validating_app = validating::create_app(cs.clone());
        let validating_server =
            TestServer::new_with_config(validating_app, validating_server_config).unwrap();
        let validating_url = validating_server.server_address().unwrap();

        let app_state = AppState {
            remote_url: validating_url,
            discovery_cache: Arc::new(Default::default()),
        };

        let app = create_app(app_state);
        let server = TestServer::new(app).unwrap();

        // Submit discovery request
        let response = server.post("/submission/gp/").json(
            &json!({
                "cpv_uuid":"17820e40-2a2b-4de1-931f-72cefb6d490d",
                "data":"LS0tIGhlbGxvLmMJMjAxNC0xMC0wNyAxODoxNzo0OS4wMDAwMDAwMDAgKzA1MzANCisrKyBoZWxsb19uZXcuYwkyMDE0LTEwLTA3IDE4OjE3OjU0LjAwMDAwMDAwMCArMDUzMA0KQEAgLTEsNSArMSw2IEBADQogI2luY2x1ZGUgPHN0ZGlvLmg+DQogDQotaW50IG1haW4oKSB7DQoraW50IG1haW4oaW50IGFyZ2MsIGNoYXIgKmFyZ3ZbXSkgew0KIAlwcmludGYoIkhlbGxvIFdvcmxkXG4iKTsNCisJcmV0dXJuIDA7DQogfQ=="
        })).await.json::<IAPIServerResponse>();

        assert_eq!(response.status, Status::Accepted,);
        let gp_uuid = response.gp_uuid.unwrap();

        assert_eq!(cs.submit_patch(), 1);
        assert_eq!(cs.get_patch_validation_status(), 0);

        let path = format!("/submission/gp/{gp_uuid}");
        let r2 = server.get(path.as_str()).await.json::<IAPIServerResponse>();

        assert_eq!(r2.status, Status::Accepted,);

        assert_eq!(cs.get_patch_validation_status(), 1);
    }

    #[tokio::test]
    async fn submit_patch_too_large_patch() {
        // Create test backend server
        let validating_server_config = TestServerConfig::builder().http_transport().build();

        let cs = CountingState::default();

        // Start validating instance, i.e. mimicking remote backend server.
        let validating_app = validating::create_app(cs.clone());
        let validating_server =
            TestServer::new_with_config(validating_app, validating_server_config).unwrap();
        let validating_url = validating_server.server_address().unwrap();

        let app_state = AppState {
            remote_url: validating_url,
            discovery_cache: Arc::new(Default::default()),
        };

        let app = create_app(app_state);
        let server = TestServer::new(app).unwrap();

        let data = String::from_utf8(vec![99; 100 * 1024 + 1]).unwrap();

        // Submit discovery request
        let response = server
            .post("/submission/gp/")
            .json(&json!({
                    "cpv_uuid":"17820e40-2a2b-4de1-931f-72cefb6d490d",
                    "data": data
            }))
            .await
            .json::<IAPIServerResponse>();

        assert_eq!(
            response.status,
            Status::UnexpectedError("Provided patch is too large 102401".into())
        );

        // Check: Should never reach backend
        assert_eq!(cs.submit_patch(), 0);
    }
}
