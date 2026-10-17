ARG BUILDER=golang:1.26.8-bookworm@sha256:dc9ad6c05acc7a88e5b71bde60a5fe3bd4b9f0db209011711b464107438a8107
ARG RUNTIME=debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587
FROM --platform=$BUILDPLATFORM ${BUILDER} AS sources
ENV GOTOOLCHAIN=local
COPY .build/inputs.env /inputs.env
COPY .build/minio.tar.gz .build/mc.tar.gz /archives/
RUN . /inputs.env && \
    echo "$MINIO_SHA256  /archives/minio.tar.gz" | sha256sum -c - && \
    echo "$MC_SHA256  /archives/mc.tar.gz" | sha256sum -c - && \
    mkdir -p /src/minio /src/mc && \
    tar -xzf /archives/minio.tar.gz -C /src/minio --strip-components=1 && \
    tar -xzf /archives/mc.tar.gz -C /src/mc --strip-components=1
RUN cd /src/minio && sha256sum go.mod go.sum > /tmp/minio-locks && \
    go mod download && go mod verify && go mod vendor && sha256sum -c /tmp/minio-locks
RUN cd /src/mc && sha256sum go.mod go.sum > /tmp/mc-locks && \
    go mod download && go mod verify && go mod vendor && sha256sum -c /tmp/mc-locks
COPY Dockerfile inputs.json LICENSE NOTICE.md README.md SECURITY.md /recipe/
COPY scripts/ /recipe/scripts/
COPY .github/ /recipe/.github/
RUN mkdir /release && \
    tar -czf /release/corresponding-source.tar.gz -C / src recipe archives inputs.env && \
    cp /recipe/inputs.json /release/ && \
    cp /src/minio/go.mod /release/minio.go.mod && cp /src/minio/go.sum /release/minio.go.sum && \
    cp /src/mc/go.mod /release/mc.go.mod && cp /src/mc/go.sum /release/mc.go.sum

FROM scratch AS source-bundle
COPY --from=sources /release/ /

FROM sources AS builder
ARG TARGETARCH
RUN --network=none sh /recipe/scripts/compile.sh

FROM ${RUNTIME} AS runtime
ARG REVISION
ARG VERSION
LABEL org.opencontainers.image.title="Unofficial MinIO Community Edition with mc" \
      org.opencontainers.image.description="Independent source build published by Yelqo; see SECURITY.md for scope and known risks" \
      org.opencontainers.image.vendor="Yelqo" \
      org.opencontainers.image.authors="Yelqo" \
      org.opencontainers.image.source="https://github.com/Yelqo/minio-builds" \
      org.opencontainers.image.url="https://github.com/Yelqo/minio-builds" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.revision=$REVISION \
      org.opencontainers.image.version=$VERSION \
      io.yelqo.minio.upstream.revision="9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a" \
      io.yelqo.mc.upstream.revision="7394ce0dd2a80935aded936b09fa12cbb3cb8096"
COPY --from=builder /out/ /usr/local/bin/
COPY --from=sources /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=sources /src/minio/LICENSE /usr/share/licenses/minio/LICENSE
COPY --from=sources /src/mc/LICENSE /usr/share/licenses/mc/LICENSE
COPY NOTICE.md inputs.json /usr/share/doc/minio-builds/
COPY --chmod=755 scripts/entrypoint.sh /usr/local/bin/entrypoint
EXPOSE 9000 9001
VOLUME ["/data"]
ENTRYPOINT ["/usr/local/bin/entrypoint"]
CMD ["server", "/data"]
