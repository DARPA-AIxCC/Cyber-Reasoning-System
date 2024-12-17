use crate::{
    GeneratePatchCheckRequest, IAPIServerResponse, ProofOfUnderstanding, ProofOfVulnerability,
    ProofOfVulnerabilityDiscovery,
};
use base64::Engine;
use reqwest::Client;
use serde_json::json;
use url::Url;

pub type Result<T> = core::result::Result<T, Error>;
pub type Error = Box<dyn std::error::Error>;

pub async fn check_health(api_url: &Url) -> Result<String> {
    let api_url = api_url.as_str();
    let path = "health/";
    let body = reqwest::get(format!("{api_url}{path}"))
        .await?
        .text()
        .await?;
    Ok(body)
}

pub async fn submit_generated_patch(
    api_url: &Url,
    cpv_uuid: String,
    patch_content: String,
) -> Result<IAPIServerResponse> {
    let data = base64::engine::general_purpose::STANDARD.encode(patch_content.as_bytes());
    let pg_submission = GeneratePatchCheckRequest { cpv_uuid, data };

    let api_url = api_url.as_str();
    let path = "submission/gp/";

    let request_body = json!(pg_submission);
    let response = Client::new()
        .post(format!("{api_url}{path}"))
        .json(&request_body)
        .send()
        .await?;

    Ok(response.json::<IAPIServerResponse>().await?)
}

pub async fn submit_proof_of_vulnerability_discovery(
    api_url: &Url,
    cp_name: String,
    sanitizer_id: String,
    commit_sha1: String,
    harness_id: String,
    harness_input: String,
) -> Result<String> {
    let data = base64::engine::general_purpose::STANDARD.encode(harness_input.as_bytes());
    let vd_proof = ProofOfVulnerabilityDiscovery {
        cp_name,
        pou: ProofOfUnderstanding {
            commit_sha1,
            sanitizer: sanitizer_id,
        },
        pov: ProofOfVulnerability {
            harness: harness_id,
            data,
        },
    };

    let response = submit_proof_of_vulnerability_discovery2(api_url, vd_proof).await?;
    Ok(format!("{response:#?}"))
}

pub async fn submit_proof_of_vulnerability_discovery2(
    api_url: &Url,
    vd_proof: ProofOfVulnerabilityDiscovery,
) -> Result<IAPIServerResponse> {
    let api_url = api_url.as_str();
    let path = "submission/vds/";

    let request_body = json!(vd_proof);
    let response = Client::new()
        .post(format!("{api_url}{path}"))
        .json(&request_body)
        .send()
        .await?;

    let response: IAPIServerResponse = response.json().await?;

    Ok(response)
}

pub async fn check_vulnerability_discovery_status(
    api_url: &Url,
    vds_id: String,
) -> Result<IAPIServerResponse> {
    let api_url = api_url.as_str();
    let path = format!("submission/vds/{vds_id}");

    let response: IAPIServerResponse = reqwest::get(format!("{api_url}{path}"))
        .await?
        .json()
        .await?;

    Ok(response)
}

pub async fn check_generated_patch_status(
    api_url: &Url,
    gp_id: String,
) -> Result<IAPIServerResponse> {
    let api_url = api_url.as_str();
    let path = format!("submission/gp/{gp_id}");
    let response: IAPIServerResponse = reqwest::get(format!("{api_url}{path}"))
        .await?
        .json()
        .await?;

    Ok(response)
}
