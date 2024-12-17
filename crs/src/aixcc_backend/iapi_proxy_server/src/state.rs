use crate::config::Arguments;
use lib_iapi::ProofOfVulnerabilityDiscovery;
use std::collections::HashSet;
use std::sync::Arc;
use tokio::sync::Mutex;
use url::Url;

#[derive(Clone)]
pub struct AppState {
    pub remote_url: Url,
    pub discovery_cache: Arc<Mutex<HashSet<ProofOfVulnerabilityDiscovery>>>,
}

pub fn create_app_state(_args: &Arguments, remote_url: Url) -> crate::Result<AppState> {
    Ok(AppState {
        remote_url,
        discovery_cache: Arc::new(Default::default()),
    })
}
