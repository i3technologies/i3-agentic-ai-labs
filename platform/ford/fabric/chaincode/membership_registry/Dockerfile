FROM golang:1.21 AS builder
ENV GONOSUMCHECK=*
ENV GONOSUMDB=*
ENV GOFLAGS=-mod=mod
ENV GONOPROXY=*
ENV GONOSUMCHECK=*
ENV CGO_ENABLED=0
ENV GOOS=linux
WORKDIR /chaincode
COPY go.mod .
COPY membership_registry.go .
RUN go build -o /chaincode/membership-registry .

FROM debian:bookworm-slim
RUN groupadd -r fabric && useradd -r -g fabric fabric
COPY --from=builder /chaincode/membership-registry /usr/local/bin/membership-registry
RUN chown fabric:fabric /usr/local/bin/membership-registry
USER fabric
ENV CHAINCODE_SERVER_ADDRESS=0.0.0.0:9999
EXPOSE 9999
CMD ["/usr/local/bin/membership-registry", "-peer.address", "peer0-i3tech.i3-ford.svc.cluster.local:7052"]
