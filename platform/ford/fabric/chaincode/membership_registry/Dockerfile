FROM golang:1.21 AS builder
ENV GONOSUMCHECK=*
ENV GONOSUMDB=*
ENV GOFLAGS=-mod=mod
ENV GONOPROXY=*
ENV GONOSUMCHECK=*
WORKDIR /chaincode
COPY go.mod .
COPY membership_registry.go .
RUN go mod download -x 2>&1 | tail -5 || true
RUN CGO_ENABLED=0 GOOS=linux go build -v -o /chaincode/membership-registry .

FROM debian:bookworm-slim
RUN addgroup -S fabric && adduser -S fabric -G fabric
COPY --from=builder /chaincode/membership-registry /usr/local/bin/membership-registry
RUN chown fabric:fabric /usr/local/bin/membership-registry
USER fabric
ENV CHAINCODE_SERVER_ADDRESS=0.0.0.0:9999
EXPOSE 9999
CMD ["/usr/local/bin/membership-registry"]
