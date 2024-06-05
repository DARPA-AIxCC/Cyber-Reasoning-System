#[cfg(test)]
pub mod validating {
    use axum::extract::{Path, State};
    use axum::http::StatusCode;
    use axum::response::IntoResponse;
    use axum::routing::{get, post};
    use axum::{Json, Router};
    use lib_iapi::{
        status_accepted_cpv, status_accepted_gp, status_accepted_vd, status_health_ok,
        GeneratePatchCheckRequest, ProofOfVulnerabilityDiscovery,
    };
    use log::info;
    use std::sync::{Arc, Mutex};
    use tracing::debug;
    use uuid::Uuid;

    #[derive(Clone)]
    pub struct CountingState {
        call_health: Arc<Mutex<u64>>,

        call_get_proof_of_vulnerability_status: Arc<Mutex<u64>>,
        call_submit_proof_of_vulnerability_discovery: Arc<Mutex<u64>>,

        call_submit_patch: Arc<Mutex<u64>>,
        call_get_patch_validation_status: Arc<Mutex<u64>>,
    }

    impl CountingState {
        pub fn inc_health_call(&self) {
            let mut lock = self.call_health.lock().unwrap();
            *lock += 1;
        }

        pub fn health(&self) -> u64 {
            let lock = self.call_health.lock().unwrap();
            *lock
        }
        pub fn inc_get_proof_of_vulnerability_status(&self) {
            let mut lock = self.call_get_proof_of_vulnerability_status.lock().unwrap();
            *lock += 1;
        }

        pub fn proof_of_vulnerability_status(&self) -> u64 {
            let lock = self.call_get_proof_of_vulnerability_status.lock().unwrap();
            *lock
        }

        pub fn inc_submit_proof_of_vulnerability_discovery(&self) {
            let mut lock = self
                .call_submit_proof_of_vulnerability_discovery
                .lock()
                .unwrap();
            *lock += 1;
        }
        pub fn submit_proof_of_vulnerability_discovery(&self) -> u64 {
            let lock = self
                .call_submit_proof_of_vulnerability_discovery
                .lock()
                .unwrap();
            *lock
        }

        pub fn inc_submit_patch(&self) {
            let mut lock = self.call_submit_patch.lock().unwrap();
            *lock += 1;
        }
        pub fn submit_patch(&self) -> u64 {
            let lock = self.call_submit_patch.lock().unwrap();
            *lock
        }

        pub fn inc_get_patch_validation_status(&self) {
            let mut lock = self.call_get_patch_validation_status.lock().unwrap();
            *lock += 1;
        }
        pub fn get_patch_validation_status(&self) -> u64 {
            let lock = self.call_get_patch_validation_status.lock().unwrap();
            *lock
        }
    }

    impl Default for CountingState {
        fn default() -> Self {
            CountingState {
                call_health: Arc::new(Mutex::new(0)),
                call_get_proof_of_vulnerability_status: Arc::new(Mutex::new(0)),
                call_submit_proof_of_vulnerability_discovery: Arc::new(Mutex::new(0)),
                call_submit_patch: Arc::new(Mutex::new(0)),
                call_get_patch_validation_status: Arc::new(Mutex::new(0)),
            }
        }
    }

    pub fn create_app(state: CountingState) -> Router {
        Router::new()
            .route("/health/", get(get_health))
            .route(
                "/submission/vds/:vd_uuid",
                get(get_proof_of_vulnerability_status),
            )
            .route(
                "/submission/vds/",
                post(submit_proof_of_vulnerability_discovery),
            )
            .route("/submission/gp/:gp_uuid", get(get_patch_validation_status))
            .route("/submission/gp/", post(submit_patch))
            .with_state(state)
    }
    async fn get_health(State(state): State<CountingState>) -> impl IntoResponse {
        info!("Get: Health (validated)");
        state.inc_health_call();
        (StatusCode::OK, Json(status_health_ok()))
    }

    async fn submit_proof_of_vulnerability_discovery(
        State(state): State<CountingState>,
        Json(payload): Json<ProofOfVulnerabilityDiscovery>,
    ) -> impl IntoResponse {
        info!("Post ProofOfVulnerability: {payload:#?} (validated)");
        state.inc_submit_proof_of_vulnerability_discovery();

        (StatusCode::OK, Json(status_accepted_vd(Uuid::new_v4())))
    }

    async fn get_proof_of_vulnerability_status(
        State(state): State<CountingState>,
        Path(vd_uuid): Path<String>,
    ) -> impl IntoResponse {
        info!("vds with path called: {vd_uuid} (validated)");

        state.inc_get_proof_of_vulnerability_status();

        (StatusCode::OK, Json(status_accepted_cpv(Uuid::new_v4())))
    }

    async fn get_patch_validation_status(
        Path(gp_id): Path<String>,
        State(state): State<CountingState>,
    ) -> impl IntoResponse {
        info!("get patch validation status (validated)");
        debug!("gp_id: {gp_id:?}");
        state.inc_get_patch_validation_status();

        (StatusCode::OK, Json(status_accepted_gp(Uuid::new_v4())))
    }

    async fn submit_patch(
        State(state): State<CountingState>,
        Json(payload): Json<GeneratePatchCheckRequest>,
    ) -> impl IntoResponse {
        info!("validate patch (validated)");

        debug!("Payload: {payload:?}");

        state.inc_submit_patch();

        (StatusCode::OK, Json(status_accepted_gp(Uuid::new_v4())))
    }
}
