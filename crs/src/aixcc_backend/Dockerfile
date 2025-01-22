# Build AIxCC backend
FROM rust:1.81-bullseye AS chef
RUN cargo install cargo-chef
WORKDIR /usr/src/aixcc_backend


FROM chef AS planner
COPY . .
RUN cargo chef prepare --recipe-path recipe.json

FROM chef AS builder
COPY --from=planner /usr/src/aixcc_backend/recipe.json recipe.json
# Build dependencies
RUN cargo chef cook --release --recipe-path recipe.json

# Build application
COPY . .
RUN cargo build --release

FROM debian:bullseye-slim
RUN apt-get update \
    && apt-get install -y ca-certificates tzdata curl rsync \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 9042


ARG APP=/usr/src/aixcc-apps
# ARG APP_USER="aixcc"

ENV TZ=Etc/UTC

# RUN groupadd $APP_USER \
#     && useradd -g $APP_USER $APP_USER \
#     && mkdir -p ${APP}

COPY --from=builder /usr/src/aixcc_backend/target/release/aixcc-reader ${APP}/aixcc-reader
COPY --from=builder /usr/src/aixcc_backend/target/release/aixcc_status_server ${APP}/aixcc_status_server
COPY --from=builder /usr/src/aixcc_backend/run.sh ${APP}/
COPY --from=builder /usr/src/aixcc_backend/aixcc-reader/cerberus_configuration ${APP}/cerberus_configuration

# Copy iAPI Proxy Server
COPY --from=builder /usr/src/aixcc_backend/target/release/iapi_proxy_server ${APP}/iapi_proxy_server

# RUN chown -R $APP_USER:$APP_USER ${APP}

# USER $APP_USER
WORKDIR ${APP}

CMD ["./run.sh"]